//! Explicit paper-routing and shadow-live suppression controls.
//!
//! This module stays self-contained so non-economic execution rehearsal rules
//! can be implemented and exercised without coupling to unrelated in-flight
//! runtime wiring.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// Canonical non-economic route modes for runtime execution rehearsals.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RouteMode {
    Paper,
    ShadowLive,
    LiveAdjacentRehearsal,
}

impl RouteMode {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Paper => "paper",
            Self::ShadowLive => "shadow_live",
            Self::LiveAdjacentRehearsal => "live_adjacent_rehearsal",
        }
    }
}

/// Canonical mutation requests evaluated by the route-mode policy.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RouteAction {
    SubmitOrderIntent,
    CancelOpenOrders,
    FlattenPositions,
}

impl RouteAction {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SubmitOrderIntent => "submit_order_intent",
            Self::CancelOpenOrders => "cancel_open_orders",
            Self::FlattenPositions => "flatten_positions",
        }
    }

    const fn increases_risk(self) -> bool {
        matches!(self, Self::SubmitOrderIntent)
    }
}

/// Session state inherited from the compiled schedule and runtime topology.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionState {
    Tradeable,
    ResetBoundary,
    Closed,
}

impl SessionState {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Tradeable => "tradeable",
            Self::ResetBoundary => "reset_boundary",
            Self::Closed => "closed",
        }
    }
}

/// Session-readiness state used before route-mode decisions are allowed.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReadinessState {
    Green,
    Suspect,
    Blocked,
}

impl ReadinessState {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Green => "green",
            Self::Suspect => "suspect",
            Self::Blocked => "blocked",
        }
    }
}

/// Result of one non-economic routing evaluation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RouteOutcome {
    RoutedToPaper,
    Suppressed,
    Blocked,
}

impl RouteOutcome {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::RoutedToPaper => "routed_to_paper",
            Self::Suppressed => "suppressed",
            Self::Blocked => "blocked",
        }
    }
}

/// Full request evaluated by the route-mode contract.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RouteModeRequest {
    pub request_id: String,
    pub correlation_id: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub route_mode: RouteMode,
    pub action: RouteAction,
    pub order_intent_id: String,
    pub session_state: SessionState,
    pub readiness_state: ReadinessState,
    pub risk_allows_new_risk: bool,
    pub paper_adapter_available: bool,
    pub shadow_suppression_sink_available: bool,
    pub live_broker_connected: bool,
    pub duplicate_suppression_detected: bool,
    pub decision_trace_id: String,
    pub operator_reason_bundle_id: String,
    pub expected_timeline_id: String,
    pub actual_timeline_id: String,
    pub policy_input_ids: Vec<String>,
    pub source_artifact_ids: Vec<String>,
}

/// Evidence-bearing routing decision retained for operator diagnostics.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RouteDecisionReport {
    pub request_id: String,
    pub correlation_id: String,
    pub route_mode: RouteMode,
    pub action: RouteAction,
    pub outcome: RouteOutcome,
    pub reason_code: String,
    pub route_target: String,
    pub economic_mutation_permitted: bool,
    pub paper_mutation_recorded: bool,
    pub suppression_recorded: bool,
    pub duplicate_prevented: bool,
    pub retained_artifact_id: String,
    pub retained_artifact_ids: Vec<String>,
    pub proof_bundle: BTreeMap<String, String>,
    pub explanation: String,
}

fn push_unique(target: &mut Vec<String>, value: impl Into<String>) {
    let value = value.into();
    if value.is_empty() || target.iter().any(|current| current == &value) {
        return;
    }
    target.push(value);
}

fn format_list(values: &[String]) -> String {
    values.join(",")
}

fn format_context(values: &BTreeMap<String, String>) -> String {
    values
        .iter()
        .map(|(key, value)| format!("{key}:{value}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn render_request(request: &RouteModeRequest) -> String {
    [
        format!("request_id={}", request.request_id),
        format!("correlation_id={}", request.correlation_id),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!("session_id={}", request.session_id),
        format!("route_mode={}", request.route_mode.as_str()),
        format!("action={}", request.action.as_str()),
        format!("order_intent_id={}", request.order_intent_id),
        format!("session_state={}", request.session_state.as_str()),
        format!("readiness_state={}", request.readiness_state.as_str()),
        format!("risk_allows_new_risk={}", request.risk_allows_new_risk),
        format!(
            "paper_adapter_available={}",
            request.paper_adapter_available
        ),
        format!(
            "shadow_suppression_sink_available={}",
            request.shadow_suppression_sink_available
        ),
        format!("live_broker_connected={}", request.live_broker_connected),
        format!(
            "duplicate_suppression_detected={}",
            request.duplicate_suppression_detected
        ),
        format!("decision_trace_id={}", request.decision_trace_id),
        format!(
            "operator_reason_bundle_id={}",
            request.operator_reason_bundle_id
        ),
        format!("expected_timeline_id={}", request.expected_timeline_id),
        format!("actual_timeline_id={}", request.actual_timeline_id),
        format!(
            "policy_input_ids={}",
            format_list(&request.policy_input_ids)
        ),
        format!(
            "source_artifact_ids={}",
            format_list(&request.source_artifact_ids)
        ),
    ]
    .join("\n")
}

fn render_report(report: &RouteDecisionReport) -> String {
    [
        format!("request_id={}", report.request_id),
        format!("correlation_id={}", report.correlation_id),
        format!("route_mode={}", report.route_mode.as_str()),
        format!("action={}", report.action.as_str()),
        format!("outcome={}", report.outcome.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("route_target={}", report.route_target),
        format!(
            "economic_mutation_permitted={}",
            report.economic_mutation_permitted
        ),
        format!("paper_mutation_recorded={}", report.paper_mutation_recorded),
        format!("suppression_recorded={}", report.suppression_recorded),
        format!("duplicate_prevented={}", report.duplicate_prevented),
        format!("retained_artifact_id={}", report.retained_artifact_id),
        format!(
            "retained_artifact_ids={}",
            format_list(&report.retained_artifact_ids)
        ),
        format!("proof_bundle={}", format_context(&report.proof_bundle)),
        format!("explanation={}", report.explanation),
    ]
    .join("\n")
}

fn render_manifest(request: &RouteModeRequest, report: &RouteDecisionReport) -> String {
    [
        format!("request_id={}", request.request_id),
        format!("route_mode={}", request.route_mode.as_str()),
        format!("action={}", request.action.as_str()),
        format!("outcome={}", report.outcome.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("route_target={}", report.route_target),
        format!(
            "economic_mutation_permitted={}",
            report.economic_mutation_permitted
        ),
        format!("paper_mutation_recorded={}", report.paper_mutation_recorded),
        format!("suppression_recorded={}", report.suppression_recorded),
        format!("duplicate_prevented={}", report.duplicate_prevented),
        format!("artifact_count={}", report.retained_artifact_ids.len()),
        format!(
            "retained_artifact_ids={}",
            format_list(&report.retained_artifact_ids)
        ),
    ]
    .join("\n")
}

fn base_artifact_ids(request: &RouteModeRequest) -> Vec<String> {
    let mut retained = Vec::new();
    for artifact_id in &request.source_artifact_ids {
        push_unique(&mut retained, artifact_id.clone());
    }
    push_unique(&mut retained, request.decision_trace_id.clone());
    push_unique(&mut retained, request.operator_reason_bundle_id.clone());
    push_unique(&mut retained, request.expected_timeline_id.clone());
    push_unique(&mut retained, request.actual_timeline_id.clone());
    for policy_input_id in &request.policy_input_ids {
        push_unique(&mut retained, policy_input_id.clone());
    }
    retained
}

fn build_proof_bundle(
    request: &RouteModeRequest,
    route_target: &str,
    economic_mutation_permitted: bool,
    paper_mutation_recorded: bool,
    suppression_recorded: bool,
    duplicate_prevented: bool,
) -> BTreeMap<String, String> {
    let mut proof_bundle = BTreeMap::new();
    proof_bundle.insert(
        "route_mode".to_string(),
        request.route_mode.as_str().to_string(),
    );
    proof_bundle.insert("action".to_string(), request.action.as_str().to_string());
    proof_bundle.insert(
        "session_state".to_string(),
        request.session_state.as_str().to_string(),
    );
    proof_bundle.insert(
        "readiness_state".to_string(),
        request.readiness_state.as_str().to_string(),
    );
    proof_bundle.insert("route_target".to_string(), route_target.to_string());
    proof_bundle.insert(
        "live_broker_mutation_count".to_string(),
        if economic_mutation_permitted {
            "1"
        } else {
            "0"
        }
        .to_string(),
    );
    proof_bundle.insert(
        "paper_broker_mutation_count".to_string(),
        if paper_mutation_recorded { "1" } else { "0" }.to_string(),
    );
    proof_bundle.insert(
        "suppression_record_count".to_string(),
        if suppression_recorded { "1" } else { "0" }.to_string(),
    );
    proof_bundle.insert(
        "duplicate_prevented".to_string(),
        duplicate_prevented.to_string(),
    );
    proof_bundle.insert(
        "order_intent_id".to_string(),
        request.order_intent_id.clone(),
    );
    proof_bundle
}

#[allow(clippy::too_many_arguments)]
fn report_from_outcome(
    request: &RouteModeRequest,
    outcome: RouteOutcome,
    reason_code: &str,
    route_target: &str,
    economic_mutation_permitted: bool,
    paper_mutation_recorded: bool,
    suppression_recorded: bool,
    duplicate_prevented: bool,
    explanation: &str,
) -> RouteDecisionReport {
    let mut retained_artifact_ids = base_artifact_ids(request);
    let retained_artifact_id = format!("route_mode_report_{}", request.request_id);
    push_unique(&mut retained_artifact_ids, retained_artifact_id.clone());
    push_unique(
        &mut retained_artifact_ids,
        format!("route_mode_manifest_{}", request.request_id),
    );
    if paper_mutation_recorded {
        push_unique(
            &mut retained_artifact_ids,
            format!("paper_route_receipt_{}", request.request_id),
        );
    }
    if suppression_recorded {
        push_unique(
            &mut retained_artifact_ids,
            format!("shadow_suppression_receipt_{}", request.request_id),
        );
    }
    if duplicate_prevented {
        push_unique(
            &mut retained_artifact_ids,
            format!("suppression_dedup_key_{}", request.request_id),
        );
    }
    if matches!(outcome, RouteOutcome::Blocked) {
        push_unique(
            &mut retained_artifact_ids,
            format!("blocked_route_decision_{}", request.request_id),
        );
    }

    RouteDecisionReport {
        request_id: request.request_id.clone(),
        correlation_id: request.correlation_id.clone(),
        route_mode: request.route_mode,
        action: request.action,
        outcome,
        reason_code: reason_code.to_string(),
        route_target: route_target.to_string(),
        economic_mutation_permitted,
        paper_mutation_recorded,
        suppression_recorded,
        duplicate_prevented,
        retained_artifact_id,
        proof_bundle: build_proof_bundle(
            request,
            route_target,
            economic_mutation_permitted,
            paper_mutation_recorded,
            suppression_recorded,
            duplicate_prevented,
        ),
        retained_artifact_ids,
        explanation: explanation.to_string(),
    }
}

/// Evaluates one deterministic non-economic routing decision.
pub fn evaluate_route_mode(request: &RouteModeRequest) -> RouteDecisionReport {
    if request.session_state != SessionState::Tradeable {
        return report_from_outcome(
            request,
            RouteOutcome::Blocked,
            "SESSION_NOT_TRADEABLE_FOR_NON_ECONOMIC_REHEARSAL",
            "none",
            false,
            false,
            false,
            false,
            "The session is not tradeable, so the rehearsal route is blocked before any broker mutation can occur.",
        );
    }

    if request.readiness_state != ReadinessState::Green {
        return report_from_outcome(
            request,
            RouteOutcome::Blocked,
            "READINESS_NOT_GREEN_FOR_NON_ECONOMIC_REHEARSAL",
            "none",
            false,
            false,
            false,
            false,
            "The readiness packet is not green, so the runtime must not rehearse even non-economic execution mutations.",
        );
    }

    if request.action.increases_risk() && !request.risk_allows_new_risk {
        return report_from_outcome(
            request,
            RouteOutcome::Blocked,
            "RISK_GATE_BLOCKS_NEW_REHEARSAL_INTENT",
            "none",
            false,
            false,
            false,
            false,
            "The runtime risk surface rejected new risk, so the rehearsal submit path is blocked.",
        );
    }

    match request.route_mode {
        RouteMode::Paper => {
            if request.paper_adapter_available {
                return report_from_outcome(
                    request,
                    RouteOutcome::RoutedToPaper,
                    "PAPER_ROUTE_EXECUTION_REHEARSAL",
                    "paper_adapter",
                    false,
                    true,
                    false,
                    false,
                    "The runtime rerouted the action into the paper adapter so the live lane can be rehearsed without economic mutation.",
                );
            }
            if request.shadow_suppression_sink_available {
                return report_from_outcome(
                    request,
                    RouteOutcome::Suppressed,
                    "PAPER_ROUTE_FALLBACK_TO_SUPPRESSION",
                    "shadow_suppression_sink",
                    false,
                    false,
                    true,
                    false,
                    "The paper adapter was unavailable, so the runtime fell back to a non-economic suppression sink instead of touching the live broker.",
                );
            }
            report_from_outcome(
                request,
                RouteOutcome::Blocked,
                "NON_ECONOMIC_ROUTE_UNAVAILABLE",
                "none",
                false,
                false,
                false,
                false,
                "Neither the paper adapter nor the suppression sink was available, so the runtime blocked the action.",
            )
        }
        RouteMode::ShadowLive => {
            if !request.live_broker_connected {
                return report_from_outcome(
                    request,
                    RouteOutcome::Blocked,
                    "LIVE_CONNECTIVITY_REQUIRED_FOR_SHADOW_REHEARSAL",
                    "none",
                    false,
                    false,
                    false,
                    false,
                    "Shadow-live rehearsal requires the real live connectivity lane to be present, even though mutations are suppressed.",
                );
            }
            if !request.shadow_suppression_sink_available {
                return report_from_outcome(
                    request,
                    RouteOutcome::Blocked,
                    "SHADOW_SUPPRESSION_SINK_UNAVAILABLE",
                    "none",
                    false,
                    false,
                    false,
                    false,
                    "Shadow-live mode cannot prove non-economic behavior when the suppression sink is unavailable.",
                );
            }
            if request.duplicate_suppression_detected {
                return report_from_outcome(
                    request,
                    RouteOutcome::Suppressed,
                    "SHADOW_LIVE_DUPLICATE_SUPPRESSION_REPLAY",
                    "shadow_suppression_sink",
                    false,
                    false,
                    false,
                    true,
                    "The runtime detected a duplicate suppression key and reused the prior shadow-live evidence instead of recording another mutation.",
                );
            }
            report_from_outcome(
                request,
                RouteOutcome::Suppressed,
                "SHADOW_LIVE_SUPPRESSION_REQUIRED",
                "shadow_suppression_sink",
                false,
                false,
                true,
                false,
                "Shadow-live mode preserved the decision trace while diverting the action into the suppression sink.",
            )
        }
        RouteMode::LiveAdjacentRehearsal => {
            if !request.live_broker_connected {
                return report_from_outcome(
                    request,
                    RouteOutcome::Blocked,
                    "LIVE_CONNECTIVITY_REQUIRED_FOR_REHEARSAL",
                    "none",
                    false,
                    false,
                    false,
                    false,
                    "Live-adjacent rehearsal requires a healthy live connectivity lane before non-economic routing can be trusted.",
                );
            }
            if !request.shadow_suppression_sink_available {
                return report_from_outcome(
                    request,
                    RouteOutcome::Blocked,
                    "REHEARSAL_SUPPRESSION_SINK_UNAVAILABLE",
                    "none",
                    false,
                    false,
                    false,
                    false,
                    "Live-adjacent rehearsal cannot proceed without a suppression sink that proves no live broker mutation occurred.",
                );
            }
            if request.duplicate_suppression_detected {
                return report_from_outcome(
                    request,
                    RouteOutcome::Suppressed,
                    "LIVE_ADJACENT_DUPLICATE_SUPPRESSION_REPLAY",
                    "live_adjacent_suppression_sink",
                    false,
                    false,
                    false,
                    true,
                    "The runtime reused the prior live-adjacent suppression evidence rather than generating a duplicate rehearsal record.",
                );
            }
            report_from_outcome(
                request,
                RouteOutcome::Suppressed,
                "LIVE_ADJACENT_REHEARSAL_SUPPRESSED",
                "live_adjacent_suppression_sink",
                false,
                false,
                true,
                false,
                "The runtime exercised the live-adjacent lane with explicit suppression so no economic mutation reached the broker.",
            )
        }
    }
}

/// Writes retained routing artifacts for one route-mode decision.
pub fn write_route_mode_artifacts(
    root: &Path,
    request: &RouteModeRequest,
    report: &RouteDecisionReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(root.join("route_mode_request.txt"), render_request(request))?;
    fs::write(root.join("route_mode_report.txt"), render_report(report))?;
    fs::write(
        root.join("route_mode_manifest.txt"),
        render_manifest(request, report),
    )?;
    Ok(())
}

fn base_request() -> RouteModeRequest {
    RouteModeRequest {
        request_id: "route-mode-paper-green".to_string(),
        correlation_id: "corr-route-paper-green".to_string(),
        deployment_instance_id: "paper-gold-1".to_string(),
        session_id: "globex_2026_03_18".to_string(),
        route_mode: RouteMode::Paper,
        action: RouteAction::SubmitOrderIntent,
        order_intent_id: "paper-gold-1:77:leg-a:buy:entry".to_string(),
        session_state: SessionState::Tradeable,
        readiness_state: ReadinessState::Green,
        risk_allows_new_risk: true,
        paper_adapter_available: true,
        shadow_suppression_sink_available: true,
        live_broker_connected: true,
        duplicate_suppression_detected: false,
        decision_trace_id: "decision-trace-route-paper-green".to_string(),
        operator_reason_bundle_id: "reason-bundle-route-paper-green".to_string(),
        expected_timeline_id: "expected-timeline-route-paper-green".to_string(),
        actual_timeline_id: "actual-timeline-route-paper-green".to_string(),
        policy_input_ids: vec![
            "session_readiness_packet_green_v1".to_string(),
            "runtime_risk_green_v1".to_string(),
            "paper_shadow_policy_green_v1".to_string(),
        ],
        source_artifact_ids: vec![
            "candidate_bundle_freeze_v1".to_string(),
            "promotion_preflight_v1".to_string(),
        ],
    }
}

/// Returns one deterministic sample request for the smoke harness.
pub fn sample_route_mode_request(name: &str) -> Option<RouteModeRequest> {
    let mut request = base_request();
    match name {
        "paper-route-reroutes-submit" => Some(request),
        "shadow-live-suppresses-submit" => {
            request.request_id = "route-mode-shadow-suppressed".to_string();
            request.correlation_id = "corr-route-shadow-suppressed".to_string();
            request.route_mode = RouteMode::ShadowLive;
            request.paper_adapter_available = false;
            request.operator_reason_bundle_id = "reason-bundle-route-shadow".to_string();
            request.decision_trace_id = "decision-trace-route-shadow".to_string();
            request.expected_timeline_id = "expected-timeline-route-shadow".to_string();
            request.actual_timeline_id = "actual-timeline-route-shadow".to_string();
            Some(request)
        }
        "paper-route-falls-back-to-suppression" => {
            request.request_id = "route-mode-paper-fallback".to_string();
            request.correlation_id = "corr-route-paper-fallback".to_string();
            request.paper_adapter_available = false;
            request.operator_reason_bundle_id = "reason-bundle-route-paper-fallback".to_string();
            request.decision_trace_id = "decision-trace-route-paper-fallback".to_string();
            request.expected_timeline_id = "expected-timeline-route-paper-fallback".to_string();
            request.actual_timeline_id = "actual-timeline-route-paper-fallback".to_string();
            Some(request)
        }
        "shadow-live-duplicate-dedupes" => {
            request.request_id = "route-mode-shadow-duplicate".to_string();
            request.correlation_id = "corr-route-shadow-duplicate".to_string();
            request.route_mode = RouteMode::ShadowLive;
            request.paper_adapter_available = false;
            request.duplicate_suppression_detected = true;
            request.operator_reason_bundle_id = "reason-bundle-route-shadow-duplicate".to_string();
            request.decision_trace_id = "decision-trace-route-shadow-duplicate".to_string();
            request.expected_timeline_id = "expected-timeline-route-shadow-duplicate".to_string();
            request.actual_timeline_id = "actual-timeline-route-shadow-duplicate".to_string();
            Some(request)
        }
        "live-adjacent-readiness-blocked" => {
            request.request_id = "route-mode-live-adjacent-blocked".to_string();
            request.correlation_id = "corr-route-live-adjacent-blocked".to_string();
            request.route_mode = RouteMode::LiveAdjacentRehearsal;
            request.paper_adapter_available = false;
            request.readiness_state = ReadinessState::Suspect;
            request.operator_reason_bundle_id = "reason-bundle-route-live-adjacent".to_string();
            request.decision_trace_id = "decision-trace-route-live-adjacent".to_string();
            request.expected_timeline_id = "expected-timeline-route-live-adjacent".to_string();
            request.actual_timeline_id = "actual-timeline-route-live-adjacent".to_string();
            Some(request)
        }
        "shadow-live-cancel-suppressed" => {
            request.request_id = "route-mode-shadow-cancel".to_string();
            request.correlation_id = "corr-route-shadow-cancel".to_string();
            request.route_mode = RouteMode::ShadowLive;
            request.action = RouteAction::CancelOpenOrders;
            request.paper_adapter_available = false;
            request.operator_reason_bundle_id = "reason-bundle-route-shadow-cancel".to_string();
            request.decision_trace_id = "decision-trace-route-shadow-cancel".to_string();
            request.expected_timeline_id = "expected-timeline-route-shadow-cancel".to_string();
            request.actual_timeline_id = "actual-timeline-route-shadow-cancel".to_string();
            Some(request)
        }
        "paper-route-flatten-rerouted" => {
            request.request_id = "route-mode-paper-flatten".to_string();
            request.correlation_id = "corr-route-paper-flatten".to_string();
            request.action = RouteAction::FlattenPositions;
            request.operator_reason_bundle_id = "reason-bundle-route-paper-flatten".to_string();
            request.decision_trace_id = "decision-trace-route-paper-flatten".to_string();
            request.expected_timeline_id = "expected-timeline-route-paper-flatten".to_string();
            request.actual_timeline_id = "actual-timeline-route-paper-flatten".to_string();
            Some(request)
        }
        "paper-route-reset-boundary-blocked" => {
            request.request_id = "route-mode-reset-boundary".to_string();
            request.correlation_id = "corr-route-reset-boundary".to_string();
            request.session_state = SessionState::ResetBoundary;
            request.operator_reason_bundle_id = "reason-bundle-route-reset-boundary".to_string();
            request.decision_trace_id = "decision-trace-route-reset-boundary".to_string();
            request.expected_timeline_id = "expected-timeline-route-reset-boundary".to_string();
            request.actual_timeline_id = "actual-timeline-route-reset-boundary".to_string();
            Some(request)
        }
        "paper-route-closed-session-blocked" => {
            request.request_id = "route-mode-closed-session".to_string();
            request.correlation_id = "corr-route-closed-session".to_string();
            request.session_state = SessionState::Closed;
            request.operator_reason_bundle_id = "reason-bundle-route-closed-session".to_string();
            request.decision_trace_id = "decision-trace-route-closed-session".to_string();
            request.expected_timeline_id = "expected-timeline-route-closed-session".to_string();
            request.actual_timeline_id = "actual-timeline-route-closed-session".to_string();
            Some(request)
        }
        "paper-route-blocked-readiness-blocked" => {
            request.request_id = "route-mode-blocked-readiness".to_string();
            request.correlation_id = "corr-route-blocked-readiness".to_string();
            request.readiness_state = ReadinessState::Blocked;
            request.operator_reason_bundle_id = "reason-bundle-route-blocked-readiness".to_string();
            request.decision_trace_id = "decision-trace-route-blocked-readiness".to_string();
            request.expected_timeline_id = "expected-timeline-route-blocked-readiness".to_string();
            request.actual_timeline_id = "actual-timeline-route-blocked-readiness".to_string();
            Some(request)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};

    use super::{
        evaluate_route_mode, sample_route_mode_request, write_route_mode_artifacts, ReadinessState,
        RouteAction, RouteMode, RouteOutcome, SessionState,
    };

    fn safe_tmp_root() -> PathBuf {
        let shm_root = Path::new("/dev/shm");
        if shm_root.exists() {
            shm_root.join("backtesting_engine_route_mode_artifacts")
        } else {
            std::env::temp_dir().join("backtesting_engine_route_mode_artifacts")
        }
    }

    #[test]
    fn paper_mode_reroutes_to_paper_adapter() {
        let request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        let report = evaluate_route_mode(&request);

        assert_eq!(RouteMode::Paper, report.route_mode);
        assert_eq!(RouteOutcome::RoutedToPaper, report.outcome);
        assert_eq!("PAPER_ROUTE_EXECUTION_REHEARSAL", report.reason_code);
        assert_eq!("paper_adapter", report.route_target);
        assert!(!report.economic_mutation_permitted);
        assert!(report.paper_mutation_recorded);
        assert!(!report.suppression_recorded);
        assert!(report
            .retained_artifact_ids
            .contains(&"paper_route_receipt_route-mode-paper-green".to_string()));
    }

    #[test]
    fn shadow_live_mode_suppresses_mutation() {
        let request =
            sample_route_mode_request("shadow-live-suppresses-submit").expect("scenario exists");
        let report = evaluate_route_mode(&request);

        assert_eq!(RouteMode::ShadowLive, report.route_mode);
        assert_eq!(RouteOutcome::Suppressed, report.outcome);
        assert_eq!("SHADOW_LIVE_SUPPRESSION_REQUIRED", report.reason_code);
        assert_eq!("shadow_suppression_sink", report.route_target);
        assert!(!report.economic_mutation_permitted);
        assert!(!report.paper_mutation_recorded);
        assert!(report.suppression_recorded);
        assert!(!report.duplicate_prevented);
    }

    #[test]
    fn paper_mode_falls_back_to_suppression() {
        let request = sample_route_mode_request("paper-route-falls-back-to-suppression")
            .expect("scenario exists");
        let report = evaluate_route_mode(&request);

        assert_eq!(RouteOutcome::Suppressed, report.outcome);
        assert_eq!("PAPER_ROUTE_FALLBACK_TO_SUPPRESSION", report.reason_code);
        assert_eq!("shadow_suppression_sink", report.route_target);
        assert!(!report.paper_mutation_recorded);
        assert!(report.suppression_recorded);
    }

    #[test]
    fn duplicate_shadow_suppression_reuses_existing_record() {
        let request =
            sample_route_mode_request("shadow-live-duplicate-dedupes").expect("scenario exists");
        let report = evaluate_route_mode(&request);

        assert_eq!(RouteOutcome::Suppressed, report.outcome);
        assert_eq!(
            "SHADOW_LIVE_DUPLICATE_SUPPRESSION_REPLAY",
            report.reason_code
        );
        assert!(report.duplicate_prevented);
        assert!(!report.suppression_recorded);
        assert!(report
            .retained_artifact_ids
            .contains(&"suppression_dedup_key_route-mode-shadow-duplicate".to_string()));
    }

    #[test]
    fn live_adjacent_rehearsal_blocks_when_readiness_is_not_green() {
        let request =
            sample_route_mode_request("live-adjacent-readiness-blocked").expect("scenario exists");
        let report = evaluate_route_mode(&request);

        assert_eq!(RouteOutcome::Blocked, report.outcome);
        assert_eq!(
            "READINESS_NOT_GREEN_FOR_NON_ECONOMIC_REHEARSAL",
            report.reason_code
        );
        assert_eq!("none", report.route_target);
        assert_eq!(ReadinessState::Suspect, request.readiness_state);
        assert_eq!(SessionState::Tradeable, request.session_state);
    }

    #[test]
    fn non_submit_actions_can_use_non_economic_routes() {
        let mut cancel_request =
            sample_route_mode_request("shadow-live-suppresses-submit").expect("scenario exists");
        cancel_request.action = RouteAction::CancelOpenOrders;
        let cancel_report = evaluate_route_mode(&cancel_request);
        assert_eq!(RouteOutcome::Suppressed, cancel_report.outcome);

        let mut flatten_request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        flatten_request.action = RouteAction::FlattenPositions;
        let flatten_report = evaluate_route_mode(&flatten_request);
        assert_eq!(RouteOutcome::RoutedToPaper, flatten_report.outcome);
    }

    #[test]
    fn reset_boundary_closed_and_blocked_readiness_states_all_block_rehearsal() {
        let mut reset_boundary_request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        reset_boundary_request.session_state = SessionState::ResetBoundary;
        let reset_boundary_report = evaluate_route_mode(&reset_boundary_request);
        assert_eq!(RouteOutcome::Blocked, reset_boundary_report.outcome);
        assert_eq!(
            "SESSION_NOT_TRADEABLE_FOR_NON_ECONOMIC_REHEARSAL",
            reset_boundary_report.reason_code
        );

        let mut closed_request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        closed_request.session_state = SessionState::Closed;
        let closed_report = evaluate_route_mode(&closed_request);
        assert_eq!(RouteOutcome::Blocked, closed_report.outcome);
        assert_eq!(
            "SESSION_NOT_TRADEABLE_FOR_NON_ECONOMIC_REHEARSAL",
            closed_report.reason_code
        );

        let mut blocked_readiness_request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        blocked_readiness_request.readiness_state = ReadinessState::Blocked;
        let blocked_readiness_report = evaluate_route_mode(&blocked_readiness_request);
        assert_eq!(RouteOutcome::Blocked, blocked_readiness_report.outcome);
        assert_eq!(
            "READINESS_NOT_GREEN_FOR_NON_ECONOMIC_REHEARSAL",
            blocked_readiness_report.reason_code
        );
    }

    #[test]
    fn artifact_writer_emits_request_report_and_manifest() {
        let request =
            sample_route_mode_request("paper-route-reroutes-submit").expect("scenario exists");
        let report = evaluate_route_mode(&request);
        let artifact_root = safe_tmp_root();
        write_route_mode_artifacts(&artifact_root, &request, &report)
            .expect("route-mode artifacts should write");

        assert!(artifact_root.join("route_mode_request.txt").exists());
        assert!(artifact_root.join("route_mode_report.txt").exists());
        assert!(artifact_root.join("route_mode_manifest.txt").exists());
    }
}
