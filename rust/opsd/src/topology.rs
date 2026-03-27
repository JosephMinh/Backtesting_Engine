use backtesting_engine_kernels::ApprovedArtifactRef;

/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "operational daemon modules and state-ownership boundaries";

/// Logical modules that compose the operational daemon.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
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
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::MarketData => "market_data",
            Self::StrategyRunner => "strategy_runner",
            Self::Risk => "risk",
            Self::Broker => "broker",
            Self::StateStore => "state_store",
            Self::Reconciliation => "reconciliation",
            Self::OpsHttp => "ops_http",
        }
    }

    /// Whether the module owns at least one authoritative runtime state surface.
    pub const fn owns_runtime_state(self) -> bool {
        !matches!(self, Self::OpsHttp)
    }
}

/// Authoritative runtime state surfaces inside `opsd`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RuntimeStateSurface {
    NormalizedMarketState,
    BundleDecisionState,
    CompiledSessionTopology,
    TradingEligibilityState,
    ExposureState,
    Orders,
    Positions,
    Fills,
    OrderIntentMappings,
    BrokerSessionState,
    AccountingLedgerState,
    SessionCloseArtifacts,
    ReadinessState,
    ReconciliationState,
    SnapshotStorage,
    AppendOnlyJournal,
}

impl RuntimeStateSurface {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::NormalizedMarketState => "normalized_market_state",
            Self::BundleDecisionState => "bundle_decision_state",
            Self::CompiledSessionTopology => "compiled_session_topology",
            Self::TradingEligibilityState => "trading_eligibility_state",
            Self::ExposureState => "exposure_state",
            Self::Orders => "orders",
            Self::Positions => "positions",
            Self::Fills => "fills",
            Self::OrderIntentMappings => "order_intent_mappings",
            Self::BrokerSessionState => "broker_session_state",
            Self::AccountingLedgerState => "accounting_ledger_state",
            Self::SessionCloseArtifacts => "session_close_artifacts",
            Self::ReadinessState => "readiness_state",
            Self::ReconciliationState => "reconciliation_state",
            Self::SnapshotStorage => "snapshot_storage",
            Self::AppendOnlyJournal => "append_only_journal",
        }
    }
}

/// Control actions that `ops_http` may relay to authoritative modules.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RuntimeControlAction {
    HaltNewOrders,
    AssertKillSwitch,
    CancelOpenOrders,
    FlattenPositions,
    MarkSessionNotReady,
    PublishSessionReadinessPacket,
}

impl RuntimeControlAction {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::HaltNewOrders => "halt_new_orders",
            Self::AssertKillSwitch => "assert_kill_switch",
            Self::CancelOpenOrders => "cancel_open_orders",
            Self::FlattenPositions => "flatten_positions",
            Self::MarkSessionNotReady => "mark_session_not_ready",
            Self::PublishSessionReadinessPacket => "publish_session_readiness_packet",
        }
    }
}

/// Crate-level contract for artifact reads and evidence writes.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct OpsdBoundary {
    pub readable_artifact_roots: &'static [&'static str],
    pub writable_artifact_roots: &'static [&'static str],
    pub modules: &'static [OpsdModule],
}

/// Per-module daemon contract.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ModuleBoundary {
    pub module: OpsdModule,
    pub title: &'static str,
    pub responsibilities: &'static [&'static str],
    pub owned_state_surfaces: &'static [RuntimeStateSurface],
    pub allowed_control_actions: &'static [RuntimeControlAction],
    pub standard_mailbox_capacity: usize,
    pub high_priority_mailbox_capacity: usize,
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

/// Authoritative runtime state surfaces inside the daemon.
pub const ALL_STATE_SURFACES: &[RuntimeStateSurface] = &[
    RuntimeStateSurface::NormalizedMarketState,
    RuntimeStateSurface::BundleDecisionState,
    RuntimeStateSurface::CompiledSessionTopology,
    RuntimeStateSurface::TradingEligibilityState,
    RuntimeStateSurface::ExposureState,
    RuntimeStateSurface::Orders,
    RuntimeStateSurface::Positions,
    RuntimeStateSurface::Fills,
    RuntimeStateSurface::OrderIntentMappings,
    RuntimeStateSurface::BrokerSessionState,
    RuntimeStateSurface::AccountingLedgerState,
    RuntimeStateSurface::SessionCloseArtifacts,
    RuntimeStateSurface::ReadinessState,
    RuntimeStateSurface::ReconciliationState,
    RuntimeStateSurface::SnapshotStorage,
    RuntimeStateSurface::AppendOnlyJournal,
];

/// Minimal runtime boundary for the first Rust daemon workspace.
pub const OPSD_BOUNDARY: OpsdBoundary = OpsdBoundary {
    readable_artifact_roots: OPSD_READABLE_ROOTS,
    writable_artifact_roots: OPSD_WRITABLE_ROOTS,
    modules: OPSD_MODULES,
};

/// Canonical module boundaries aligned with the Python runtime contract.
pub const OPSD_MODULE_BOUNDARIES: &[ModuleBoundary] = &[
    ModuleBoundary {
        module: OpsdModule::MarketData,
        title: "opsd.market_data",
        responsibilities: &[
            "Own the latest normalized market state.",
            "Publish market-state updates to bounded internal mailboxes.",
        ],
        owned_state_surfaces: &[RuntimeStateSurface::NormalizedMarketState],
        allowed_control_actions: &[],
        standard_mailbox_capacity: 32,
        high_priority_mailbox_capacity: 4,
    },
    ModuleBoundary {
        module: OpsdModule::StrategyRunner,
        title: "opsd.strategy_runner",
        responsibilities: &[
            "Own per-bundle decision state.",
            "Translate approved bundle state into order intents without mutating broker state.",
        ],
        owned_state_surfaces: &[RuntimeStateSurface::BundleDecisionState],
        allowed_control_actions: &[],
        standard_mailbox_capacity: 32,
        high_priority_mailbox_capacity: 4,
    },
    ModuleBoundary {
        module: OpsdModule::Risk,
        title: "opsd.risk",
        responsibilities: &[
            "Own trading eligibility and exposure state.",
            "Assert kill-switch and trade-halt decisions before trading becomes active.",
        ],
        owned_state_surfaces: &[
            RuntimeStateSurface::TradingEligibilityState,
            RuntimeStateSurface::ExposureState,
        ],
        allowed_control_actions: &[
            RuntimeControlAction::HaltNewOrders,
            RuntimeControlAction::AssertKillSwitch,
        ],
        standard_mailbox_capacity: 16,
        high_priority_mailbox_capacity: 4,
    },
    ModuleBoundary {
        module: OpsdModule::Broker,
        title: "opsd.broker",
        responsibilities: &[
            "Own order-intent to broker-order mappings and broker-session state.",
            "Own routine order, fill, and position state used by the live lane.",
        ],
        owned_state_surfaces: &[
            RuntimeStateSurface::Orders,
            RuntimeStateSurface::Positions,
            RuntimeStateSurface::Fills,
            RuntimeStateSurface::OrderIntentMappings,
            RuntimeStateSurface::BrokerSessionState,
        ],
        allowed_control_actions: &[
            RuntimeControlAction::CancelOpenOrders,
            RuntimeControlAction::FlattenPositions,
        ],
        standard_mailbox_capacity: 32,
        high_priority_mailbox_capacity: 2,
    },
    ModuleBoundary {
        module: OpsdModule::StateStore,
        title: "opsd.state_store",
        responsibilities: &[
            "Own snapshots and the append-only journal.",
            "Preserve runtime evidence for replay, recovery, and audit.",
        ],
        owned_state_surfaces: &[
            RuntimeStateSurface::SnapshotStorage,
            RuntimeStateSurface::AppendOnlyJournal,
        ],
        allowed_control_actions: &[],
        standard_mailbox_capacity: 32,
        high_priority_mailbox_capacity: 4,
    },
    ModuleBoundary {
        module: OpsdModule::Reconciliation,
        title: "opsd.reconciliation",
        responsibilities: &[
            "Own compiled session topology, the internal accounting ledger, session-close artifacts, readiness state, and authoritative reconciliation status.",
            "Publish next-session readiness decisions after runtime, schedule, ledger, and broker checks reconcile.",
        ],
        owned_state_surfaces: &[
            RuntimeStateSurface::CompiledSessionTopology,
            RuntimeStateSurface::AccountingLedgerState,
            RuntimeStateSurface::SessionCloseArtifacts,
            RuntimeStateSurface::ReadinessState,
            RuntimeStateSurface::ReconciliationState,
        ],
        allowed_control_actions: &[
            RuntimeControlAction::MarkSessionNotReady,
            RuntimeControlAction::PublishSessionReadinessPacket,
        ],
        standard_mailbox_capacity: 16,
        high_priority_mailbox_capacity: 4,
    },
    ModuleBoundary {
        module: OpsdModule::OpsHttp,
        title: "opsd.ops_http",
        responsibilities: &[
            "Expose operator and automation ingress for opsd.",
            "Relay requests into authoritative internal modules without owning economic state.",
        ],
        owned_state_surfaces: &[],
        allowed_control_actions: &[],
        standard_mailbox_capacity: 16,
        high_priority_mailbox_capacity: 4,
    },
];

/// Returns the canonical boundary for the module.
pub fn module_boundary(module: OpsdModule) -> &'static ModuleBoundary {
    OPSD_MODULE_BOUNDARIES
        .iter()
        .find(|boundary| boundary.module == module)
        .expect("all opsd modules must have a canonical boundary")
}

/// Returns the authoritative owner for a runtime state surface.
pub const fn state_owner(surface: RuntimeStateSurface) -> OpsdModule {
    match surface {
        RuntimeStateSurface::NormalizedMarketState => OpsdModule::MarketData,
        RuntimeStateSurface::BundleDecisionState => OpsdModule::StrategyRunner,
        RuntimeStateSurface::CompiledSessionTopology => OpsdModule::Reconciliation,
        RuntimeStateSurface::TradingEligibilityState | RuntimeStateSurface::ExposureState => {
            OpsdModule::Risk
        }
        RuntimeStateSurface::Orders
        | RuntimeStateSurface::Positions
        | RuntimeStateSurface::Fills
        | RuntimeStateSurface::OrderIntentMappings
        | RuntimeStateSurface::BrokerSessionState => OpsdModule::Broker,
        RuntimeStateSurface::AccountingLedgerState
        | RuntimeStateSurface::SessionCloseArtifacts
        | RuntimeStateSurface::ReadinessState
        | RuntimeStateSurface::ReconciliationState => OpsdModule::Reconciliation,
        RuntimeStateSurface::SnapshotStorage | RuntimeStateSurface::AppendOnlyJournal => {
            OpsdModule::StateStore
        }
    }
}

/// Returns whether an approved artifact reference is readable by `opsd`.
pub fn artifact_ingress_allowed(reference: &ApprovedArtifactRef) -> bool {
    OPSD_READABLE_ROOTS.contains(&reference.root())
}

#[cfg(test)]
mod tests {
    use backtesting_engine_kernels::ApprovedArtifactRef;

    use super::{
        ALL_STATE_SURFACES, OPSD_BOUNDARY, OPSD_MODULE_BOUNDARIES, OPSD_MODULES,
        OPSD_READABLE_ROOTS, OPSD_WRITABLE_ROOTS, OpsdModule, RuntimeStateSurface,
        artifact_ingress_allowed, module_boundary, state_owner,
    };

    #[test]
    fn boundary_preserves_runtime_plan_module_order() {
        assert_eq!(
            &[
                OpsdModule::MarketData,
                OpsdModule::StrategyRunner,
                OpsdModule::Risk,
                OpsdModule::Broker,
                OpsdModule::StateStore,
                OpsdModule::Reconciliation,
                OpsdModule::OpsHttp,
            ],
            OPSD_MODULES
        );
        assert_eq!(OPSD_MODULES, OPSD_BOUNDARY.modules);
        assert_eq!(7, OPSD_MODULE_BOUNDARIES.len());
    }

    #[test]
    fn every_runtime_state_surface_has_a_single_authoritative_owner() {
        for surface in ALL_STATE_SURFACES {
            let owner = state_owner(*surface);
            let boundary = module_boundary(owner);
            assert!(boundary.owned_state_surfaces.contains(surface));
        }
    }

    #[test]
    fn ops_http_keeps_state_ownership_empty() {
        let boundary = module_boundary(OpsdModule::OpsHttp);
        assert!(!boundary.module.owns_runtime_state());
        assert!(boundary.owned_state_surfaces.is_empty());
    }

    #[test]
    fn artifact_ingress_reuses_kernel_approved_roots() {
        let artifact = ApprovedArtifactRef::new("signal_kernels/gold_signal.v1")
            .expect("signal kernel path should validate");
        assert!(artifact_ingress_allowed(&artifact));
        assert_eq!(OPSD_READABLE_ROOTS, OPSD_BOUNDARY.readable_artifact_roots);
        assert_eq!(OPSD_WRITABLE_ROOTS, OPSD_BOUNDARY.writable_artifact_roots);
    }

    #[test]
    fn risk_broker_and_reconciliation_keep_reserved_high_priority_mailboxes() {
        for module in [
            OpsdModule::Risk,
            OpsdModule::Broker,
            OpsdModule::Reconciliation,
        ] {
            let boundary = module_boundary(module);
            assert!(boundary.high_priority_mailbox_capacity > 0);
        }
    }

    #[test]
    fn broker_owns_all_order_execution_state() {
        for surface in [
            RuntimeStateSurface::Orders,
            RuntimeStateSurface::Positions,
            RuntimeStateSurface::Fills,
            RuntimeStateSurface::OrderIntentMappings,
            RuntimeStateSurface::BrokerSessionState,
            RuntimeStateSurface::CompiledSessionTopology,
            RuntimeStateSurface::AccountingLedgerState,
            RuntimeStateSurface::SessionCloseArtifacts,
        ] {
            let expected = if matches!(
                surface,
                RuntimeStateSurface::CompiledSessionTopology
                    | RuntimeStateSurface::AccountingLedgerState
                    | RuntimeStateSurface::SessionCloseArtifacts
            ) {
                OpsdModule::Reconciliation
            } else {
                OpsdModule::Broker
            };
            assert_eq!(expected, state_owner(surface));
        }
    }
}
