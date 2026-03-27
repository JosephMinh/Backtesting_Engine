//! Supervisor and health-automation boundary contracts.
//!
//! `watchdog` supervises process health and restart behavior without owning
//! strategy or reconciliation state.

pub mod health;
pub mod recovery;

pub use health::{
    ActivationPreflightSummary, BackupFreshnessObservation, BackupFreshnessReport,
    ClockHealthObservation, ClockHealthReport, ClockSyncState, HealthState,
    RestoreDrillObservation, RestoreDrillReport, SecretDeliverySurface, SecretHealthObservation,
    SecretHealthReport, evaluate_activation_preflight, evaluate_backup_freshness,
    evaluate_clock_health, evaluate_restore_drill, evaluate_secret_health,
    sample_activation_preflight_inputs, sample_clock_health_observation,
    sample_secret_health_observation, write_activation_preflight_artifacts,
    write_clock_health_artifacts, write_secret_health_artifacts,
};
pub use recovery::{
    BackupManifest, DurabilityEvidence, JournalDigestRecord, MigrationDomain,
    MigrationExecutionReport, MigrationExecutionRequest, MigrationStatus, RecoveryDisposition,
    RestoreExecutionReport, RestoreExecutionRequest, SnapshotManifest, VersionSet,
    execute_migration, sample_migration_request, sample_restore_request, verify_restore_execution,
    write_migration_artifacts, write_restore_artifacts,
};

/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "supervisor and health automation";

/// Runtime targets that the watchdog is expected to supervise.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SupervisionTarget {
    Opsd,
    Guardian,
    BrokerGateway,
}

/// Artifact roots watchdog may read while supervising recovery and migration.
pub const WATCHDOG_READABLE_ARTIFACT_ROOTS: &[&str] = &[
    "health_snapshots",
    "backup_manifests",
    "snapshot_manifests",
    "journal_digests",
    "migration_manifests",
];

/// Artifact roots watchdog may write while supervising recovery and migration.
pub const WATCHDOG_WRITABLE_ARTIFACT_ROOTS: &[&str] =
    &["health_reports", "restore_drills", "migration_reports"];

/// Artifact and authority boundaries for the watchdog process.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WatchdogBoundary {
    pub readable_artifact_roots: &'static [&'static str],
    pub writable_artifact_roots: &'static [&'static str],
    pub supervision_targets: &'static [SupervisionTarget],
    pub owns_economic_state: bool,
}

/// Watchdog reads health snapshots and writes supervision evidence only.
pub const WATCHDOG_BOUNDARY: WatchdogBoundary = WatchdogBoundary {
    readable_artifact_roots: WATCHDOG_READABLE_ARTIFACT_ROOTS,
    writable_artifact_roots: WATCHDOG_WRITABLE_ARTIFACT_ROOTS,
    supervision_targets: &[
        SupervisionTarget::Opsd,
        SupervisionTarget::Guardian,
        SupervisionTarget::BrokerGateway,
    ],
    owns_economic_state: false,
};

#[cfg(test)]
mod tests {
    use super::{
        SupervisionTarget, WATCHDOG_BOUNDARY, WATCHDOG_READABLE_ARTIFACT_ROOTS,
        WATCHDOG_WRITABLE_ARTIFACT_ROOTS,
    };

    #[test]
    fn watchdog_supervises_the_expected_runtime_targets() {
        assert_eq!(
            &[
                SupervisionTarget::Opsd,
                SupervisionTarget::Guardian,
                SupervisionTarget::BrokerGateway,
            ],
            WATCHDOG_BOUNDARY.supervision_targets
        );
    }

    #[test]
    fn watchdog_does_not_own_economic_state() {
        let boundary = WATCHDOG_BOUNDARY;
        assert!(!boundary.owns_economic_state);
        assert_eq!(
            WATCHDOG_WRITABLE_ARTIFACT_ROOTS,
            boundary.writable_artifact_roots
        );
    }

    #[test]
    fn watchdog_boundary_covers_restore_and_migration_artifacts() {
        let boundary = WATCHDOG_BOUNDARY;
        assert_eq!(
            WATCHDOG_READABLE_ARTIFACT_ROOTS,
            boundary.readable_artifact_roots
        );
        assert!(boundary.writable_artifact_roots.contains(&"restore_drills"));
        assert!(
            boundary
                .writable_artifact_roots
                .contains(&"migration_reports")
        );
    }
}
