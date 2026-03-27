use std::fs;
use std::path::Path;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RecoveryTrigger {
    ProcessStart,
    BrokerReconnect,
    SupervisedRestart,
    DailyReset,
}

impl RecoveryTrigger {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ProcessStart => "process_start",
            Self::BrokerReconnect => "broker_reconnect",
            Self::SupervisedRestart => "supervised_restart",
            Self::DailyReset => "daily_reset",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReadinessGateStatus {
    Green,
    Blocked,
    Suspect,
    Invalid,
}

impl ReadinessGateStatus {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Green => "green",
            Self::Blocked => "blocked",
            Self::Suspect => "suspect",
            Self::Invalid => "invalid",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NextSessionDisposition {
    Eligible,
    Blocked,
    ReviewRequired,
}

impl NextSessionDisposition {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Eligible => "eligible",
            Self::Blocked => "blocked",
            Self::ReviewRequired => "review_required",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WarmupSource {
    SnapshotSeed,
    JournalReplay,
    FreshHistory,
}

impl WarmupSource {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SnapshotSeed => "snapshot_seed",
            Self::JournalReplay => "journal_replay",
            Self::FreshHistory => "fresh_history",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ShutdownBarrierStatus {
    RestartReady,
    FlattenBeforeShutdown,
    HaltRequired,
    Invalid,
}

impl ShutdownBarrierStatus {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::RestartReady => "restart_ready",
            Self::FlattenBeforeShutdown => "flatten_before_shutdown",
            Self::HaltRequired => "halt_required",
            Self::Invalid => "invalid",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RecoveryStatus {
    ResumeTradeable,
    ResumeExitOnly,
    Recovering,
    Halted,
    Invalid,
}

impl RecoveryStatus {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ResumeTradeable => "resume_tradeable",
            Self::ResumeExitOnly => "resume_exit_only",
            Self::Recovering => "recovering",
            Self::Halted => "halted",
            Self::Invalid => "invalid",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ShutdownBarrierRequest {
    pub shutdown_id: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub triggered_at_utc: String,
    pub snapshot_target_id: String,
    pub journal_barrier_id: String,
    pub snapshot_write_succeeded: bool,
    pub snapshot_digest_verified: bool,
    pub journal_barrier_persisted: bool,
    pub journal_flush_verified: bool,
    pub open_position_contracts: i64,
    pub open_order_count: usize,
    pub restart_while_holding_permitted: bool,
    pub flatten_completed: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ShutdownBarrierArtifact {
    pub shutdown_id: String,
    pub status: ShutdownBarrierStatus,
    pub reason_code: String,
    pub retained_artifact_id: String,
    pub snapshot_target_id: String,
    pub journal_barrier_id: String,
    pub snapshot_barrier_verified: bool,
    pub journal_barrier_verified: bool,
    pub safe_restart_ready: bool,
    pub explanation: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RecoveryRequest {
    pub recovery_id: String,
    pub trigger: RecoveryTrigger,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub occurred_at_utc: String,
    pub shutdown_barrier_id: String,
    pub snapshot_barrier_verified: bool,
    pub journal_barrier_verified: bool,
    pub broker_state_synchronized: bool,
    pub local_state_restored: bool,
    pub snapshot_seed_available: bool,
    pub journal_replay_available: bool,
    pub journal_replay_completed: bool,
    pub fresh_history_available: bool,
    pub readiness_status: ReadinessGateStatus,
    pub readiness_reason_code: String,
    pub next_session_disposition: NextSessionDisposition,
    pub reconciliation_review_required: bool,
    pub warmup_history_bars_required: usize,
    pub warmup_history_bars_observed: usize,
    pub warmup_state_seed_required: bool,
    pub warmup_state_seed_loaded: bool,
    pub open_position_contracts: i64,
    pub open_order_count: usize,
    pub daily_reset_pending: bool,
    pub ambiguity_detected: bool,
    pub ambiguity_reason_code: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RecoveryReport {
    pub recovery_id: String,
    pub status: RecoveryStatus,
    pub reason_code: String,
    pub retained_artifact_id: String,
    pub allow_new_entries: bool,
    pub exit_only: bool,
    pub require_flatten: bool,
    pub selected_warmup_source: Option<WarmupSource>,
    pub blocking_reasons: Vec<String>,
    pub explanation: String,
}

fn render_shutdown_request(request: &ShutdownBarrierRequest) -> String {
    [
        format!("shutdown_id={}", request.shutdown_id),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!("session_id={}", request.session_id),
        format!("triggered_at_utc={}", request.triggered_at_utc),
        format!("snapshot_target_id={}", request.snapshot_target_id),
        format!("journal_barrier_id={}", request.journal_barrier_id),
        format!(
            "snapshot_write_succeeded={}",
            request.snapshot_write_succeeded
        ),
        format!(
            "snapshot_digest_verified={}",
            request.snapshot_digest_verified
        ),
        format!(
            "journal_barrier_persisted={}",
            request.journal_barrier_persisted
        ),
        format!("journal_flush_verified={}", request.journal_flush_verified),
        format!(
            "open_position_contracts={}",
            request.open_position_contracts
        ),
        format!("open_order_count={}", request.open_order_count),
        format!(
            "restart_while_holding_permitted={}",
            request.restart_while_holding_permitted
        ),
        format!("flatten_completed={}", request.flatten_completed),
    ]
    .join("\n")
}

fn render_shutdown_artifact(artifact: &ShutdownBarrierArtifact) -> String {
    [
        format!("shutdown_id={}", artifact.shutdown_id),
        format!("status={}", artifact.status.as_str()),
        format!("reason_code={}", artifact.reason_code),
        format!("retained_artifact_id={}", artifact.retained_artifact_id),
        format!("snapshot_target_id={}", artifact.snapshot_target_id),
        format!("journal_barrier_id={}", artifact.journal_barrier_id),
        format!(
            "snapshot_barrier_verified={}",
            artifact.snapshot_barrier_verified
        ),
        format!(
            "journal_barrier_verified={}",
            artifact.journal_barrier_verified
        ),
        format!("safe_restart_ready={}", artifact.safe_restart_ready),
        format!("explanation={}", artifact.explanation),
    ]
    .join("\n")
}

fn render_recovery_request(request: &RecoveryRequest) -> String {
    [
        format!("recovery_id={}", request.recovery_id),
        format!("trigger={}", request.trigger.as_str()),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!("session_id={}", request.session_id),
        format!("occurred_at_utc={}", request.occurred_at_utc),
        format!("shutdown_barrier_id={}", request.shutdown_barrier_id),
        format!(
            "snapshot_barrier_verified={}",
            request.snapshot_barrier_verified
        ),
        format!(
            "journal_barrier_verified={}",
            request.journal_barrier_verified
        ),
        format!(
            "broker_state_synchronized={}",
            request.broker_state_synchronized
        ),
        format!("local_state_restored={}", request.local_state_restored),
        format!(
            "snapshot_seed_available={}",
            request.snapshot_seed_available
        ),
        format!(
            "journal_replay_available={}",
            request.journal_replay_available
        ),
        format!(
            "journal_replay_completed={}",
            request.journal_replay_completed
        ),
        format!(
            "fresh_history_available={}",
            request.fresh_history_available
        ),
        format!("readiness_status={}", request.readiness_status.as_str()),
        format!("readiness_reason_code={}", request.readiness_reason_code),
        format!(
            "next_session_disposition={}",
            request.next_session_disposition.as_str()
        ),
        format!(
            "reconciliation_review_required={}",
            request.reconciliation_review_required
        ),
        format!(
            "warmup_history_bars_required={}",
            request.warmup_history_bars_required
        ),
        format!(
            "warmup_history_bars_observed={}",
            request.warmup_history_bars_observed
        ),
        format!(
            "warmup_state_seed_required={}",
            request.warmup_state_seed_required
        ),
        format!(
            "warmup_state_seed_loaded={}",
            request.warmup_state_seed_loaded
        ),
        format!(
            "open_position_contracts={}",
            request.open_position_contracts
        ),
        format!("open_order_count={}", request.open_order_count),
        format!("daily_reset_pending={}", request.daily_reset_pending),
        format!("ambiguity_detected={}", request.ambiguity_detected),
        format!(
            "ambiguity_reason_code={}",
            request.ambiguity_reason_code.clone().unwrap_or_default()
        ),
    ]
    .join("\n")
}

fn render_recovery_report(report: &RecoveryReport) -> String {
    [
        format!("recovery_id={}", report.recovery_id),
        format!("status={}", report.status.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("retained_artifact_id={}", report.retained_artifact_id),
        format!("allow_new_entries={}", report.allow_new_entries),
        format!("exit_only={}", report.exit_only),
        format!("require_flatten={}", report.require_flatten),
        format!(
            "selected_warmup_source={}",
            report
                .selected_warmup_source
                .map(WarmupSource::as_str)
                .unwrap_or("")
        ),
        format!("blocking_reasons={}", report.blocking_reasons.join(",")),
        format!("explanation={}", report.explanation),
    ]
    .join("\n")
}

fn invalid_shutdown(
    request: &ShutdownBarrierRequest,
    reason_code: &str,
    explanation: &str,
) -> ShutdownBarrierArtifact {
    ShutdownBarrierArtifact {
        shutdown_id: request.shutdown_id.clone(),
        status: ShutdownBarrierStatus::Invalid,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!(
            "runtime_state/recovery/{}/shutdown_barrier.txt",
            request.shutdown_id
        ),
        snapshot_target_id: request.snapshot_target_id.clone(),
        journal_barrier_id: request.journal_barrier_id.clone(),
        snapshot_barrier_verified: false,
        journal_barrier_verified: false,
        safe_restart_ready: false,
        explanation: explanation.to_string(),
    }
}

fn invalid_recovery(
    request: &RecoveryRequest,
    reason_code: &str,
    explanation: &str,
) -> RecoveryReport {
    RecoveryReport {
        recovery_id: request.recovery_id.clone(),
        status: RecoveryStatus::Invalid,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!(
            "runtime_state/recovery/{}/recovery_report.txt",
            request.recovery_id
        ),
        allow_new_entries: false,
        exit_only: false,
        require_flatten: false,
        selected_warmup_source: None,
        blocking_reasons: vec![reason_code.to_string()],
        explanation: explanation.to_string(),
    }
}

pub fn plan_graceful_shutdown(request: &ShutdownBarrierRequest) -> ShutdownBarrierArtifact {
    if request.shutdown_id.trim().is_empty()
        || request.deployment_instance_id.trim().is_empty()
        || request.session_id.trim().is_empty()
        || request.snapshot_target_id.trim().is_empty()
        || request.journal_barrier_id.trim().is_empty()
        || request.triggered_at_utc.trim().is_empty()
    {
        return invalid_shutdown(
            request,
            "RECOVERY_SHUTDOWN_REQUEST_INVALID",
            "Shutdown barrier planning requires stable ids, timestamps, and target references.",
        );
    }

    let snapshot_barrier_verified =
        request.snapshot_write_succeeded && request.snapshot_digest_verified;
    let journal_barrier_verified =
        request.journal_barrier_persisted && request.journal_flush_verified;
    let holding_state_present =
        request.open_position_contracts != 0 || request.open_order_count > 0;

    let (status, reason_code, safe_restart_ready, explanation) = if !snapshot_barrier_verified
        || !journal_barrier_verified
    {
        (
            ShutdownBarrierStatus::HaltRequired,
            "RECOVERY_SHUTDOWN_BARRIER_INCOMPLETE",
            false,
            "Graceful shutdown did not persist both snapshot and journal barriers, so restart must halt until state-store integrity is repaired.",
        )
    } else if holding_state_present
        && !request.restart_while_holding_permitted
        && !request.flatten_completed
    {
        (
            ShutdownBarrierStatus::FlattenBeforeShutdown,
            "RECOVERY_SHUTDOWN_FLATTEN_REQUIRED",
            false,
            "Open positions or orders remain and restart-while-holding is not approved, so flatten must complete before the shutdown becomes restart-safe.",
        )
    } else {
        (
            ShutdownBarrierStatus::RestartReady,
            "RECOVERY_SHUTDOWN_RESTART_READY",
            true,
            "Snapshot and journal barriers are persisted and the shutdown is ready for verified restart.",
        )
    };

    ShutdownBarrierArtifact {
        shutdown_id: request.shutdown_id.clone(),
        status,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!(
            "runtime_state/recovery/{}/shutdown_barrier.txt",
            request.shutdown_id
        ),
        snapshot_target_id: request.snapshot_target_id.clone(),
        journal_barrier_id: request.journal_barrier_id.clone(),
        snapshot_barrier_verified,
        journal_barrier_verified,
        safe_restart_ready,
        explanation: explanation.to_string(),
    }
}

fn select_warmup_source(request: &RecoveryRequest) -> Option<WarmupSource> {
    if request.snapshot_seed_available && request.local_state_restored {
        Some(WarmupSource::SnapshotSeed)
    } else if request.journal_replay_available && request.journal_replay_completed {
        Some(WarmupSource::JournalReplay)
    } else if request.fresh_history_available {
        Some(WarmupSource::FreshHistory)
    } else {
        None
    }
}

pub fn evaluate_recovery(request: &RecoveryRequest) -> RecoveryReport {
    if request.recovery_id.trim().is_empty()
        || request.deployment_instance_id.trim().is_empty()
        || request.session_id.trim().is_empty()
        || request.occurred_at_utc.trim().is_empty()
        || request.shutdown_barrier_id.trim().is_empty()
        || request.readiness_reason_code.trim().is_empty()
    {
        return invalid_recovery(
            request,
            "RECOVERY_REQUEST_INVALID",
            "Recovery gating requires stable identifiers, timestamps, and readiness provenance.",
        );
    }

    let selected_warmup_source = select_warmup_source(request);
    let warmup_complete = request.warmup_history_bars_observed
        >= request.warmup_history_bars_required
        && (!request.warmup_state_seed_required || request.warmup_state_seed_loaded);
    let holding_state_present =
        request.open_position_contracts != 0 || request.open_order_count > 0;

    let (
        status,
        reason_code,
        allow_new_entries,
        exit_only,
        require_flatten,
        blocking_reasons,
        explanation,
    ) = if request.ambiguity_detected {
        (
            RecoveryStatus::Halted,
            request
                .ambiguity_reason_code
                .clone()
                .unwrap_or_else(|| "RECOVERY_AMBIGUITY_ESCALATION".to_string()),
            false,
            false,
            false,
            vec!["ambiguity_detected".to_string()],
            "Ambiguous broker or local state requires a safe halt instead of speculative recovery.",
        )
    } else if !request.snapshot_barrier_verified || !request.journal_barrier_verified {
        (
            RecoveryStatus::Halted,
            "RECOVERY_BARRIER_VERIFICATION_FAILED".to_string(),
            false,
            false,
            false,
            vec![
                "snapshot_or_journal_barrier_not_verified".to_string(),
                request.shutdown_barrier_id.clone(),
            ],
            "Verified restart requires intact snapshot and journal barriers before runtime activity can resume.",
        )
    } else if !request.broker_state_synchronized {
        (
            RecoveryStatus::Halted,
            "RECOVERY_BROKER_STATE_NOT_SYNCHRONIZED".to_string(),
            false,
            false,
            holding_state_present,
            vec!["broker_state_not_synchronized".to_string()],
            "Recovery cannot proceed while broker state is unsynchronized because restart would rely on unknown live exposure.",
        )
    } else if request.next_session_disposition == NextSessionDisposition::Blocked {
        (
            RecoveryStatus::Halted,
            "RECOVERY_RECONCILIATION_BLOCKED".to_string(),
            false,
            false,
            holding_state_present,
            vec!["next_session_blocked".to_string()],
            "Authoritative reconciliation blocked the next session, so recovery must stay halted.",
        )
    } else if request.daily_reset_pending {
        (
            RecoveryStatus::Recovering,
            "RECOVERY_DAILY_RESET_PENDING".to_string(),
            false,
            holding_state_present,
            false,
            vec!["daily_reset_pending".to_string()],
            "Daily reset boundaries require fresh readiness and recovery evidence before new entries can reopen.",
        )
    } else if matches!(
        request.readiness_status,
        ReadinessGateStatus::Blocked | ReadinessGateStatus::Invalid
    ) {
        (
            RecoveryStatus::Recovering,
            "RECOVERY_READINESS_BLOCKED".to_string(),
            false,
            holding_state_present,
            false,
            vec![
                "readiness_not_green".to_string(),
                request.readiness_reason_code.clone(),
            ],
            "Recovery remains fenced until the latest readiness packet returns green.",
        )
    } else if request.reconciliation_review_required
        || request.next_session_disposition == NextSessionDisposition::ReviewRequired
        || request.readiness_status == ReadinessGateStatus::Suspect
    {
        (
            RecoveryStatus::ResumeExitOnly,
            "RECOVERY_REVIEW_REQUIRED".to_string(),
            false,
            true,
            false,
            vec!["operator_review_required".to_string()],
            "Recovery can only resume in exit-only mode while review-required evidence remains unresolved.",
        )
    } else if !request.local_state_restored {
        (
            RecoveryStatus::Recovering,
            "RECOVERY_LOCAL_STATE_RESTORE_REQUIRED".to_string(),
            false,
            holding_state_present,
            false,
            vec!["local_state_not_restored".to_string()],
            "Recovery remains fenced until local state is restored from the verified snapshot or journal path.",
        )
    } else if selected_warmup_source.is_none() {
        (
            RecoveryStatus::Halted,
            "RECOVERY_WARMUP_SOURCE_UNAVAILABLE".to_string(),
            false,
            false,
            false,
            vec!["warmup_source_unavailable".to_string()],
            "No approved warm-up source is available, so recovery must halt instead of guessing at resumed state.",
        )
    } else if !warmup_complete {
        (
            RecoveryStatus::Recovering,
            "RECOVERY_WARMUP_INCOMPLETE".to_string(),
            false,
            holding_state_present,
            false,
            vec!["warmup_incomplete".to_string()],
            "The runtime has not yet satisfied the required warm-up bars or seed-state conditions for resumed entries.",
        )
    } else if request.trigger == RecoveryTrigger::SupervisedRestart && holding_state_present {
        (
            RecoveryStatus::ResumeExitOnly,
            "RECOVERY_RESTART_WHILE_HOLDING_EXIT_ONLY".to_string(),
            false,
            true,
            false,
            vec!["restart_while_holding".to_string()],
            "A supervised restart while holding exposure resumes in exit-only mode until the operator chooses the next session posture explicitly.",
        )
    } else {
        (
            RecoveryStatus::ResumeTradeable,
            "RECOVERY_RESUME_TRADEABLE".to_string(),
            true,
            false,
            false,
            Vec::new(),
            "Snapshot, journal, readiness, reconciliation, and warm-up gates are satisfied, so tradeable recovery is allowed.",
        )
    };

    RecoveryReport {
        recovery_id: request.recovery_id.clone(),
        status,
        reason_code,
        retained_artifact_id: format!(
            "runtime_state/recovery/{}/recovery_report.txt",
            request.recovery_id
        ),
        allow_new_entries,
        exit_only,
        require_flatten,
        selected_warmup_source,
        blocking_reasons,
        explanation: explanation.to_string(),
    }
}

pub fn write_recovery_artifacts(
    root: &Path,
    shutdown_request: &ShutdownBarrierRequest,
    shutdown_artifact: &ShutdownBarrierArtifact,
    recovery_request: &RecoveryRequest,
    recovery_report: &RecoveryReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("shutdown_barrier_request.txt"),
        render_shutdown_request(shutdown_request),
    )?;
    fs::write(
        root.join("shutdown_barrier_artifact.txt"),
        render_shutdown_artifact(shutdown_artifact),
    )?;
    fs::write(
        root.join("recovery_request.txt"),
        render_recovery_request(recovery_request),
    )?;
    fs::write(
        root.join("recovery_report.txt"),
        render_recovery_report(recovery_report),
    )?;
    Ok(())
}

fn base_shutdown_request() -> ShutdownBarrierRequest {
    ShutdownBarrierRequest {
        shutdown_id: "shutdown-2026-03-27-001".to_string(),
        deployment_instance_id: "deployment_gc_shadow".to_string(),
        session_id: "session_2026_03_18".to_string(),
        triggered_at_utc: "2026-03-27T21:00:00Z".to_string(),
        snapshot_target_id: "runtime_state/snapshots/session_2026_03_18.snapshot".to_string(),
        journal_barrier_id: "runtime_state/journal/barrier_2026_03_27_210000".to_string(),
        snapshot_write_succeeded: true,
        snapshot_digest_verified: true,
        journal_barrier_persisted: true,
        journal_flush_verified: true,
        open_position_contracts: 0,
        open_order_count: 0,
        restart_while_holding_permitted: false,
        flatten_completed: true,
    }
}

fn base_recovery_request() -> RecoveryRequest {
    RecoveryRequest {
        recovery_id: "recovery-2026-03-27-001".to_string(),
        trigger: RecoveryTrigger::ProcessStart,
        deployment_instance_id: "deployment_gc_shadow".to_string(),
        session_id: "session_2026_03_18".to_string(),
        occurred_at_utc: "2026-03-27T21:05:00Z".to_string(),
        shutdown_barrier_id: "runtime_state/journal/barrier_2026_03_27_210000".to_string(),
        snapshot_barrier_verified: true,
        journal_barrier_verified: true,
        broker_state_synchronized: true,
        local_state_restored: true,
        snapshot_seed_available: true,
        journal_replay_available: true,
        journal_replay_completed: true,
        fresh_history_available: true,
        readiness_status: ReadinessGateStatus::Green,
        readiness_reason_code: "READINESS_READY_TO_ACTIVATE".to_string(),
        next_session_disposition: NextSessionDisposition::Eligible,
        reconciliation_review_required: false,
        warmup_history_bars_required: 60,
        warmup_history_bars_observed: 60,
        warmup_state_seed_required: true,
        warmup_state_seed_loaded: true,
        open_position_contracts: 0,
        open_order_count: 0,
        daily_reset_pending: false,
        ambiguity_detected: false,
        ambiguity_reason_code: None,
    }
}

pub fn sample_recovery_scenario(name: &str) -> Option<(ShutdownBarrierRequest, RecoveryRequest)> {
    let mut shutdown = base_shutdown_request();
    let mut recovery = base_recovery_request();

    match name {
        "green-verified-restart" => Some((shutdown, recovery)),
        "warmup-journal-hold" => {
            recovery.recovery_id = "recovery-warmup-hold".to_string();
            recovery.trigger = RecoveryTrigger::BrokerReconnect;
            recovery.local_state_restored = false;
            recovery.snapshot_seed_available = false;
            recovery.journal_replay_available = true;
            recovery.journal_replay_completed = true;
            recovery.warmup_history_bars_observed = 24;
            recovery.warmup_state_seed_loaded = false;
            Some((shutdown, recovery))
        }
        "restart-while-holding-exit-only" => {
            shutdown.shutdown_id = "shutdown-holding".to_string();
            shutdown.open_position_contracts = 1;
            shutdown.restart_while_holding_permitted = true;
            shutdown.flatten_completed = false;
            recovery.recovery_id = "recovery-holding".to_string();
            recovery.trigger = RecoveryTrigger::SupervisedRestart;
            recovery.open_position_contracts = 1;
            recovery.open_order_count = 1;
            Some((shutdown, recovery))
        }
        "daily-reset-readiness-blocked" => {
            recovery.recovery_id = "recovery-daily-reset".to_string();
            recovery.trigger = RecoveryTrigger::DailyReset;
            recovery.daily_reset_pending = true;
            recovery.readiness_status = ReadinessGateStatus::Blocked;
            recovery.readiness_reason_code = "READINESS_PROVIDER_BLOCKED".to_string();
            Some((shutdown, recovery))
        }
        "ambiguous-journal-halt" => {
            recovery.recovery_id = "recovery-ambiguous".to_string();
            recovery.readiness_status = ReadinessGateStatus::Invalid;
            recovery.readiness_reason_code = "READINESS_REQUIRED_PROVIDER_MISSING".to_string();
            recovery.ambiguity_detected = true;
            recovery.ambiguity_reason_code = Some("RECOVERY_AMBIGUITY_JOURNAL_GAP".to_string());
            recovery.local_state_restored = false;
            recovery.journal_replay_completed = false;
            Some((shutdown, recovery))
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        RecoveryStatus, ShutdownBarrierStatus, WarmupSource, evaluate_recovery,
        plan_graceful_shutdown, sample_recovery_scenario,
    };

    #[test]
    fn green_verified_restart_resumes_tradeable() {
        let (shutdown_request, recovery_request) =
            sample_recovery_scenario("green-verified-restart")
                .expect("green scenario should exist");
        let shutdown_artifact = plan_graceful_shutdown(&shutdown_request);
        let report = evaluate_recovery(&recovery_request);

        assert_eq!(
            ShutdownBarrierStatus::RestartReady,
            shutdown_artifact.status
        );
        assert_eq!(RecoveryStatus::ResumeTradeable, report.status);
        assert!(report.allow_new_entries);
        assert_eq!(
            Some(WarmupSource::SnapshotSeed),
            report.selected_warmup_source
        );
    }

    #[test]
    fn warmup_hold_uses_journal_replay_and_keeps_gate_closed() {
        let (_, recovery_request) =
            sample_recovery_scenario("warmup-journal-hold").expect("warmup scenario should exist");
        let report = evaluate_recovery(&recovery_request);

        assert_eq!(RecoveryStatus::Recovering, report.status);
        assert!(!report.allow_new_entries);
        assert_eq!(
            Some(WarmupSource::JournalReplay),
            report.selected_warmup_source
        );
        assert_eq!("RECOVERY_LOCAL_STATE_RESTORE_REQUIRED", report.reason_code);
    }

    #[test]
    fn supervised_restart_while_holding_resumes_exit_only() {
        let (shutdown_request, recovery_request) =
            sample_recovery_scenario("restart-while-holding-exit-only")
                .expect("holding scenario should exist");
        let shutdown_artifact = plan_graceful_shutdown(&shutdown_request);
        let report = evaluate_recovery(&recovery_request);

        assert_eq!(
            ShutdownBarrierStatus::RestartReady,
            shutdown_artifact.status
        );
        assert_eq!(RecoveryStatus::ResumeExitOnly, report.status);
        assert!(report.exit_only);
        assert!(!report.allow_new_entries);
        assert_eq!(
            "RECOVERY_RESTART_WHILE_HOLDING_EXIT_ONLY",
            report.reason_code
        );
    }

    #[test]
    fn ambiguous_state_halts_instead_of_guessing() {
        let (_, recovery_request) = sample_recovery_scenario("ambiguous-journal-halt")
            .expect("ambiguity scenario should exist");
        let report = evaluate_recovery(&recovery_request);

        assert_eq!(RecoveryStatus::Halted, report.status);
        assert_eq!("RECOVERY_AMBIGUITY_JOURNAL_GAP", report.reason_code);
        assert!(!report.allow_new_entries);
    }

    #[test]
    fn incomplete_shutdown_barriers_block_restart_readiness() {
        let (mut shutdown_request, _) = sample_recovery_scenario("green-verified-restart")
            .expect("green scenario should exist");
        shutdown_request.snapshot_digest_verified = false;
        let artifact = plan_graceful_shutdown(&shutdown_request);

        assert_eq!(ShutdownBarrierStatus::HaltRequired, artifact.status);
        assert!(!artifact.safe_restart_ready);
        assert_eq!("RECOVERY_SHUTDOWN_BARRIER_INCOMPLETE", artifact.reason_code);
    }
}
