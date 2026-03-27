//! Backup, restore, and migration tooling for the operational runtime.
//!
//! The watchdog crate is the safest home for this command path because it may
//! inspect runtime health and recovery evidence without owning live strategy or
//! broker state.

use std::fs;
use std::path::Path;

/// Supported runtime-state schema version for executable migrations.
pub const SUPPORTED_RUNTIME_SCHEMA_VERSION: u16 = 1;
/// Supported snapshot schema version for executable migrations.
pub const SUPPORTED_SNAPSHOT_SCHEMA_VERSION: u16 = 1;
/// Supported journal schema version for executable migrations.
pub const SUPPORTED_JOURNAL_SCHEMA_VERSION: u16 = 1;

/// Snapshot material retained for restore verification.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SnapshotManifest {
    pub snapshot_artifact_id: String,
    pub runtime_schema_version: u16,
    pub snapshot_schema_version: u16,
    pub journal_schema_version: u16,
    pub last_applied_sequence: u64,
    pub journal_digest_frontier: String,
    pub state_digest: String,
}

/// One digest-anchored journal record retained in the restore chain.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct JournalDigestRecord {
    pub sequence: u64,
    pub event_id: String,
    pub prior_cumulative_digest: Option<String>,
    pub payload_digest: String,
    pub cumulative_digest: String,
}

/// Backup material and off-host reference for restore drills.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BackupManifest {
    pub backup_artifact_id: String,
    pub snapshot_artifact_id: String,
    pub created_at_minute: u64,
    pub off_host_uri: String,
    pub tamper_evident: bool,
    pub digest_manifest_artifact_id: String,
}

/// Recoverability evidence retained alongside backup material.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DurabilityEvidence {
    pub evidence_artifact_id: String,
    pub off_host_recoverable: bool,
    pub tamper_evident: bool,
    pub latest_restore_drill_minute: u64,
    pub max_restore_drill_staleness_minutes: u64,
}

/// Executable restore verification request routed through watchdog.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RestoreExecutionRequest {
    pub request_id: String,
    pub deployment_instance_id: String,
    pub snapshot: SnapshotManifest,
    pub journal_chain: Vec<JournalDigestRecord>,
    pub backup: BackupManifest,
    pub durability: DurabilityEvidence,
    pub expected_frontier_digest: String,
    pub clean_host: bool,
    pub ambiguity_detected: bool,
    pub broker_reconciliation_clean: bool,
    pub reviewed_waiver_id: Option<String>,
    pub max_backup_age_minutes: u64,
    pub current_minute: u64,
}

/// Operator outcome for a restore verification run.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RecoveryDisposition {
    SafeResume,
    SafeHalt,
}

impl RecoveryDisposition {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SafeResume => "safe_resume",
            Self::SafeHalt => "safe_halt",
        }
    }
}

/// Inspectable restore verification report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RestoreExecutionReport {
    pub request_id: String,
    pub disposition: RecoveryDisposition,
    pub reason_code: String,
    pub verified_frontier_digest: String,
    pub backup_age_minutes: u64,
    pub retained_artifact_ids: Vec<String>,
    pub missing_requirements: Vec<String>,
    pub explanation: String,
}

/// Canonical schema-version tuple used for migrations.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct VersionSet {
    pub runtime: u16,
    pub snapshot: u16,
    pub journal: u16,
}

impl VersionSet {
    fn render(self) -> String {
        format!(
            "runtime={}. snapshot={}. journal={}.",
            self.runtime, self.snapshot, self.journal
        )
    }
}

/// Migration domains handled by the watchdog command path.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MigrationDomain {
    Journal,
    Snapshot,
    Runtime,
}

impl MigrationDomain {
    fn as_str(self) -> &'static str {
        match self {
            Self::Journal => "journal",
            Self::Snapshot => "snapshot",
            Self::Runtime => "runtime",
        }
    }
}

/// One applied migration step with retained manifest identity.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MigrationStep {
    pub domain: MigrationDomain,
    pub from_version: u16,
    pub to_version: u16,
    pub manifest_artifact_id: String,
}

/// Executable migration request routed through watchdog.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MigrationExecutionRequest {
    pub execution_id: String,
    pub from: VersionSet,
    pub to: VersionSet,
    pub backup_artifact_id: String,
    pub digest_frontier_id: String,
    pub operator_approval_id: String,
    pub state_store_clean: bool,
    pub backup_verified: bool,
}

/// Migration outcome reported to the operator.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MigrationStatus {
    Executed,
    Rejected,
    SafeHalt,
}

impl MigrationStatus {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Executed => "executed",
            Self::Rejected => "rejected",
            Self::SafeHalt => "safe_halt",
        }
    }
}

/// Inspectable migration execution report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MigrationExecutionReport {
    pub execution_id: String,
    pub status: MigrationStatus,
    pub reason_code: String,
    pub applied_steps: Vec<MigrationStep>,
    pub retained_artifact_ids: Vec<String>,
    pub safe_halt_required: bool,
    pub explanation: String,
}

fn missing_string(label: &str, value: &str, missing: &mut Vec<String>) {
    if value.is_empty() {
        missing.push(label.to_string());
    }
}

fn verify_digest_chain(
    chain: &[JournalDigestRecord],
    expected_last_sequence: u64,
) -> Result<&JournalDigestRecord, &'static str> {
    if chain.is_empty() {
        return Err("RESTORE_JOURNAL_CHAIN_REQUIRED");
    }

    let mut previous_digest: Option<&str> = None;
    for (expected_sequence, record) in (1_u64..).zip(chain.iter()) {
        if record.sequence != expected_sequence {
            return Err("RESTORE_JOURNAL_SEQUENCE_GAP");
        }
        if record.event_id.is_empty()
            || record.payload_digest.is_empty()
            || record.cumulative_digest.is_empty()
        {
            return Err("RESTORE_JOURNAL_RECORD_FIELDS_REQUIRED");
        }
        if previous_digest != record.prior_cumulative_digest.as_deref() {
            return Err("RESTORE_JOURNAL_DIGEST_CHAIN_BROKEN");
        }
        previous_digest = Some(record.cumulative_digest.as_str());
    }

    let Some(last) = chain.last() else {
        return Err("RESTORE_JOURNAL_CHAIN_REQUIRED");
    };
    if last.sequence != expected_last_sequence {
        return Err("RESTORE_JOURNAL_FRONTIER_SEQUENCE_MISMATCH");
    }
    Ok(last)
}

fn restore_artifact_ids(request: &RestoreExecutionRequest) -> Vec<String> {
    vec![
        request.backup.backup_artifact_id.clone(),
        request.backup.digest_manifest_artifact_id.clone(),
        request.snapshot.snapshot_artifact_id.clone(),
        request.durability.evidence_artifact_id.clone(),
    ]
}

fn render_restore_request(request: &RestoreExecutionRequest) -> String {
    let mut lines = vec![
        format!("request_id={}", request.request_id),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!(
            "snapshot_artifact_id={}",
            request.snapshot.snapshot_artifact_id
        ),
        format!("backup_artifact_id={}", request.backup.backup_artifact_id),
        format!(
            "expected_frontier_digest={}",
            request.expected_frontier_digest
        ),
        format!("clean_host={}", request.clean_host),
        format!("ambiguity_detected={}", request.ambiguity_detected),
        format!(
            "broker_reconciliation_clean={}",
            request.broker_reconciliation_clean
        ),
        format!("current_minute={}", request.current_minute),
        format!("max_backup_age_minutes={}", request.max_backup_age_minutes),
    ];
    if let Some(waiver_id) = request.reviewed_waiver_id.as_deref() {
        lines.push(format!("reviewed_waiver_id={waiver_id}"));
    }
    lines.join("\n")
}

fn render_journal_chain(chain: &[JournalDigestRecord]) -> String {
    let mut lines = Vec::new();
    for record in chain {
        lines.push(format!(
            "sequence={} event_id={} prior_digest={} cumulative_digest={}",
            record.sequence,
            record.event_id,
            record.prior_cumulative_digest.as_deref().unwrap_or("none"),
            record.cumulative_digest,
        ));
    }
    lines.join("\n")
}

fn render_restore_report(report: &RestoreExecutionReport) -> String {
    let mut lines = vec![
        format!("request_id={}", report.request_id),
        format!("disposition={}", report.disposition.as_str()),
        format!("reason_code={}", report.reason_code),
        format!(
            "verified_frontier_digest={}",
            report.verified_frontier_digest
        ),
        format!("backup_age_minutes={}", report.backup_age_minutes),
        format!("explanation={}", report.explanation),
    ];
    if !report.missing_requirements.is_empty() {
        lines.push(format!(
            "missing_requirements={}",
            report.missing_requirements.join(",")
        ));
    }
    if !report.retained_artifact_ids.is_empty() {
        lines.push(format!(
            "retained_artifact_ids={}",
            report.retained_artifact_ids.join(",")
        ));
    }
    lines.join("\n")
}

fn render_migration_request(request: &MigrationExecutionRequest) -> String {
    [
        format!("execution_id={}", request.execution_id),
        format!("from_versions={}", request.from.render()),
        format!("to_versions={}", request.to.render()),
        format!("backup_artifact_id={}", request.backup_artifact_id),
        format!("digest_frontier_id={}", request.digest_frontier_id),
        format!("operator_approval_id={}", request.operator_approval_id),
        format!("state_store_clean={}", request.state_store_clean),
        format!("backup_verified={}", request.backup_verified),
    ]
    .join("\n")
}

fn render_migration_plan(report: &MigrationExecutionReport) -> String {
    let mut lines = vec![
        format!("execution_id={}", report.execution_id),
        format!("status={}", report.status.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("safe_halt_required={}", report.safe_halt_required),
        format!("explanation={}", report.explanation),
    ];
    if !report.retained_artifact_ids.is_empty() {
        lines.push(format!(
            "retained_artifact_ids={}",
            report.retained_artifact_ids.join(",")
        ));
    }
    for step in &report.applied_steps {
        lines.push(format!(
            "step domain={} from={} to={} manifest={}",
            step.domain.as_str(),
            step.from_version,
            step.to_version,
            step.manifest_artifact_id
        ));
    }
    lines.join("\n")
}

/// Writes retained restore drill artifacts to the provided directory.
pub fn write_restore_artifacts(
    root: &Path,
    request: &RestoreExecutionRequest,
    report: &RestoreExecutionReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("restore_request.txt"),
        render_restore_request(request),
    )?;
    fs::write(
        root.join("restore_report.txt"),
        render_restore_report(report),
    )?;
    fs::write(
        root.join("journal_chain.txt"),
        render_journal_chain(&request.journal_chain),
    )?;
    Ok(())
}

/// Writes retained migration artifacts to the provided directory.
pub fn write_migration_artifacts(
    root: &Path,
    request: &MigrationExecutionRequest,
    report: &MigrationExecutionReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("migration_request.txt"),
        render_migration_request(request),
    )?;
    fs::write(
        root.join("migration_report.txt"),
        render_migration_plan(report),
    )?;
    Ok(())
}

/// Verifies restore material and returns a governed safe-resume or safe-halt report.
pub fn verify_restore_execution(request: &RestoreExecutionRequest) -> RestoreExecutionReport {
    let mut missing = Vec::new();
    missing_string("request_id", &request.request_id, &mut missing);
    missing_string(
        "deployment_instance_id",
        &request.deployment_instance_id,
        &mut missing,
    );
    missing_string(
        "snapshot.snapshot_artifact_id",
        &request.snapshot.snapshot_artifact_id,
        &mut missing,
    );
    missing_string(
        "snapshot.journal_digest_frontier",
        &request.snapshot.journal_digest_frontier,
        &mut missing,
    );
    missing_string(
        "snapshot.state_digest",
        &request.snapshot.state_digest,
        &mut missing,
    );
    missing_string(
        "backup.backup_artifact_id",
        &request.backup.backup_artifact_id,
        &mut missing,
    );
    missing_string(
        "backup.snapshot_artifact_id",
        &request.backup.snapshot_artifact_id,
        &mut missing,
    );
    missing_string(
        "backup.off_host_uri",
        &request.backup.off_host_uri,
        &mut missing,
    );
    missing_string(
        "backup.digest_manifest_artifact_id",
        &request.backup.digest_manifest_artifact_id,
        &mut missing,
    );
    missing_string(
        "durability.evidence_artifact_id",
        &request.durability.evidence_artifact_id,
        &mut missing,
    );
    missing_string(
        "expected_frontier_digest",
        &request.expected_frontier_digest,
        &mut missing,
    );
    if !missing.is_empty() {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_REQUIRED_FIELDS_MISSING".to_string(),
            verified_frontier_digest: String::new(),
            backup_age_minutes: 0,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: missing,
            explanation:
                "Restore verification requires explicit backup, snapshot, frontier, and durability artifacts."
                    .to_string(),
        };
    }

    if request.current_minute < request.backup.created_at_minute {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_CLOCK_FRONTIER_REGRESSION".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes: 0,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["current_minute".to_string()],
            explanation: "Backup creation time cannot be ahead of the restore verifier clock."
                .to_string(),
        };
    }

    let backup_age_minutes = request.current_minute - request.backup.created_at_minute;
    if backup_age_minutes > request.max_backup_age_minutes {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_BACKUP_TOO_STALE".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["fresh_backup".to_string()],
            explanation:
                "Restore verification refused a backup older than the configured freshness threshold."
                    .to_string(),
        };
    }

    if !request.backup.tamper_evident
        || !request.durability.tamper_evident
        || !request.durability.off_host_recoverable
    {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_DURABILITY_EVIDENCE_INVALID".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec![
                "tamper_evident_backup".to_string(),
                "off_host_recoverability".to_string(),
            ],
            explanation:
                "Restore verification requires tamper-evident off-host backup evidence before it may proceed."
                    .to_string(),
        };
    }

    if request.current_minute < request.durability.latest_restore_drill_minute {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_DRILL_CLOCK_REGRESSION".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["latest_restore_drill_minute".to_string()],
            explanation: "Restore-drill evidence cannot be newer than the verifier clock."
                .to_string(),
        };
    }

    let drill_age = request.current_minute - request.durability.latest_restore_drill_minute;
    if drill_age > request.durability.max_restore_drill_staleness_minutes {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_DRILL_EVIDENCE_TOO_STALE".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["fresh_restore_drill".to_string()],
            explanation: "Restore verification requires a recent restore drill before safe resume."
                .to_string(),
        };
    }

    if request.backup.snapshot_artifact_id != request.snapshot.snapshot_artifact_id {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_SNAPSHOT_BINDING_MISMATCH".to_string(),
            verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["matching_snapshot_binding".to_string()],
            explanation:
                "Backup material must bind to the exact snapshot artifact used for restore verification."
                    .to_string(),
        };
    }

    let chain_tail = match verify_digest_chain(
        &request.journal_chain,
        request.snapshot.last_applied_sequence,
    ) {
        Ok(last) => last,
        Err(reason_code) => {
            return RestoreExecutionReport {
                request_id: request.request_id.clone(),
                disposition: RecoveryDisposition::SafeHalt,
                reason_code: reason_code.to_string(),
                verified_frontier_digest: request.snapshot.journal_digest_frontier.clone(),
                backup_age_minutes,
                retained_artifact_ids: restore_artifact_ids(request),
                missing_requirements: vec!["valid_journal_chain".to_string()],
                explanation:
                    "Snapshot restore must verify a contiguous journal digest chain up to the frontier."
                        .to_string(),
            };
        }
    };

    if chain_tail.cumulative_digest != request.snapshot.journal_digest_frontier
        || chain_tail.cumulative_digest != request.expected_frontier_digest
    {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_DIGEST_FRONTIER_MISMATCH".to_string(),
            verified_frontier_digest: chain_tail.cumulative_digest.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["matching_digest_frontier".to_string()],
            explanation:
                "Restore verification refused material whose snapshot, requested frontier, and journal digest chain do not converge."
                    .to_string(),
        };
    }

    if !request.clean_host {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_CLEAN_HOST_REQUIRED".to_string(),
            verified_frontier_digest: chain_tail.cumulative_digest.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["clean_host".to_string()],
            explanation:
                "Restore verification requires replay to a clean host before any safe-resume decision."
                    .to_string(),
        };
    }

    if request.ambiguity_detected {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_AMBIGUITY_REQUIRES_SAFE_HALT".to_string(),
            verified_frontier_digest: chain_tail.cumulative_digest.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["ambiguity_resolution".to_string()],
            explanation:
                "Any ambiguity in restored state or intent ownership forces a rollback-safe halt."
                    .to_string(),
        };
    }

    if !request.broker_reconciliation_clean && request.reviewed_waiver_id.is_none() {
        return RestoreExecutionReport {
            request_id: request.request_id.clone(),
            disposition: RecoveryDisposition::SafeHalt,
            reason_code: "RESTORE_RECONCILIATION_REVIEW_REQUIRED".to_string(),
            verified_frontier_digest: chain_tail.cumulative_digest.clone(),
            backup_age_minutes,
            retained_artifact_ids: restore_artifact_ids(request),
            missing_requirements: vec!["reviewed_waiver_id".to_string()],
            explanation:
                "Restore verification cannot allow safe resume after a dirty broker reconciliation without a reviewed waiver."
                    .to_string(),
        };
    }

    RestoreExecutionReport {
        request_id: request.request_id.clone(),
        disposition: RecoveryDisposition::SafeResume,
        reason_code: "RESTORE_MATERIAL_VERIFIED".to_string(),
        verified_frontier_digest: chain_tail.cumulative_digest.clone(),
        backup_age_minutes,
        retained_artifact_ids: restore_artifact_ids(request),
        missing_requirements: Vec::new(),
        explanation:
            "Restore verification matched the snapshot frontier to a contiguous digest chain, confirmed off-host tamper-evident durability, and governed resume safety."
                .to_string(),
    }
}

fn version_delta(from: u16, to: u16) -> i32 {
    i32::from(to) - i32::from(from)
}

/// Executes a versioned migration request or refuses it with an operator-readable reason.
pub fn execute_migration(request: &MigrationExecutionRequest) -> MigrationExecutionReport {
    let mut missing = Vec::new();
    missing_string("execution_id", &request.execution_id, &mut missing);
    missing_string(
        "backup_artifact_id",
        &request.backup_artifact_id,
        &mut missing,
    );
    missing_string(
        "digest_frontier_id",
        &request.digest_frontier_id,
        &mut missing,
    );
    missing_string(
        "operator_approval_id",
        &request.operator_approval_id,
        &mut missing,
    );
    if !missing.is_empty() {
        return MigrationExecutionReport {
            execution_id: request.execution_id.clone(),
            status: MigrationStatus::Rejected,
            reason_code: "MIGRATION_REQUIRED_FIELDS_MISSING".to_string(),
            applied_steps: Vec::new(),
            retained_artifact_ids: vec![
                request.backup_artifact_id.clone(),
                request.digest_frontier_id.clone(),
            ],
            safe_halt_required: false,
            explanation:
                "Migration execution requires explicit backup, digest frontier, and operator approval artifacts."
                    .to_string(),
        };
    }

    if !request.backup_verified || !request.state_store_clean {
        return MigrationExecutionReport {
            execution_id: request.execution_id.clone(),
            status: MigrationStatus::SafeHalt,
            reason_code: "MIGRATION_PREREQUISITES_NOT_MET".to_string(),
            applied_steps: Vec::new(),
            retained_artifact_ids: vec![
                request.backup_artifact_id.clone(),
                request.digest_frontier_id.clone(),
                request.operator_approval_id.clone(),
            ],
            safe_halt_required: true,
            explanation:
                "Migration execution halted because verified backup evidence and a clean state-store frontier are mandatory prerequisites."
                    .to_string(),
        };
    }

    let runtime_delta = version_delta(request.from.runtime, request.to.runtime);
    let snapshot_delta = version_delta(request.from.snapshot, request.to.snapshot);
    let journal_delta = version_delta(request.from.journal, request.to.journal);

    if runtime_delta == 0 && snapshot_delta == 0 && journal_delta == 0 {
        return MigrationExecutionReport {
            execution_id: request.execution_id.clone(),
            status: MigrationStatus::Rejected,
            reason_code: "MIGRATION_NO_CHANGES_REQUESTED".to_string(),
            applied_steps: Vec::new(),
            retained_artifact_ids: vec![
                request.backup_artifact_id.clone(),
                request.digest_frontier_id.clone(),
                request.operator_approval_id.clone(),
            ],
            safe_halt_required: false,
            explanation:
                "Migration execution refused a no-op request because no version boundary would change."
                    .to_string(),
        };
    }

    if runtime_delta < 0 || snapshot_delta < 0 || journal_delta < 0 {
        return MigrationExecutionReport {
            execution_id: request.execution_id.clone(),
            status: MigrationStatus::Rejected,
            reason_code: "MIGRATION_DOWNGRADE_REJECTED".to_string(),
            applied_steps: Vec::new(),
            retained_artifact_ids: vec![
                request.backup_artifact_id.clone(),
                request.digest_frontier_id.clone(),
                request.operator_approval_id.clone(),
            ],
            safe_halt_required: false,
            explanation: "Migration execution refused an unsupported downgrade transition."
                .to_string(),
        };
    }

    if runtime_delta > 1 || snapshot_delta > 1 || journal_delta > 1 {
        return MigrationExecutionReport {
            execution_id: request.execution_id.clone(),
            status: MigrationStatus::Rejected,
            reason_code: "MIGRATION_UNSUPPORTED_VERSION_SKIP".to_string(),
            applied_steps: Vec::new(),
            retained_artifact_ids: vec![
                request.backup_artifact_id.clone(),
                request.digest_frontier_id.clone(),
                request.operator_approval_id.clone(),
            ],
            safe_halt_required: false,
            explanation:
                "Migration execution only supports one-version-at-a-time upgrades for runtime, snapshot, and journal schemas."
                    .to_string(),
        };
    }

    let mut applied_steps = Vec::new();
    for (domain, from_version, to_version) in [
        (
            MigrationDomain::Journal,
            request.from.journal,
            request.to.journal,
        ),
        (
            MigrationDomain::Snapshot,
            request.from.snapshot,
            request.to.snapshot,
        ),
        (
            MigrationDomain::Runtime,
            request.from.runtime,
            request.to.runtime,
        ),
    ] {
        if from_version != to_version {
            applied_steps.push(MigrationStep {
                domain,
                from_version,
                to_version,
                manifest_artifact_id: format!(
                    "migration::{execution_id}::{domain}::{from_version}->{to_version}",
                    execution_id = request.execution_id,
                    domain = domain.as_str(),
                ),
            });
        }
    }

    MigrationExecutionReport {
        execution_id: request.execution_id.clone(),
        status: MigrationStatus::Executed,
        reason_code: "MIGRATION_EXECUTED".to_string(),
        applied_steps,
        retained_artifact_ids: vec![
            request.backup_artifact_id.clone(),
            request.digest_frontier_id.clone(),
            request.operator_approval_id.clone(),
        ],
        safe_halt_required: false,
        explanation:
            "Migration execution applied only incremental, operator-approved transitions on top of a verified backup and digest frontier."
                .to_string(),
    }
}

fn base_restore_request() -> RestoreExecutionRequest {
    RestoreExecutionRequest {
        request_id: "restore-happy-path".to_string(),
        deployment_instance_id: "opsd-gc-001".to_string(),
        snapshot: SnapshotManifest {
            snapshot_artifact_id: "snapshot-20260327T2000".to_string(),
            runtime_schema_version: SUPPORTED_RUNTIME_SCHEMA_VERSION,
            snapshot_schema_version: SUPPORTED_SNAPSHOT_SCHEMA_VERSION,
            journal_schema_version: SUPPORTED_JOURNAL_SCHEMA_VERSION,
            last_applied_sequence: 3,
            journal_digest_frontier: "digest-3".to_string(),
            state_digest: "state-digest-17".to_string(),
        },
        journal_chain: vec![
            JournalDigestRecord {
                sequence: 1,
                event_id: "event-1".to_string(),
                prior_cumulative_digest: None,
                payload_digest: "payload-1".to_string(),
                cumulative_digest: "digest-1".to_string(),
            },
            JournalDigestRecord {
                sequence: 2,
                event_id: "event-2".to_string(),
                prior_cumulative_digest: Some("digest-1".to_string()),
                payload_digest: "payload-2".to_string(),
                cumulative_digest: "digest-2".to_string(),
            },
            JournalDigestRecord {
                sequence: 3,
                event_id: "event-3".to_string(),
                prior_cumulative_digest: Some("digest-2".to_string()),
                payload_digest: "payload-3".to_string(),
                cumulative_digest: "digest-3".to_string(),
            },
        ],
        backup: BackupManifest {
            backup_artifact_id: "backup-20260327T1950".to_string(),
            snapshot_artifact_id: "snapshot-20260327T2000".to_string(),
            created_at_minute: 490,
            off_host_uri: "s3://gc-backups/backup-20260327T1950".to_string(),
            tamper_evident: true,
            digest_manifest_artifact_id: "backup-digest-20260327T1950".to_string(),
        },
        durability: DurabilityEvidence {
            evidence_artifact_id: "durability-proof-20260327T1955".to_string(),
            off_host_recoverable: true,
            tamper_evident: true,
            latest_restore_drill_minute: 495,
            max_restore_drill_staleness_minutes: 60,
        },
        expected_frontier_digest: "digest-3".to_string(),
        clean_host: true,
        ambiguity_detected: false,
        broker_reconciliation_clean: true,
        reviewed_waiver_id: None,
        max_backup_age_minutes: 30,
        current_minute: 500,
    }
}

fn base_migration_request() -> MigrationExecutionRequest {
    MigrationExecutionRequest {
        execution_id: "migration-incremental-upgrade".to_string(),
        from: VersionSet {
            runtime: 1,
            snapshot: 1,
            journal: 1,
        },
        to: VersionSet {
            runtime: 2,
            snapshot: 2,
            journal: 2,
        },
        backup_artifact_id: "backup-20260327T1950".to_string(),
        digest_frontier_id: "digest-3".to_string(),
        operator_approval_id: "approval-20260327T2001".to_string(),
        state_store_clean: true,
        backup_verified: true,
    }
}

/// Built-in restore verification scenarios used by tests and smoke drills.
pub fn sample_restore_request(name: &str) -> Option<RestoreExecutionRequest> {
    let mut request = base_restore_request();
    match name {
        "happy-path" => Some(request),
        "frontier-mismatch" => {
            request.expected_frontier_digest = "digest-9".to_string();
            Some(request)
        }
        "stale-backup" => {
            request.current_minute = 560;
            Some(request)
        }
        "ambiguous-state" => {
            request.ambiguity_detected = true;
            Some(request)
        }
        "dirty-reconciliation" => {
            request.broker_reconciliation_clean = false;
            Some(request)
        }
        _ => None,
    }
}

/// Built-in migration scenarios used by tests and smoke drills.
pub fn sample_migration_request(name: &str) -> Option<MigrationExecutionRequest> {
    let mut request = base_migration_request();
    match name {
        "incremental-upgrade" => Some(request),
        "unsupported-skip" => {
            request.to.runtime = 3;
            Some(request)
        }
        "downgrade" => {
            request.to.runtime = 0;
            Some(request)
        }
        "dirty-state-store" => {
            request.state_store_clean = false;
            Some(request)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        MigrationStatus, RecoveryDisposition, execute_migration, sample_migration_request,
        sample_restore_request, verify_restore_execution,
    };

    #[test]
    fn restore_verification_passes_when_frontier_and_durability_align() {
        let request =
            sample_restore_request("happy-path").expect("happy-path scenario should exist");
        let report = verify_restore_execution(&request);

        assert_eq!(RecoveryDisposition::SafeResume, report.disposition);
        assert_eq!("RESTORE_MATERIAL_VERIFIED", report.reason_code);
        assert_eq!("digest-3", report.verified_frontier_digest);
    }

    #[test]
    fn restore_verification_halts_on_frontier_mismatch() {
        let request = sample_restore_request("frontier-mismatch")
            .expect("frontier mismatch scenario should exist");
        let report = verify_restore_execution(&request);

        assert_eq!(RecoveryDisposition::SafeHalt, report.disposition);
        assert_eq!("RESTORE_DIGEST_FRONTIER_MISMATCH", report.reason_code);
    }

    #[test]
    fn restore_verification_halts_on_stale_backup() {
        let request =
            sample_restore_request("stale-backup").expect("stale backup scenario should exist");
        let report = verify_restore_execution(&request);

        assert_eq!(RecoveryDisposition::SafeHalt, report.disposition);
        assert_eq!("RESTORE_BACKUP_TOO_STALE", report.reason_code);
    }

    #[test]
    fn restore_verification_halts_on_dirty_reconciliation_without_waiver() {
        let request = sample_restore_request("dirty-reconciliation")
            .expect("dirty reconciliation scenario should exist");
        let report = verify_restore_execution(&request);

        assert_eq!(RecoveryDisposition::SafeHalt, report.disposition);
        assert_eq!("RESTORE_RECONCILIATION_REVIEW_REQUIRED", report.reason_code);
    }

    #[test]
    fn migration_executes_incremental_upgrade_with_prerequisites_met() {
        let request = sample_migration_request("incremental-upgrade")
            .expect("incremental upgrade scenario should exist");
        let report = execute_migration(&request);

        assert_eq!(MigrationStatus::Executed, report.status);
        assert_eq!("MIGRATION_EXECUTED", report.reason_code);
        assert_eq!(3, report.applied_steps.len());
    }

    #[test]
    fn migration_rejects_version_skips() {
        let request = sample_migration_request("unsupported-skip")
            .expect("unsupported skip scenario should exist");
        let report = execute_migration(&request);

        assert_eq!(MigrationStatus::Rejected, report.status);
        assert_eq!("MIGRATION_UNSUPPORTED_VERSION_SKIP", report.reason_code);
    }

    #[test]
    fn migration_rejects_downgrades() {
        let request =
            sample_migration_request("downgrade").expect("downgrade scenario should exist");
        let report = execute_migration(&request);

        assert_eq!(MigrationStatus::Rejected, report.status);
        assert_eq!("MIGRATION_DOWNGRADE_REJECTED", report.reason_code);
    }

    #[test]
    fn migration_halts_when_prerequisites_are_not_met() {
        let request = sample_migration_request("dirty-state-store")
            .expect("dirty state store scenario should exist");
        let report = execute_migration(&request);

        assert_eq!(MigrationStatus::SafeHalt, report.status);
        assert_eq!("MIGRATION_PREREQUISITES_NOT_MET", report.reason_code);
        assert!(report.safe_halt_required);
    }
}
