//! Deterministic watchdog supervision and restart policy.
//!
//! This module owns the small supervision decision engine for `opsd`,
//! `guardian`, and the broker gateway. It records health state, restart
//! actions, restart-loop escalation, and the `RECOVERING` handoff required
//! after an `opsd` restart.

use std::fs;
use std::path::Path;

use crate::{HealthState, SupervisionTarget};

/// Observability category for process supervision and restart policy.
pub const SUPERVISION_HEALTH_CATEGORY: &str = "process_supervision_and_restart_policy";
/// The required runtime gate after an `opsd` restart.
pub const OPSD_RECOVERING_GATE_STATE: &str = "RECOVERING";
/// Number of restart attempts allowed before the watchdog quarantines a target.
pub const MAX_RESTART_ATTEMPTS_BEFORE_QUARANTINE: u32 = 2;

/// Coarse liveness states the watchdog can observe without owning runtime state.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProcessLiveness {
    Healthy,
    Unresponsive,
    Down,
}

impl ProcessLiveness {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Healthy => "healthy",
            Self::Unresponsive => "unresponsive",
            Self::Down => "down",
        }
    }
}

/// Supervision action selected by the watchdog.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SupervisionAction {
    Observe,
    RestartOpsd,
    RestartGuardian,
    RestartBrokerGateway,
    QuarantineTarget,
}

impl SupervisionAction {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Observe => "observe",
            Self::RestartOpsd => "restart_opsd",
            Self::RestartGuardian => "restart_guardian",
            Self::RestartBrokerGateway => "restart_broker_gateway",
            Self::QuarantineTarget => "quarantine_target",
        }
    }
}

/// One target-specific health observation captured by the watchdog.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisionObservation {
    pub health_check_id: String,
    pub target: SupervisionTarget,
    pub observed_at_utc: String,
    pub liveness: ProcessLiveness,
    pub heartbeat_age_seconds: u64,
    pub heartbeat_budget_seconds: u64,
    pub prior_restart_attempts: u32,
    pub prior_drill_evidence_id: Option<String>,
    pub recovering_gate_supported: bool,
    pub last_exit_reason: String,
}

/// Correlated bundle of process observations evaluated as one supervision run.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisionBundle {
    pub run_id: String,
    pub correlation_id: String,
    pub decision_trace_id: String,
    pub artifact_manifest_id: String,
    pub observations: Vec<SupervisionObservation>,
}

/// One target-specific machine-readable supervision report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisionTargetReport {
    pub health_check_id: String,
    pub target: SupervisionTarget,
    pub state: HealthState,
    pub action: SupervisionAction,
    pub reason_code: String,
    pub failure_category: &'static str,
    pub prior_restart_attempts: u32,
    pub resulting_restart_attempts: u32,
    pub required_recovery_gate_state: Option<String>,
    pub prior_drill_evidence_id: Option<String>,
    pub retained_evidence_id: String,
    pub operator_summary: String,
}

/// One correlated supervision event retained for later diagnostics.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisionTraceEvent {
    pub target: SupervisionTarget,
    pub event_type: String,
    pub correlation_id: String,
    pub decision_trace_id: String,
    pub artifact_manifest_id: String,
    pub reason_code: String,
    pub action: Option<SupervisionAction>,
    pub high_priority_lane: bool,
    pub sequence_number: usize,
}

/// Aggregate watchdog report covering one supervision run.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisionRunReport {
    pub run_id: String,
    pub state: HealthState,
    pub reason_code: String,
    pub correlation_id: String,
    pub decision_trace_id: String,
    pub artifact_manifest_id: String,
    pub restarted_targets: Vec<SupervisionTarget>,
    pub quarantined_targets: Vec<SupervisionTarget>,
    pub target_reports: Vec<SupervisionTargetReport>,
    pub trace_events: Vec<SupervisionTraceEvent>,
    pub operator_summary: String,
}

fn max_state(left: HealthState, right: HealthState) -> HealthState {
    match (left, right) {
        (HealthState::Block, _) | (_, HealthState::Block) => HealthState::Block,
        (HealthState::Restrict, _) | (_, HealthState::Restrict) => HealthState::Restrict,
        (HealthState::Warn, _) | (_, HealthState::Warn) => HealthState::Warn,
        _ => HealthState::Green,
    }
}

fn nearing_budget(age_seconds: u64, budget_seconds: u64) -> bool {
    budget_seconds > 0 && age_seconds.saturating_mul(100) >= budget_seconds.saturating_mul(80)
}

fn target_restart_action(target: SupervisionTarget) -> SupervisionAction {
    match target {
        SupervisionTarget::Opsd => SupervisionAction::RestartOpsd,
        SupervisionTarget::Guardian => SupervisionAction::RestartGuardian,
        SupervisionTarget::BrokerGateway => SupervisionAction::RestartBrokerGateway,
    }
}

fn target_prefix(target: SupervisionTarget) -> &'static str {
    match target {
        SupervisionTarget::Opsd => "OPSD",
        SupervisionTarget::Guardian => "GUARDIAN",
        SupervisionTarget::BrokerGateway => "BROKER_GATEWAY",
    }
}

fn render_bundle(bundle: &SupervisionBundle) -> String {
    let mut lines = vec![
        format!("run_id={}", bundle.run_id),
        format!("correlation_id={}", bundle.correlation_id),
        format!("decision_trace_id={}", bundle.decision_trace_id),
        format!("artifact_manifest_id={}", bundle.artifact_manifest_id),
    ];
    for (index, observation) in bundle.observations.iter().enumerate() {
        lines.push(format!(
            "observation[{index}].health_check_id={}",
            observation.health_check_id
        ));
        lines.push(format!(
            "observation[{index}].target={}",
            observation.target.as_str()
        ));
        lines.push(format!(
            "observation[{index}].observed_at_utc={}",
            observation.observed_at_utc
        ));
        lines.push(format!(
            "observation[{index}].liveness={}",
            observation.liveness.as_str()
        ));
        lines.push(format!(
            "observation[{index}].heartbeat_age_seconds={}",
            observation.heartbeat_age_seconds
        ));
        lines.push(format!(
            "observation[{index}].heartbeat_budget_seconds={}",
            observation.heartbeat_budget_seconds
        ));
        lines.push(format!(
            "observation[{index}].prior_restart_attempts={}",
            observation.prior_restart_attempts
        ));
        lines.push(format!(
            "observation[{index}].prior_drill_evidence_id={}",
            observation
                .prior_drill_evidence_id
                .as_deref()
                .unwrap_or("none")
        ));
        lines.push(format!(
            "observation[{index}].recovering_gate_supported={}",
            observation.recovering_gate_supported
        ));
        lines.push(format!(
            "observation[{index}].last_exit_reason={}",
            observation.last_exit_reason
        ));
    }
    lines.join("\n")
}

fn render_target_report(index: usize, report: &SupervisionTargetReport) -> Vec<String> {
    vec![
        format!(
            "target_report[{index}].health_check_id={}",
            report.health_check_id
        ),
        format!("target_report[{index}].target={}", report.target.as_str()),
        format!("target_report[{index}].state={}", report.state.as_str()),
        format!("target_report[{index}].action={}", report.action.as_str()),
        format!("target_report[{index}].reason_code={}", report.reason_code),
        format!(
            "target_report[{index}].failure_category={}",
            report.failure_category
        ),
        format!(
            "target_report[{index}].prior_restart_attempts={}",
            report.prior_restart_attempts
        ),
        format!(
            "target_report[{index}].resulting_restart_attempts={}",
            report.resulting_restart_attempts
        ),
        format!(
            "target_report[{index}].required_recovery_gate_state={}",
            report
                .required_recovery_gate_state
                .as_deref()
                .unwrap_or("none")
        ),
        format!(
            "target_report[{index}].prior_drill_evidence_id={}",
            report.prior_drill_evidence_id.as_deref().unwrap_or("none")
        ),
        format!(
            "target_report[{index}].retained_evidence_id={}",
            report.retained_evidence_id
        ),
        format!(
            "target_report[{index}].operator_summary={}",
            report.operator_summary
        ),
    ]
}

fn render_run_report(report: &SupervisionRunReport) -> String {
    let mut lines = vec![
        format!("run_id={}", report.run_id),
        format!("state={}", report.state.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("correlation_id={}", report.correlation_id),
        format!("decision_trace_id={}", report.decision_trace_id),
        format!("artifact_manifest_id={}", report.artifact_manifest_id),
        format!(
            "restarted_targets={}",
            report
                .restarted_targets
                .iter()
                .map(|target| target.as_str())
                .collect::<Vec<_>>()
                .join(",")
        ),
        format!(
            "quarantined_targets={}",
            report
                .quarantined_targets
                .iter()
                .map(|target| target.as_str())
                .collect::<Vec<_>>()
                .join(",")
        ),
        format!("operator_summary={}", report.operator_summary),
    ];
    for (index, target_report) in report.target_reports.iter().enumerate() {
        lines.extend(render_target_report(index, target_report));
    }
    lines.join("\n")
}

fn render_trace_events(events: &[SupervisionTraceEvent]) -> String {
    let mut lines = Vec::new();
    for event in events {
        lines.push(format!("sequence_number={}", event.sequence_number));
        lines.push(format!("target={}", event.target.as_str()));
        lines.push(format!("event_type={}", event.event_type));
        lines.push(format!("correlation_id={}", event.correlation_id));
        lines.push(format!("decision_trace_id={}", event.decision_trace_id));
        lines.push(format!(
            "artifact_manifest_id={}",
            event.artifact_manifest_id
        ));
        lines.push(format!("reason_code={}", event.reason_code));
        lines.push(format!(
            "action={}",
            event
                .action
                .map(SupervisionAction::as_str)
                .unwrap_or("none")
        ));
        lines.push(format!("high_priority_lane={}", event.high_priority_lane));
    }
    lines.join("\n")
}

fn evaluate_observation(
    bundle: &SupervisionBundle,
    observation: &SupervisionObservation,
) -> (SupervisionTargetReport, SupervisionTraceEvent) {
    let retained_evidence_id = format!(
        "watchdog-supervision-{}-{}",
        bundle.run_id,
        observation.target.as_str()
    );
    let prefix = target_prefix(observation.target);

    let (state, action, reason_code, resulting_restart_attempts, required_recovery_gate_state, event_type, operator_summary) =
        match observation.liveness {
            ProcessLiveness::Healthy if nearing_budget(
                observation.heartbeat_age_seconds,
                observation.heartbeat_budget_seconds,
            ) => (
                HealthState::Warn,
                SupervisionAction::Observe,
                format!("WATCHDOG_{prefix}_HEARTBEAT_AGING"),
                0,
                None,
                "health_warning".to_string(),
                format!(
                    "Watchdog kept {} running but flagged an aging heartbeat at {}/{} seconds; prior drill evidence is {}.",
                    observation.target.as_str(),
                    observation.heartbeat_age_seconds,
                    observation.heartbeat_budget_seconds,
                    observation
                        .prior_drill_evidence_id
                        .as_deref()
                        .unwrap_or("not_recorded")
                ),
            ),
            ProcessLiveness::Healthy => (
                HealthState::Green,
                SupervisionAction::Observe,
                format!("WATCHDOG_{prefix}_HEALTHY"),
                0,
                None,
                "health_green".to_string(),
                format!(
                    "Watchdog observed {} as healthy and kept restart attempts at zero.",
                    observation.target.as_str()
                ),
            ),
            _ if observation.target == SupervisionTarget::Opsd
                && !observation.recovering_gate_supported =>
            {
                (
                    HealthState::Block,
                    SupervisionAction::QuarantineTarget,
                    "WATCHDOG_OPSD_RECOVERING_GATE_REQUIRED".to_string(),
                    observation.prior_restart_attempts,
                    Some(OPSD_RECOVERING_GATE_STATE.to_string()),
                    "supervision_blocked".to_string(),
                    "Watchdog refused to restart opsd because the governed RECOVERING handoff was not available."
                        .to_string(),
                )
            }
            _ if observation.prior_restart_attempts + 1 > MAX_RESTART_ATTEMPTS_BEFORE_QUARANTINE => {
                (
                    HealthState::Block,
                    SupervisionAction::QuarantineTarget,
                    format!("WATCHDOG_{prefix}_RESTART_LOOP_ESCALATED"),
                    observation.prior_restart_attempts + 1,
                    None,
                    "supervision_escalated".to_string(),
                    format!(
                        "Watchdog quarantined {} after {} restart attempts; prior drill evidence is {} and manual recovery is required.",
                        observation.target.as_str(),
                        observation.prior_restart_attempts + 1,
                        observation
                            .prior_drill_evidence_id
                            .as_deref()
                            .unwrap_or("not_recorded")
                    ),
                )
            }
            _ => {
                let action = target_restart_action(observation.target);
                let reason_code = if observation.target == SupervisionTarget::Opsd {
                    "WATCHDOG_OPSD_RESTART_RECOVERING_REQUIRED".to_string()
                } else {
                    format!("WATCHDOG_{prefix}_RESTART_REQUIRED")
                };
                let required_recovery_gate_state = if observation.target == SupervisionTarget::Opsd
                {
                    Some(OPSD_RECOVERING_GATE_STATE.to_string())
                } else {
                    None
                };
                let operator_summary = if observation.target == SupervisionTarget::Opsd {
                    "Watchdog requested an opsd restart and requires the runtime to re-enter RECOVERING before any readiness or tradeability checks may resume."
                        .to_string()
                } else {
                    format!(
                        "Watchdog requested a restart for {} after {}; prior drill evidence is {}.",
                        observation.target.as_str(),
                        observation.last_exit_reason,
                        observation
                            .prior_drill_evidence_id
                            .as_deref()
                            .unwrap_or("not_recorded")
                    )
                };
                (
                    HealthState::Restrict,
                    action,
                    reason_code,
                    observation.prior_restart_attempts + 1,
                    required_recovery_gate_state,
                    "restart_requested".to_string(),
                    operator_summary,
                )
            }
        };

    let report = SupervisionTargetReport {
        health_check_id: observation.health_check_id.clone(),
        target: observation.target,
        state,
        action,
        reason_code: reason_code.clone(),
        failure_category: SUPERVISION_HEALTH_CATEGORY,
        prior_restart_attempts: observation.prior_restart_attempts,
        resulting_restart_attempts,
        required_recovery_gate_state,
        prior_drill_evidence_id: observation.prior_drill_evidence_id.clone(),
        retained_evidence_id: retained_evidence_id.clone(),
        operator_summary,
    };
    let event = SupervisionTraceEvent {
        target: observation.target,
        event_type,
        correlation_id: bundle.correlation_id.clone(),
        decision_trace_id: bundle.decision_trace_id.clone(),
        artifact_manifest_id: bundle.artifact_manifest_id.clone(),
        reason_code,
        action: Some(action),
        high_priority_lane: false,
        sequence_number: 0,
    };
    (report, event)
}

/// Evaluates one correlated supervision bundle and emits watchdog restart decisions.
pub fn evaluate_supervision_bundle(bundle: &SupervisionBundle) -> SupervisionRunReport {
    if bundle.observations.is_empty() {
        return SupervisionRunReport {
            run_id: bundle.run_id.clone(),
            state: HealthState::Block,
            reason_code: "WATCHDOG_SUPERVISION_BUNDLE_EMPTY".to_string(),
            correlation_id: bundle.correlation_id.clone(),
            decision_trace_id: bundle.decision_trace_id.clone(),
            artifact_manifest_id: bundle.artifact_manifest_id.clone(),
            restarted_targets: Vec::new(),
            quarantined_targets: Vec::new(),
            target_reports: Vec::new(),
            trace_events: Vec::new(),
            operator_summary:
                "Watchdog cannot evaluate supervision without at least one target observation."
                    .to_string(),
        };
    }

    let mut target_reports = Vec::new();
    let mut trace_events = Vec::new();
    let mut restarted_targets = Vec::new();
    let mut quarantined_targets = Vec::new();
    let mut overall_state = HealthState::Green;

    for (sequence_number, observation) in bundle.observations.iter().enumerate() {
        let (report, mut event) = evaluate_observation(bundle, observation);
        if matches!(
            report.action,
            SupervisionAction::RestartOpsd
                | SupervisionAction::RestartGuardian
                | SupervisionAction::RestartBrokerGateway
        ) {
            restarted_targets.push(report.target);
        }
        if report.action == SupervisionAction::QuarantineTarget {
            quarantined_targets.push(report.target);
        }
        overall_state = max_state(overall_state, report.state);
        event.sequence_number = sequence_number + 1;
        target_reports.push(report);
        trace_events.push(event);
    }

    let reason_code = if !quarantined_targets.is_empty() {
        "WATCHDOG_SUPERVISION_ESCALATED".to_string()
    } else if restarted_targets.contains(&SupervisionTarget::Opsd) {
        "WATCHDOG_SUPERVISION_RECOVERING_REQUIRED".to_string()
    } else if !restarted_targets.is_empty() {
        "WATCHDOG_SUPERVISION_RESTART_REQUIRED".to_string()
    } else if overall_state == HealthState::Warn {
        "WATCHDOG_SUPERVISION_WARN".to_string()
    } else {
        "WATCHDOG_SUPERVISION_GREEN".to_string()
    };

    let operator_summary = if !quarantined_targets.is_empty() {
        format!(
            "Watchdog quarantined {} after restart-loop escalation and retained correlated supervision evidence.",
            quarantined_targets
                .iter()
                .map(|target| target.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )
    } else if restarted_targets.contains(&SupervisionTarget::Opsd) {
        "Watchdog requested an opsd restart and the runtime must re-enter RECOVERING before it can progress through governed readiness checks."
            .to_string()
    } else if !restarted_targets.is_empty() {
        format!(
            "Watchdog requested restarts for {} and retained correlated supervision evidence for later diagnostics.",
            restarted_targets
                .iter()
                .map(|target| target.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )
    } else if overall_state == HealthState::Warn {
        "Watchdog observed aging health signals but did not restart any target.".to_string()
    } else {
        "Watchdog observed healthy targets and recorded a green supervision snapshot.".to_string()
    };

    SupervisionRunReport {
        run_id: bundle.run_id.clone(),
        state: overall_state,
        reason_code,
        correlation_id: bundle.correlation_id.clone(),
        decision_trace_id: bundle.decision_trace_id.clone(),
        artifact_manifest_id: bundle.artifact_manifest_id.clone(),
        restarted_targets,
        quarantined_targets,
        target_reports,
        trace_events,
        operator_summary,
    }
}

/// Writes the supervision bundle, report, and trace events to the provided directory.
pub fn write_supervision_artifacts(
    root: &Path,
    bundle: &SupervisionBundle,
    report: &SupervisionRunReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(root.join("supervision_bundle.txt"), render_bundle(bundle))?;
    fs::write(
        root.join("supervision_report.txt"),
        render_run_report(report),
    )?;
    fs::write(
        root.join("supervision_trace_events.txt"),
        render_trace_events(&report.trace_events),
    )?;
    Ok(())
}

fn base_bundle() -> SupervisionBundle {
    SupervisionBundle {
        run_id: "watchdog-supervision-run-001".to_string(),
        correlation_id: "watchdog-correlation-001".to_string(),
        decision_trace_id: "watchdog-trace-001".to_string(),
        artifact_manifest_id: "artifact/watchdog-supervision-run-001".to_string(),
        observations: vec![
            SupervisionObservation {
                health_check_id: "opsd-health-001".to_string(),
                target: SupervisionTarget::Opsd,
                observed_at_utc: "2026-03-27T20:45:00+00:00".to_string(),
                liveness: ProcessLiveness::Healthy,
                heartbeat_age_seconds: 8,
                heartbeat_budget_seconds: 60,
                prior_restart_attempts: 0,
                prior_drill_evidence_id: Some("watchdog-supervision-prev-opsd".to_string()),
                recovering_gate_supported: true,
                last_exit_reason: "clean_shutdown".to_string(),
            },
            SupervisionObservation {
                health_check_id: "guardian-health-001".to_string(),
                target: SupervisionTarget::Guardian,
                observed_at_utc: "2026-03-27T20:45:00+00:00".to_string(),
                liveness: ProcessLiveness::Healthy,
                heartbeat_age_seconds: 6,
                heartbeat_budget_seconds: 60,
                prior_restart_attempts: 0,
                prior_drill_evidence_id: Some("watchdog-supervision-prev-guardian".to_string()),
                recovering_gate_supported: true,
                last_exit_reason: "clean_shutdown".to_string(),
            },
            SupervisionObservation {
                health_check_id: "broker-gateway-health-001".to_string(),
                target: SupervisionTarget::BrokerGateway,
                observed_at_utc: "2026-03-27T20:45:00+00:00".to_string(),
                liveness: ProcessLiveness::Healthy,
                heartbeat_age_seconds: 5,
                heartbeat_budget_seconds: 60,
                prior_restart_attempts: 0,
                prior_drill_evidence_id: Some(
                    "watchdog-supervision-prev-broker-gateway".to_string(),
                ),
                recovering_gate_supported: true,
                last_exit_reason: "clean_shutdown".to_string(),
            },
        ],
    }
}

/// Built-in supervision bundles used by tests and executable drills.
pub fn sample_supervision_bundle(name: &str) -> Option<SupervisionBundle> {
    let mut bundle = base_bundle();
    match name {
        "all-green" => Some(bundle),
        "opsd-restart-into-recovering" => {
            bundle.run_id = "watchdog-supervision-run-opsd-restart".to_string();
            bundle.artifact_manifest_id =
                "artifact/watchdog-supervision-run-opsd-restart".to_string();
            bundle.observations[0].liveness = ProcessLiveness::Down;
            bundle.observations[0].heartbeat_age_seconds = 95;
            bundle.observations[0].last_exit_reason =
                "process_exit_without_clean_handoff".to_string();
            Some(bundle)
        }
        "guardian-heartbeat-aging" => {
            bundle.run_id = "watchdog-supervision-run-guardian-aging".to_string();
            bundle.artifact_manifest_id =
                "artifact/watchdog-supervision-run-guardian-aging".to_string();
            bundle.observations[1].heartbeat_age_seconds = 54;
            Some(bundle)
        }
        "broker-gateway-restart-loop" => {
            bundle.run_id = "watchdog-supervision-run-broker-escalation".to_string();
            bundle.artifact_manifest_id =
                "artifact/watchdog-supervision-run-broker-escalation".to_string();
            bundle.observations[2].liveness = ProcessLiveness::Down;
            bundle.observations[2].heartbeat_age_seconds = 144;
            bundle.observations[2].prior_restart_attempts = MAX_RESTART_ATTEMPTS_BEFORE_QUARANTINE;
            bundle.observations[2].last_exit_reason =
                "restart_loop_after_gateway_disconnect".to_string();
            bundle.observations[2].prior_drill_evidence_id =
                Some("watchdog-supervision-run-broker-prior".to_string());
            Some(bundle)
        }
        "opsd-restart-without-recovering-gate" => {
            bundle.run_id = "watchdog-supervision-run-opsd-blocked".to_string();
            bundle.artifact_manifest_id =
                "artifact/watchdog-supervision-run-opsd-blocked".to_string();
            bundle.observations[0].liveness = ProcessLiveness::Down;
            bundle.observations[0].heartbeat_age_seconds = 120;
            bundle.observations[0].recovering_gate_supported = false;
            bundle.observations[0].last_exit_reason =
                "process_exit_without_recovery_gate".to_string();
            Some(bundle)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        evaluate_supervision_bundle, sample_supervision_bundle, HealthState, SupervisionAction,
        SupervisionTarget, MAX_RESTART_ATTEMPTS_BEFORE_QUARANTINE, OPSD_RECOVERING_GATE_STATE,
    };

    #[test]
    fn green_supervision_bundle_requires_no_restart() {
        let bundle = sample_supervision_bundle("all-green").expect("green bundle exists");
        let report = evaluate_supervision_bundle(&bundle);

        assert_eq!(HealthState::Green, report.state);
        assert_eq!("WATCHDOG_SUPERVISION_GREEN", report.reason_code);
        assert!(report.restarted_targets.is_empty());
        assert!(report.quarantined_targets.is_empty());
    }

    #[test]
    fn opsd_restart_requires_recovering_handoff() {
        let bundle = sample_supervision_bundle("opsd-restart-into-recovering")
            .expect("opsd restart bundle exists");
        let report = evaluate_supervision_bundle(&bundle);
        let opsd = report
            .target_reports
            .iter()
            .find(|target_report| target_report.target == SupervisionTarget::Opsd)
            .expect("opsd target report exists");

        assert_eq!(HealthState::Restrict, opsd.state);
        assert_eq!(SupervisionAction::RestartOpsd, opsd.action);
        assert_eq!(
            Some(OPSD_RECOVERING_GATE_STATE.to_string()),
            opsd.required_recovery_gate_state
        );
        assert_eq!(
            "WATCHDOG_SUPERVISION_RECOVERING_REQUIRED",
            report.reason_code
        );
    }

    #[test]
    fn aging_heartbeat_warns_without_restart() {
        let bundle = sample_supervision_bundle("guardian-heartbeat-aging")
            .expect("guardian aging bundle exists");
        let report = evaluate_supervision_bundle(&bundle);
        let guardian = report
            .target_reports
            .iter()
            .find(|target_report| target_report.target == SupervisionTarget::Guardian)
            .expect("guardian target report exists");

        assert_eq!(HealthState::Warn, guardian.state);
        assert_eq!(SupervisionAction::Observe, guardian.action);
        assert_eq!("WATCHDOG_GUARDIAN_HEARTBEAT_AGING", guardian.reason_code);
    }

    #[test]
    fn restart_loop_escalates_to_quarantine() {
        let bundle = sample_supervision_bundle("broker-gateway-restart-loop")
            .expect("broker escalation bundle exists");
        let report = evaluate_supervision_bundle(&bundle);
        let gateway = report
            .target_reports
            .iter()
            .find(|target_report| target_report.target == SupervisionTarget::BrokerGateway)
            .expect("broker gateway target report exists");

        assert_eq!(HealthState::Block, gateway.state);
        assert_eq!(SupervisionAction::QuarantineTarget, gateway.action);
        assert_eq!(
            MAX_RESTART_ATTEMPTS_BEFORE_QUARANTINE + 1,
            gateway.resulting_restart_attempts
        );
        assert_eq!("WATCHDOG_SUPERVISION_ESCALATED", report.reason_code);
    }

    #[test]
    fn opsd_restart_blocks_without_recovering_gate_support() {
        let bundle = sample_supervision_bundle("opsd-restart-without-recovering-gate")
            .expect("blocked opsd bundle exists");
        let report = evaluate_supervision_bundle(&bundle);
        let opsd = report
            .target_reports
            .iter()
            .find(|target_report| target_report.target == SupervisionTarget::Opsd)
            .expect("opsd target report exists");

        assert_eq!(HealthState::Block, opsd.state);
        assert_eq!(SupervisionAction::QuarantineTarget, opsd.action);
        assert_eq!("WATCHDOG_OPSD_RECOVERING_GATE_REQUIRED", opsd.reason_code);
    }
}
