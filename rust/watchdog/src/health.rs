//! Activation-lane health providers for clock discipline and secrets.
//!
//! These providers emit machine-readable evidence that later readiness and
//! activation surfaces can consume without re-deriving operational health from
//! ad-hoc booleans.

use std::fs;
use std::path::Path;

/// Observability category for clock-discipline health.
pub const CLOCK_HEALTH_CATEGORY: &str = "clock_synchronization_health";
/// Observability category for secret and break-glass health.
pub const SECRET_HEALTH_CATEGORY: &str = "secret_rotation_age_and_break_glass";
/// Observability category for backup freshness and restore drills.
pub const RECOVERY_HEALTH_CATEGORY: &str = "backup_freshness_journal_digest_and_restore_drill";

/// Shared health-state ladder used by providers and aggregate preflight reports.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum HealthState {
    Green,
    Warn,
    Restrict,
    Block,
}

impl HealthState {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Green => "green",
            Self::Warn => "warn",
            Self::Restrict => "restrict",
            Self::Block => "block",
        }
    }

    fn severity_rank(self) -> u8 {
        match self {
            Self::Green => 0,
            Self::Warn => 1,
            Self::Restrict => 2,
            Self::Block => 3,
        }
    }
}

/// Synchronization state carried by the clock-health provider.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ClockSyncState {
    Synced,
    Unknown,
}

impl ClockSyncState {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Synced => "synced",
            Self::Unknown => "unknown",
        }
    }
}

/// Controlled secret-delivery surfaces for the operational runtime.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SecretDeliverySurface {
    RuntimeSecretPath,
    RootOnlyEncryptedFile,
    SecretService,
    Manifest,
    SourceCode,
    Log,
    SystemdUnitFile,
}

impl SecretDeliverySurface {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::RuntimeSecretPath => "runtime_secret_path",
            Self::RootOnlyEncryptedFile => "root_only_encrypted_file",
            Self::SecretService => "secret_service",
            Self::Manifest => "manifest",
            Self::SourceCode => "source_code",
            Self::Log => "log",
            Self::SystemdUnitFile => "systemd_unit_file",
        }
    }

    fn embedded(self) -> bool {
        matches!(
            self,
            Self::Manifest | Self::SourceCode | Self::Log | Self::SystemdUnitFile
        )
    }

    fn requires_root_only_permissions(self) -> bool {
        matches!(self, Self::RootOnlyEncryptedFile)
    }
}

/// Machine-readable clock-health observation captured by watchdog.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ClockHealthObservation {
    pub check_id: String,
    pub session_id: String,
    pub measured_at_utc: String,
    pub session_boundary_resolved_at_utc: String,
    pub measurement_age_minutes: u64,
    pub max_measurement_age_minutes: u64,
    pub measured_skew_ms: i64,
    pub warn_threshold_ms: u64,
    pub restrict_threshold_ms: u64,
    pub block_threshold_ms: u64,
    pub synchronization_state: ClockSyncState,
}

/// Inspectable clock-health provider report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ClockHealthReport {
    pub check_id: String,
    pub session_id: String,
    pub state: HealthState,
    pub reason_code: String,
    pub failure_category: &'static str,
    pub measured_skew_ms: i64,
    pub configured_threshold_ms: u64,
    pub synchronization_state: ClockSyncState,
    pub measured_at_utc: String,
    pub session_boundary_resolved_at_utc: String,
    pub operator_summary: String,
}

/// Machine-readable secret-health observation captured by watchdog.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SecretHealthObservation {
    pub check_id: String,
    pub credential_ref: String,
    pub observed_at_utc: String,
    pub evidence_age_minutes: u64,
    pub max_evidence_age_minutes: u64,
    pub secret_type: String,
    pub delivery_surface: SecretDeliverySurface,
    pub credential_domain_growth: bool,
    pub root_only_permissions: bool,
    pub rotation_age_days: u32,
    pub max_rotation_age_days: u32,
    pub break_glass_accessed: bool,
    pub break_glass_reviewed_before_next_live: bool,
}

/// Inspectable secret-health provider report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SecretHealthReport {
    pub check_id: String,
    pub credential_ref: String,
    pub state: HealthState,
    pub reason_code: String,
    pub failure_category: &'static str,
    pub secret_type: String,
    pub delivery_surface: SecretDeliverySurface,
    pub rotation_age_days: u32,
    pub max_rotation_age_days: u32,
    pub break_glass_accessed: bool,
    pub observed_at_utc: String,
    pub operator_summary: String,
}

/// Backup freshness input consumed by the activation summary.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BackupFreshnessObservation {
    pub check_id: String,
    pub backup_artifact_id: String,
    pub observed_at_utc: String,
    pub age_minutes: u64,
    pub freshness_budget_minutes: u64,
    pub off_host_recoverable: bool,
}

/// Backup freshness report suitable for activation preflight.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BackupFreshnessReport {
    pub check_id: String,
    pub backup_artifact_id: String,
    pub state: HealthState,
    pub reason_code: String,
    pub failure_category: &'static str,
    pub age_minutes: u64,
    pub freshness_budget_minutes: u64,
    pub observed_at_utc: String,
    pub operator_summary: String,
}

/// Restore-drill input consumed by the activation summary.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RestoreDrillObservation {
    pub check_id: String,
    pub restore_drill_id: String,
    pub observed_at_utc: String,
    pub age_minutes: u64,
    pub staleness_budget_minutes: u64,
    pub digest_chain_verified: bool,
    pub off_host_recoverable: bool,
    pub dashboard_visible: bool,
}

/// Restore-drill report suitable for activation preflight.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RestoreDrillReport {
    pub check_id: String,
    pub restore_drill_id: String,
    pub state: HealthState,
    pub reason_code: String,
    pub failure_category: &'static str,
    pub age_minutes: u64,
    pub staleness_budget_minutes: u64,
    pub observed_at_utc: String,
    pub operator_summary: String,
}

/// Aggregate activation-lane health summary carrying the exact preflight check ids.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ActivationPreflightSummary {
    pub summary_id: String,
    pub state: HealthState,
    pub reason_code: String,
    pub clock_health_check_id: String,
    pub secret_health_check_id: String,
    pub backup_freshness_check_id: String,
    pub restore_drill_check_id: String,
    pub failed_check_ids: Vec<String>,
    pub warning_check_ids: Vec<String>,
    pub failure_categories: Vec<&'static str>,
    pub operator_summary: String,
}

fn max_state(left: HealthState, right: HealthState) -> HealthState {
    if left.severity_rank() >= right.severity_rank() {
        left
    } else {
        right
    }
}

fn nearing_budget(current: u64, budget: u64) -> bool {
    budget > 0 && current.saturating_mul(100) >= budget.saturating_mul(80)
}

fn render_clock_health_observation(observation: &ClockHealthObservation) -> String {
    [
        format!("check_id={}", observation.check_id),
        format!("session_id={}", observation.session_id),
        format!("measured_at_utc={}", observation.measured_at_utc),
        format!(
            "session_boundary_resolved_at_utc={}",
            observation.session_boundary_resolved_at_utc
        ),
        format!(
            "measurement_age_minutes={}",
            observation.measurement_age_minutes
        ),
        format!(
            "max_measurement_age_minutes={}",
            observation.max_measurement_age_minutes
        ),
        format!("measured_skew_ms={}", observation.measured_skew_ms),
        format!("warn_threshold_ms={}", observation.warn_threshold_ms),
        format!(
            "restrict_threshold_ms={}",
            observation.restrict_threshold_ms
        ),
        format!("block_threshold_ms={}", observation.block_threshold_ms),
        format!(
            "synchronization_state={}",
            observation.synchronization_state.as_str()
        ),
    ]
    .join("\n")
}

fn render_clock_health_report(report: &ClockHealthReport) -> String {
    [
        format!("check_id={}", report.check_id),
        format!("session_id={}", report.session_id),
        format!("state={}", report.state.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("failure_category={}", report.failure_category),
        format!("measured_skew_ms={}", report.measured_skew_ms),
        format!("configured_threshold_ms={}", report.configured_threshold_ms),
        format!(
            "synchronization_state={}",
            report.synchronization_state.as_str()
        ),
        format!("measured_at_utc={}", report.measured_at_utc),
        format!(
            "session_boundary_resolved_at_utc={}",
            report.session_boundary_resolved_at_utc
        ),
        format!("operator_summary={}", report.operator_summary),
    ]
    .join("\n")
}

fn render_secret_health_observation(observation: &SecretHealthObservation) -> String {
    [
        format!("check_id={}", observation.check_id),
        format!("credential_ref={}", observation.credential_ref),
        format!("observed_at_utc={}", observation.observed_at_utc),
        format!("evidence_age_minutes={}", observation.evidence_age_minutes),
        format!(
            "max_evidence_age_minutes={}",
            observation.max_evidence_age_minutes
        ),
        format!("secret_type={}", observation.secret_type),
        format!("delivery_surface={}", observation.delivery_surface.as_str()),
        format!(
            "credential_domain_growth={}",
            observation.credential_domain_growth
        ),
        format!(
            "root_only_permissions={}",
            observation.root_only_permissions
        ),
        format!("rotation_age_days={}", observation.rotation_age_days),
        format!(
            "max_rotation_age_days={}",
            observation.max_rotation_age_days
        ),
        format!("break_glass_accessed={}", observation.break_glass_accessed),
        format!(
            "break_glass_reviewed_before_next_live={}",
            observation.break_glass_reviewed_before_next_live
        ),
    ]
    .join("\n")
}

fn render_secret_health_report(report: &SecretHealthReport) -> String {
    [
        format!("check_id={}", report.check_id),
        format!("credential_ref={}", report.credential_ref),
        format!("state={}", report.state.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("failure_category={}", report.failure_category),
        format!("secret_type={}", report.secret_type),
        format!("delivery_surface={}", report.delivery_surface.as_str()),
        format!("rotation_age_days={}", report.rotation_age_days),
        format!("max_rotation_age_days={}", report.max_rotation_age_days),
        format!("break_glass_accessed={}", report.break_glass_accessed),
        format!("observed_at_utc={}", report.observed_at_utc),
        format!("operator_summary={}", report.operator_summary),
    ]
    .join("\n")
}

fn render_backup_freshness_report(report: &BackupFreshnessReport) -> String {
    [
        format!("check_id={}", report.check_id),
        format!("backup_artifact_id={}", report.backup_artifact_id),
        format!("state={}", report.state.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("failure_category={}", report.failure_category),
        format!("age_minutes={}", report.age_minutes),
        format!(
            "freshness_budget_minutes={}",
            report.freshness_budget_minutes
        ),
        format!("observed_at_utc={}", report.observed_at_utc),
        format!("operator_summary={}", report.operator_summary),
    ]
    .join("\n")
}

fn render_restore_drill_report(report: &RestoreDrillReport) -> String {
    [
        format!("check_id={}", report.check_id),
        format!("restore_drill_id={}", report.restore_drill_id),
        format!("state={}", report.state.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("failure_category={}", report.failure_category),
        format!("age_minutes={}", report.age_minutes),
        format!(
            "staleness_budget_minutes={}",
            report.staleness_budget_minutes
        ),
        format!("observed_at_utc={}", report.observed_at_utc),
        format!("operator_summary={}", report.operator_summary),
    ]
    .join("\n")
}

fn render_activation_preflight_summary(summary: &ActivationPreflightSummary) -> String {
    let mut lines = vec![
        format!("summary_id={}", summary.summary_id),
        format!("state={}", summary.state.as_str()),
        format!("reason_code={}", summary.reason_code),
        format!("clock_health_check_id={}", summary.clock_health_check_id),
        format!("secret_health_check_id={}", summary.secret_health_check_id),
        format!(
            "backup_freshness_check_id={}",
            summary.backup_freshness_check_id
        ),
        format!("restore_drill_check_id={}", summary.restore_drill_check_id),
        format!("operator_summary={}", summary.operator_summary),
    ];
    if !summary.failed_check_ids.is_empty() {
        lines.push(format!(
            "failed_check_ids={}",
            summary.failed_check_ids.join(",")
        ));
    }
    if !summary.warning_check_ids.is_empty() {
        lines.push(format!(
            "warning_check_ids={}",
            summary.warning_check_ids.join(",")
        ));
    }
    if !summary.failure_categories.is_empty() {
        lines.push(format!(
            "failure_categories={}",
            summary.failure_categories.join(",")
        ));
    }
    lines.join("\n")
}

/// Writes clock-health artifacts to the provided directory.
pub fn write_clock_health_artifacts(
    root: &Path,
    observation: &ClockHealthObservation,
    report: &ClockHealthReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("clock_health_observation.txt"),
        render_clock_health_observation(observation),
    )?;
    fs::write(
        root.join("clock_health_report.txt"),
        render_clock_health_report(report),
    )?;
    Ok(())
}

/// Writes secret-health artifacts to the provided directory.
pub fn write_secret_health_artifacts(
    root: &Path,
    observation: &SecretHealthObservation,
    report: &SecretHealthReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("secret_health_observation.txt"),
        render_secret_health_observation(observation),
    )?;
    fs::write(
        root.join("secret_health_report.txt"),
        render_secret_health_report(report),
    )?;
    Ok(())
}

/// Writes activation-preflight artifacts to the provided directory.
pub fn write_activation_preflight_artifacts(
    root: &Path,
    clock_report: &ClockHealthReport,
    secret_report: &SecretHealthReport,
    backup_report: &BackupFreshnessReport,
    restore_report: &RestoreDrillReport,
    summary: &ActivationPreflightSummary,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("clock_health_report.txt"),
        render_clock_health_report(clock_report),
    )?;
    fs::write(
        root.join("secret_health_report.txt"),
        render_secret_health_report(secret_report),
    )?;
    fs::write(
        root.join("backup_freshness_report.txt"),
        render_backup_freshness_report(backup_report),
    )?;
    fs::write(
        root.join("restore_drill_report.txt"),
        render_restore_drill_report(restore_report),
    )?;
    fs::write(
        root.join("activation_preflight_summary.txt"),
        render_activation_preflight_summary(summary),
    )?;
    Ok(())
}

/// Evaluates clock-discipline health for readiness and activation flows.
pub fn evaluate_clock_health(observation: &ClockHealthObservation) -> ClockHealthReport {
    if observation.measurement_age_minutes > observation.max_measurement_age_minutes {
        return ClockHealthReport {
            check_id: observation.check_id.clone(),
            session_id: observation.session_id.clone(),
            state: HealthState::Block,
            reason_code: "CLOCK_HEALTH_EVIDENCE_STALE".to_string(),
            failure_category: CLOCK_HEALTH_CATEGORY,
            measured_skew_ms: observation.measured_skew_ms,
            configured_threshold_ms: observation.block_threshold_ms,
            synchronization_state: observation.synchronization_state,
            measured_at_utc: observation.measured_at_utc.clone(),
            session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
            operator_summary:
                "Clock-health evidence is stale, so activation cannot trust the current host clock."
                    .to_string(),
        };
    }

    if observation.synchronization_state == ClockSyncState::Unknown {
        return ClockHealthReport {
            check_id: observation.check_id.clone(),
            session_id: observation.session_id.clone(),
            state: HealthState::Block,
            reason_code: "CLOCK_SYNC_STATE_UNKNOWN".to_string(),
            failure_category: CLOCK_HEALTH_CATEGORY,
            measured_skew_ms: observation.measured_skew_ms,
            configured_threshold_ms: observation.block_threshold_ms,
            synchronization_state: observation.synchronization_state,
            measured_at_utc: observation.measured_at_utc.clone(),
            session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
            operator_summary:
                "Synchronization state is unknown, so activation must block until clock trust is re-established."
                    .to_string(),
        };
    }

    let absolute_skew = observation.measured_skew_ms.unsigned_abs();
    if absolute_skew >= observation.block_threshold_ms {
        return ClockHealthReport {
            check_id: observation.check_id.clone(),
            session_id: observation.session_id.clone(),
            state: HealthState::Block,
            reason_code: "CLOCK_SKEW_BLOCK_THRESHOLD".to_string(),
            failure_category: CLOCK_HEALTH_CATEGORY,
            measured_skew_ms: observation.measured_skew_ms,
            configured_threshold_ms: observation.block_threshold_ms,
            synchronization_state: observation.synchronization_state,
            measured_at_utc: observation.measured_at_utc.clone(),
            session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
            operator_summary:
                "Measured skew exceeds the block threshold, so activation and readiness must stop."
                    .to_string(),
        };
    }

    if absolute_skew >= observation.restrict_threshold_ms {
        return ClockHealthReport {
            check_id: observation.check_id.clone(),
            session_id: observation.session_id.clone(),
            state: HealthState::Restrict,
            reason_code: "CLOCK_SKEW_RESTRICT_THRESHOLD".to_string(),
            failure_category: CLOCK_HEALTH_CATEGORY,
            measured_skew_ms: observation.measured_skew_ms,
            configured_threshold_ms: observation.restrict_threshold_ms,
            synchronization_state: observation.synchronization_state,
            measured_at_utc: observation.measured_at_utc.clone(),
            session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
            operator_summary:
                "Measured skew exceeds the restrict threshold, so the host stays in a restricted activation posture."
                    .to_string(),
        };
    }

    if absolute_skew >= observation.warn_threshold_ms {
        return ClockHealthReport {
            check_id: observation.check_id.clone(),
            session_id: observation.session_id.clone(),
            state: HealthState::Warn,
            reason_code: "CLOCK_SKEW_WARN_THRESHOLD".to_string(),
            failure_category: CLOCK_HEALTH_CATEGORY,
            measured_skew_ms: observation.measured_skew_ms,
            configured_threshold_ms: observation.warn_threshold_ms,
            synchronization_state: observation.synchronization_state,
            measured_at_utc: observation.measured_at_utc.clone(),
            session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
            operator_summary:
                "Measured skew exceeds the warn threshold and should be investigated before live activation."
                    .to_string(),
        };
    }

    ClockHealthReport {
        check_id: observation.check_id.clone(),
        session_id: observation.session_id.clone(),
        state: HealthState::Green,
        reason_code: "CLOCK_SKEW_WITHIN_POLICY".to_string(),
        failure_category: CLOCK_HEALTH_CATEGORY,
        measured_skew_ms: observation.measured_skew_ms,
        configured_threshold_ms: observation.warn_threshold_ms,
        synchronization_state: observation.synchronization_state,
        measured_at_utc: observation.measured_at_utc.clone(),
        session_boundary_resolved_at_utc: observation.session_boundary_resolved_at_utc.clone(),
        operator_summary:
            "Clock synchronization health is current and within the approved skew budget."
                .to_string(),
    }
}

/// Evaluates secret-delivery, rotation, and break-glass health for activation flows.
pub fn evaluate_secret_health(observation: &SecretHealthObservation) -> SecretHealthReport {
    if observation.evidence_age_minutes > observation.max_evidence_age_minutes {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_EVIDENCE_STALE".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Secret-health evidence is stale, so activation cannot trust credential delivery or break-glass state."
                    .to_string(),
        };
    }

    if observation.delivery_surface.embedded() {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_EMBEDDED_SURFACE".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Operational credentials are embedded in an unsafe surface and must block activation."
                    .to_string(),
        };
    }

    if observation
        .delivery_surface
        .requires_root_only_permissions()
        && !observation.root_only_permissions
    {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_FILE_NOT_ROOT_ONLY".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "The encrypted secret file is not root-only, so activation must block until permissions are repaired."
                    .to_string(),
        };
    }

    if observation.credential_domain_growth
        && observation.delivery_surface != SecretDeliverySurface::SecretService
    {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_DELIVERY_TOO_LIGHT".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Credential-domain growth requires a secret service, so lighter delivery paths block activation."
                    .to_string(),
        };
    }

    if observation.break_glass_accessed && !observation.break_glass_reviewed_before_next_live {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_BREAK_GLASS_REVIEW_REQUIRED".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Break-glass access occurred without a reviewed follow-up, so activation must remain blocked."
                    .to_string(),
        };
    }

    if observation.rotation_age_days > observation.max_rotation_age_days {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Block,
            reason_code: "SECRET_HEALTH_ROTATION_EXPIRED".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Secret rotation age exceeds the approved maximum and must block activation."
                    .to_string(),
        };
    }

    if nearing_budget(
        u64::from(observation.rotation_age_days),
        u64::from(observation.max_rotation_age_days),
    ) || observation.break_glass_accessed
    {
        return SecretHealthReport {
            check_id: observation.check_id.clone(),
            credential_ref: observation.credential_ref.clone(),
            state: HealthState::Warn,
            reason_code: "SECRET_HEALTH_ROTATION_AGING".to_string(),
            failure_category: SECRET_HEALTH_CATEGORY,
            secret_type: observation.secret_type.clone(),
            delivery_surface: observation.delivery_surface,
            rotation_age_days: observation.rotation_age_days,
            max_rotation_age_days: observation.max_rotation_age_days,
            break_glass_accessed: observation.break_glass_accessed,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Secret rotation age or reviewed break-glass activity is approaching the activation budget and should be cleaned up."
                    .to_string(),
        };
    }

    SecretHealthReport {
        check_id: observation.check_id.clone(),
        credential_ref: observation.credential_ref.clone(),
        state: HealthState::Green,
        reason_code: "SECRET_HEALTH_WITHIN_POLICY".to_string(),
        failure_category: SECRET_HEALTH_CATEGORY,
        secret_type: observation.secret_type.clone(),
        delivery_surface: observation.delivery_surface,
        rotation_age_days: observation.rotation_age_days,
        max_rotation_age_days: observation.max_rotation_age_days,
        break_glass_accessed: observation.break_glass_accessed,
        observed_at_utc: observation.observed_at_utc.clone(),
        operator_summary:
            "Secret delivery, rotation age, and break-glass status are within the approved activation policy."
                .to_string(),
    }
}

/// Evaluates backup freshness for activation-lane readiness.
pub fn evaluate_backup_freshness(
    observation: &BackupFreshnessObservation,
) -> BackupFreshnessReport {
    if !observation.off_host_recoverable {
        return BackupFreshnessReport {
            check_id: observation.check_id.clone(),
            backup_artifact_id: observation.backup_artifact_id.clone(),
            state: HealthState::Block,
            reason_code: "BACKUP_FRESHNESS_OFF_HOST_REQUIRED".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            freshness_budget_minutes: observation.freshness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Backup evidence is not independently recoverable off-host, so activation must block."
                    .to_string(),
        };
    }

    if observation.age_minutes > observation.freshness_budget_minutes {
        return BackupFreshnessReport {
            check_id: observation.check_id.clone(),
            backup_artifact_id: observation.backup_artifact_id.clone(),
            state: HealthState::Block,
            reason_code: "BACKUP_FRESHNESS_BREACH".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            freshness_budget_minutes: observation.freshness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Backup freshness exceeds the approved budget and must block activation."
                    .to_string(),
        };
    }

    if nearing_budget(
        observation.age_minutes,
        observation.freshness_budget_minutes,
    ) {
        return BackupFreshnessReport {
            check_id: observation.check_id.clone(),
            backup_artifact_id: observation.backup_artifact_id.clone(),
            state: HealthState::Warn,
            reason_code: "BACKUP_FRESHNESS_AGING".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            freshness_budget_minutes: observation.freshness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Backup freshness is nearing the approved budget and should be refreshed before promotion."
                    .to_string(),
        };
    }

    BackupFreshnessReport {
        check_id: observation.check_id.clone(),
        backup_artifact_id: observation.backup_artifact_id.clone(),
        state: HealthState::Green,
        reason_code: "BACKUP_FRESHNESS_WITHIN_POLICY".to_string(),
        failure_category: RECOVERY_HEALTH_CATEGORY,
        age_minutes: observation.age_minutes,
        freshness_budget_minutes: observation.freshness_budget_minutes,
        observed_at_utc: observation.observed_at_utc.clone(),
        operator_summary:
            "Backup freshness is within budget and can be attached to activation preflight."
                .to_string(),
    }
}

/// Evaluates restore-drill freshness and integrity for activation-lane readiness.
pub fn evaluate_restore_drill(observation: &RestoreDrillObservation) -> RestoreDrillReport {
    if !observation.off_host_recoverable {
        return RestoreDrillReport {
            check_id: observation.check_id.clone(),
            restore_drill_id: observation.restore_drill_id.clone(),
            state: HealthState::Block,
            reason_code: "RESTORE_DRILL_OFF_HOST_REQUIRED".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            staleness_budget_minutes: observation.staleness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Restore-drill evidence is not off-host recoverable and must block activation."
                    .to_string(),
        };
    }

    if !observation.digest_chain_verified {
        return RestoreDrillReport {
            check_id: observation.check_id.clone(),
            restore_drill_id: observation.restore_drill_id.clone(),
            state: HealthState::Block,
            reason_code: "RESTORE_DRILL_DIGEST_CHAIN_REQUIRED".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            staleness_budget_minutes: observation.staleness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Restore-drill evidence lacks digest-chain verification and must block activation."
                    .to_string(),
        };
    }

    if !observation.dashboard_visible {
        return RestoreDrillReport {
            check_id: observation.check_id.clone(),
            restore_drill_id: observation.restore_drill_id.clone(),
            state: HealthState::Block,
            reason_code: "RESTORE_DRILL_VISIBILITY_REQUIRED".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            staleness_budget_minutes: observation.staleness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Restore-drill evidence is not visible on the operator surface and must block activation."
                    .to_string(),
        };
    }

    if observation.age_minutes > observation.staleness_budget_minutes {
        return RestoreDrillReport {
            check_id: observation.check_id.clone(),
            restore_drill_id: observation.restore_drill_id.clone(),
            state: HealthState::Block,
            reason_code: "RESTORE_DRILL_STALE".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            staleness_budget_minutes: observation.staleness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Restore-drill evidence is stale and must block activation until a fresh drill is recorded."
                    .to_string(),
        };
    }

    if nearing_budget(
        observation.age_minutes,
        observation.staleness_budget_minutes,
    ) {
        return RestoreDrillReport {
            check_id: observation.check_id.clone(),
            restore_drill_id: observation.restore_drill_id.clone(),
            state: HealthState::Warn,
            reason_code: "RESTORE_DRILL_AGING".to_string(),
            failure_category: RECOVERY_HEALTH_CATEGORY,
            age_minutes: observation.age_minutes,
            staleness_budget_minutes: observation.staleness_budget_minutes,
            observed_at_utc: observation.observed_at_utc.clone(),
            operator_summary:
                "Restore-drill evidence is nearing the staleness budget and should be refreshed before live activation."
                    .to_string(),
        };
    }

    RestoreDrillReport {
        check_id: observation.check_id.clone(),
        restore_drill_id: observation.restore_drill_id.clone(),
        state: HealthState::Green,
        reason_code: "RESTORE_DRILL_WITHIN_POLICY".to_string(),
        failure_category: RECOVERY_HEALTH_CATEGORY,
        age_minutes: observation.age_minutes,
        staleness_budget_minutes: observation.staleness_budget_minutes,
        observed_at_utc: observation.observed_at_utc.clone(),
        operator_summary:
            "Restore-drill evidence is fresh, verified, and visible enough for activation preflight."
                .to_string(),
    }
}

/// Aggregates provider outputs into the exact activation-lane evidence vocabulary expected later by readiness packets.
pub fn evaluate_activation_preflight(
    summary_id: impl Into<String>,
    clock_report: &ClockHealthReport,
    secret_report: &SecretHealthReport,
    backup_report: &BackupFreshnessReport,
    restore_report: &RestoreDrillReport,
) -> ActivationPreflightSummary {
    let mut state = HealthState::Green;
    let mut failed_check_ids = Vec::new();
    let mut warning_check_ids = Vec::new();
    let mut failure_categories = Vec::new();

    for (check_id, report_state, category) in [
        (
            clock_report.check_id.as_str(),
            clock_report.state,
            clock_report.failure_category,
        ),
        (
            secret_report.check_id.as_str(),
            secret_report.state,
            secret_report.failure_category,
        ),
        (
            backup_report.check_id.as_str(),
            backup_report.state,
            backup_report.failure_category,
        ),
        (
            restore_report.check_id.as_str(),
            restore_report.state,
            restore_report.failure_category,
        ),
    ] {
        state = max_state(state, report_state);
        if report_state == HealthState::Block {
            failed_check_ids.push(check_id.to_string());
            if !failure_categories.contains(&category) {
                failure_categories.push(category);
            }
        } else if report_state != HealthState::Green {
            warning_check_ids.push(check_id.to_string());
        }
    }

    let (reason_code, operator_summary) = match state {
        HealthState::Green => (
            "ACTIVATION_PREFLIGHT_HEALTHY".to_string(),
            "Clock discipline, secret health, backup freshness, and restore-drill status are all green for activation.".to_string(),
        ),
        HealthState::Warn => (
            "ACTIVATION_PREFLIGHT_WARNINGS".to_string(),
            "Activation preflight is green enough to inspect but carries aging health evidence that should be cleaned up.".to_string(),
        ),
        HealthState::Restrict => (
            "ACTIVATION_PREFLIGHT_RESTRICTED".to_string(),
            "Activation preflight found a restricted health posture, so the host should not proceed as fully tradeable.".to_string(),
        ),
        HealthState::Block => (
            "ACTIVATION_PREFLIGHT_BLOCKED".to_string(),
            "Activation preflight found blocking health evidence and must not proceed until the failed checks are repaired.".to_string(),
        ),
    };

    ActivationPreflightSummary {
        summary_id: summary_id.into(),
        state,
        reason_code,
        clock_health_check_id: clock_report.check_id.clone(),
        secret_health_check_id: secret_report.check_id.clone(),
        backup_freshness_check_id: backup_report.check_id.clone(),
        restore_drill_check_id: restore_report.check_id.clone(),
        failed_check_ids,
        warning_check_ids,
        failure_categories,
        operator_summary,
    }
}

fn base_clock_health_observation() -> ClockHealthObservation {
    ClockHealthObservation {
        check_id: "clock_health_preflight_default".to_string(),
        session_id: "globex-2026-03-27".to_string(),
        measured_at_utc: "2026-03-27T20:00:00+00:00".to_string(),
        session_boundary_resolved_at_utc: "2026-03-27T19:59:00+00:00".to_string(),
        measurement_age_minutes: 1,
        max_measurement_age_minutes: 15,
        measured_skew_ms: 42,
        warn_threshold_ms: 100,
        restrict_threshold_ms: 500,
        block_threshold_ms: 2000,
        synchronization_state: ClockSyncState::Synced,
    }
}

fn base_secret_health_observation() -> SecretHealthObservation {
    SecretHealthObservation {
        check_id: "secret_health_preflight_default".to_string(),
        credential_ref: "opsd-broker-runtime-credential".to_string(),
        observed_at_utc: "2026-03-27T20:00:30+00:00".to_string(),
        evidence_age_minutes: 2,
        max_evidence_age_minutes: 30,
        secret_type: "broker_runtime_credential".to_string(),
        delivery_surface: SecretDeliverySurface::RuntimeSecretPath,
        credential_domain_growth: false,
        root_only_permissions: true,
        rotation_age_days: 12,
        max_rotation_age_days: 30,
        break_glass_accessed: false,
        break_glass_reviewed_before_next_live: true,
    }
}

fn base_backup_freshness_observation() -> BackupFreshnessObservation {
    BackupFreshnessObservation {
        check_id: "backup_freshness_preflight_default".to_string(),
        backup_artifact_id: "backup-20260327T1950".to_string(),
        observed_at_utc: "2026-03-27T20:00:45+00:00".to_string(),
        age_minutes: 10,
        freshness_budget_minutes: 30,
        off_host_recoverable: true,
    }
}

fn base_restore_drill_observation() -> RestoreDrillObservation {
    RestoreDrillObservation {
        check_id: "restore_drill_preflight_default".to_string(),
        restore_drill_id: "restore-drill-20260326T1800".to_string(),
        observed_at_utc: "2026-03-27T20:01:00+00:00".to_string(),
        age_minutes: 60,
        staleness_budget_minutes: 1440,
        digest_chain_verified: true,
        off_host_recoverable: true,
        dashboard_visible: true,
    }
}

/// Built-in clock-health scenarios used by tests and smoke drills.
pub fn sample_clock_health_observation(name: &str) -> Option<ClockHealthObservation> {
    let mut observation = base_clock_health_observation();
    match name {
        "green" => Some(observation),
        "restrict" => {
            observation.measured_skew_ms = 750;
            Some(observation)
        }
        "blocked-unknown-sync" => {
            observation.synchronization_state = ClockSyncState::Unknown;
            Some(observation)
        }
        "stale-evidence" => {
            observation.measurement_age_minutes = 45;
            Some(observation)
        }
        _ => None,
    }
}

/// Built-in secret-health scenarios used by tests and smoke drills.
pub fn sample_secret_health_observation(name: &str) -> Option<SecretHealthObservation> {
    let mut observation = base_secret_health_observation();
    match name {
        "green" => Some(observation),
        "rotation-aging" => {
            observation.rotation_age_days = 26;
            Some(observation)
        }
        "break-glass-review-required" => {
            observation.break_glass_accessed = true;
            observation.break_glass_reviewed_before_next_live = false;
            Some(observation)
        }
        "embedded-manifest" => {
            observation.delivery_surface = SecretDeliverySurface::Manifest;
            Some(observation)
        }
        _ => None,
    }
}

/// Built-in activation-preflight scenario inputs used by tests and smoke drills.
pub fn sample_activation_preflight_inputs(
    name: &str,
) -> Option<(
    ClockHealthReport,
    SecretHealthReport,
    BackupFreshnessReport,
    RestoreDrillReport,
    ActivationPreflightSummary,
)> {
    let clock_report = match name {
        "blocked-clock" => {
            let observation = sample_clock_health_observation("blocked-unknown-sync")?;
            evaluate_clock_health(&observation)
        }
        _ => {
            let observation = sample_clock_health_observation("green")?;
            evaluate_clock_health(&observation)
        }
    };

    let secret_report = match name {
        "blocked-secret" => {
            let observation = sample_secret_health_observation("break-glass-review-required")?;
            evaluate_secret_health(&observation)
        }
        _ => {
            let observation = sample_secret_health_observation("green")?;
            evaluate_secret_health(&observation)
        }
    };

    let backup_observation = match name {
        "warn-aging" => BackupFreshnessObservation {
            age_minutes: 26,
            ..base_backup_freshness_observation()
        },
        _ => base_backup_freshness_observation(),
    };
    let backup_report = evaluate_backup_freshness(&backup_observation);

    let restore_observation = match name {
        "warn-aging" => RestoreDrillObservation {
            age_minutes: 1300,
            ..base_restore_drill_observation()
        },
        _ => base_restore_drill_observation(),
    };
    let restore_report = evaluate_restore_drill(&restore_observation);

    let summary = evaluate_activation_preflight(
        format!("activation_preflight_{name}"),
        &clock_report,
        &secret_report,
        &backup_report,
        &restore_report,
    );
    Some((
        clock_report,
        secret_report,
        backup_report,
        restore_report,
        summary,
    ))
}

#[cfg(test)]
mod tests {
    use super::{
        HealthState, evaluate_activation_preflight, evaluate_backup_freshness,
        evaluate_clock_health, evaluate_restore_drill, evaluate_secret_health,
        sample_activation_preflight_inputs, sample_clock_health_observation,
        sample_secret_health_observation,
    };

    #[test]
    fn clock_health_passes_when_skew_is_within_budget() {
        let observation =
            sample_clock_health_observation("green").expect("green clock scenario exists");
        let report = evaluate_clock_health(&observation);
        assert_eq!(HealthState::Green, report.state);
        assert_eq!("CLOCK_SKEW_WITHIN_POLICY", report.reason_code);
    }

    #[test]
    fn clock_health_restricts_when_skew_crosses_restrict_threshold() {
        let observation =
            sample_clock_health_observation("restrict").expect("restrict clock scenario exists");
        let report = evaluate_clock_health(&observation);
        assert_eq!(HealthState::Restrict, report.state);
        assert_eq!("CLOCK_SKEW_RESTRICT_THRESHOLD", report.reason_code);
    }

    #[test]
    fn clock_health_blocks_when_sync_state_is_unknown() {
        let observation = sample_clock_health_observation("blocked-unknown-sync")
            .expect("blocked clock scenario exists");
        let report = evaluate_clock_health(&observation);
        assert_eq!(HealthState::Block, report.state);
        assert_eq!("CLOCK_SYNC_STATE_UNKNOWN", report.reason_code);
    }

    #[test]
    fn secret_health_warns_when_rotation_is_aging() {
        let observation = sample_secret_health_observation("rotation-aging")
            .expect("rotation aging scenario exists");
        let report = evaluate_secret_health(&observation);
        assert_eq!(HealthState::Warn, report.state);
        assert_eq!("SECRET_HEALTH_ROTATION_AGING", report.reason_code);
    }

    #[test]
    fn secret_health_blocks_on_embedded_manifest_surface() {
        let observation = sample_secret_health_observation("embedded-manifest")
            .expect("embedded manifest scenario exists");
        let report = evaluate_secret_health(&observation);
        assert_eq!(HealthState::Block, report.state);
        assert_eq!("SECRET_HEALTH_EMBEDDED_SURFACE", report.reason_code);
    }

    #[test]
    fn secret_health_blocks_when_break_glass_lacks_review() {
        let observation = sample_secret_health_observation("break-glass-review-required")
            .expect("break-glass scenario exists");
        let report = evaluate_secret_health(&observation);
        assert_eq!(HealthState::Block, report.state);
        assert_eq!(
            "SECRET_HEALTH_BREAK_GLASS_REVIEW_REQUIRED",
            report.reason_code
        );
    }

    #[test]
    fn backup_freshness_warns_when_nearing_budget() {
        let report = evaluate_backup_freshness(&super::BackupFreshnessObservation {
            age_minutes: 26,
            ..super::base_backup_freshness_observation()
        });
        assert_eq!(HealthState::Warn, report.state);
        assert_eq!("BACKUP_FRESHNESS_AGING", report.reason_code);
    }

    #[test]
    fn restore_drill_blocks_without_digest_chain_verification() {
        let report = evaluate_restore_drill(&super::RestoreDrillObservation {
            digest_chain_verified: false,
            ..super::base_restore_drill_observation()
        });
        assert_eq!(HealthState::Block, report.state);
        assert_eq!("RESTORE_DRILL_DIGEST_CHAIN_REQUIRED", report.reason_code);
    }

    #[test]
    fn activation_preflight_is_green_when_all_inputs_are_green() {
        let (clock, secret, backup, restore, summary) =
            sample_activation_preflight_inputs("green").expect("green preflight exists");
        let recomputed =
            evaluate_activation_preflight("activation_green", &clock, &secret, &backup, &restore);
        assert_eq!(HealthState::Green, summary.state);
        assert_eq!(HealthState::Green, recomputed.state);
    }

    #[test]
    fn activation_preflight_aggregates_blocking_inputs() {
        let (_, _, _, _, summary) = sample_activation_preflight_inputs("blocked-clock")
            .expect("blocked-clock preflight exists");
        assert_eq!(HealthState::Block, summary.state);
        assert!(
            summary
                .failed_check_ids
                .contains(&"clock_health_preflight_default".to_string())
        );
    }

    #[test]
    fn activation_preflight_retains_warning_checks() {
        let (_, _, _, _, summary) =
            sample_activation_preflight_inputs("warn-aging").expect("warn-aging preflight exists");
        assert_eq!(HealthState::Warn, summary.state);
        assert!(!summary.warning_check_ids.is_empty());
    }
}
