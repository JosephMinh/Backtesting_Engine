//! Minimal out-of-band emergency control contracts.
//!
//! `guardian` remains intentionally small and separate from `opsd`. This crate
//! encodes that it owns emergency actions and evidence, not strategy or broker
//! lifecycle state.

/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "minimal out-of-band emergency control process";

/// The only actions guardian may issue independently.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GuardianAction {
    CancelAllOpenOrders,
    FlattenAllPositions,
}

/// Artifact and authority boundaries for the guardian process.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct GuardianBoundary {
    pub readable_artifact_roots: &'static [&'static str],
    pub writable_artifact_roots: &'static [&'static str],
    pub allowed_actions: &'static [GuardianAction],
    pub owns_strategy_state: bool,
}

/// Guardian can read approved control packets but only writes emergency evidence.
pub const GUARDIAN_BOUNDARY: GuardianBoundary = GuardianBoundary {
    readable_artifact_roots: &["promotion_packets", "readiness_packets"],
    writable_artifact_roots: &["control_action_evidence"],
    allowed_actions: &[
        GuardianAction::CancelAllOpenOrders,
        GuardianAction::FlattenAllPositions,
    ],
    owns_strategy_state: false,
};

#[cfg(test)]
mod tests {
    use super::{GUARDIAN_BOUNDARY, GuardianAction};

    #[test]
    fn guardian_only_allows_emergency_actions() {
        assert_eq!(
            &[
                GuardianAction::CancelAllOpenOrders,
                GuardianAction::FlattenAllPositions,
            ],
            GUARDIAN_BOUNDARY.allowed_actions
        );
    }

    #[test]
    fn guardian_does_not_own_strategy_state() {
        let boundary = GUARDIAN_BOUNDARY;
        assert!(!boundary.owns_strategy_state);
        assert_eq!(
            &["control_action_evidence"],
            boundary.writable_artifact_roots
        );
    }
}
