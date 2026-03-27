//! Supervisor and health-automation boundary contracts.
//!
//! `watchdog` supervises process health and restart behavior without owning
//! strategy or reconciliation state.

/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "supervisor and health automation";

/// Runtime targets that the watchdog is expected to supervise.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SupervisionTarget {
    Opsd,
    Guardian,
    BrokerGateway,
}

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
    readable_artifact_roots: &["health_snapshots"],
    writable_artifact_roots: &["health_reports"],
    supervision_targets: &[
        SupervisionTarget::Opsd,
        SupervisionTarget::Guardian,
        SupervisionTarget::BrokerGateway,
    ],
    owns_economic_state: false,
};

#[cfg(test)]
mod tests {
    use super::{SupervisionTarget, WATCHDOG_BOUNDARY};

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
        assert_eq!(&["health_reports"], boundary.writable_artifact_roots);
    }
}
