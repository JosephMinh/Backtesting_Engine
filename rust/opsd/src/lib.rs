//! Operational-daemon topology and artifact ingress contracts.
//!
//! The real runtime implementation will grow here, but this crate already
//! fixes the module list, artifact ingress rules, and state-ownership
//! vocabulary so later execution work does not have to re-decide them.

use backtesting_engine_kernels::ApprovedArtifactRef;

/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "operational daemon modules and state-ownership boundaries";

/// Logical modules that compose the operational daemon.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OpsdModule {
    MarketData,
    StrategyRunner,
    Risk,
    Broker,
    StateStore,
    Reconciliation,
    OpsHttp,
}

impl OpsdModule {
    /// Whether the module may own durable runtime state.
    pub const fn owns_runtime_state(self) -> bool {
        matches!(self, Self::StateStore | Self::Reconciliation)
    }
}

/// Crate-level contract for artifact reads and evidence writes.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct OpsdBoundary {
    pub readable_artifact_roots: &'static [&'static str],
    pub writable_artifact_roots: &'static [&'static str],
    pub modules: &'static [OpsdModule],
}

/// Approved artifact roots that `opsd` may read.
pub const OPSD_READABLE_ROOTS: &[&str] = &[
    "candidate_bundles",
    "data_profile_releases",
    "resolved_context_bundles",
    "signal_kernels",
];

/// Operational outputs `opsd` may produce.
pub const OPSD_WRITABLE_ROOTS: &[&str] = &["evidence", "readiness_packets", "runtime_state"];

/// Canonical logical modules for `opsd`.
pub const OPSD_MODULES: &[OpsdModule] = &[
    OpsdModule::MarketData,
    OpsdModule::StrategyRunner,
    OpsdModule::Risk,
    OpsdModule::Broker,
    OpsdModule::StateStore,
    OpsdModule::Reconciliation,
    OpsdModule::OpsHttp,
];

/// Minimal runtime boundary for the first Rust daemon workspace.
pub const OPSD_BOUNDARY: OpsdBoundary = OpsdBoundary {
    readable_artifact_roots: OPSD_READABLE_ROOTS,
    writable_artifact_roots: OPSD_WRITABLE_ROOTS,
    modules: OPSD_MODULES,
};

/// Returns whether an approved artifact reference is readable by `opsd`.
pub fn artifact_ingress_allowed(reference: &ApprovedArtifactRef) -> bool {
    OPSD_READABLE_ROOTS.contains(&reference.root())
}

#[cfg(test)]
mod tests {
    use backtesting_engine_kernels::ApprovedArtifactRef;

    use super::{OPSD_BOUNDARY, OpsdModule, artifact_ingress_allowed};

    #[test]
    fn opsd_reuses_kernel_artifact_references_for_ingress() {
        let artifact = ApprovedArtifactRef::new("resolved_context_bundles/live-canary.json")
            .expect("resolved context bundle path should validate");
        assert!(artifact_ingress_allowed(&artifact));
    }

    #[test]
    fn opsd_boundary_keeps_runtime_state_ownership_explicit() {
        assert!(OpsdModule::StateStore.owns_runtime_state());
        assert!(OpsdModule::Reconciliation.owns_runtime_state());
        assert!(!OpsdModule::Risk.owns_runtime_state());
        assert_eq!(7, OPSD_BOUNDARY.modules.len());
    }

    #[test]
    fn opsd_boundary_keeps_evidence_writes_separate_from_artifact_reads() {
        assert!(
            OPSD_BOUNDARY
                .readable_artifact_roots
                .contains(&"candidate_bundles")
        );
        assert!(
            OPSD_BOUNDARY
                .writable_artifact_roots
                .contains(&"readiness_packets")
        );
    }
}
