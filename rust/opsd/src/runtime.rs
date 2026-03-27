use std::collections::BTreeMap;

use crate::{
    BoundedMailbox, MailboxBackpressureDiagnostic, MailboxSnapshot, MessageKind, MessagePriority,
    OpsdModule, RuntimeControlAction, RuntimeMessage, RuntimeStateSurface, module_boundary,
    state_owner,
};

/// Operator request routed into the daemon through `ops_http`.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OperatorRequest {
    pub correlation_id: String,
    pub target: OpsdModule,
    pub action: RuntimeControlAction,
    pub operator_id: String,
}

impl OperatorRequest {
    /// Creates a new operator request routed through `ops_http`.
    pub fn new(
        correlation_id: impl Into<String>,
        target: OpsdModule,
        action: RuntimeControlAction,
        operator_id: impl Into<String>,
    ) -> Self {
        Self {
            correlation_id: correlation_id.into(),
            target,
            action,
            operator_id: operator_id.into(),
        }
    }
}

/// Accepted dispatch summary retained for startup and smoke diagnostics.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DispatchReceipt {
    pub target: OpsdModule,
    pub priority: MessagePriority,
    pub accepted_depth: usize,
    pub correlation_id: String,
    pub message_kind: MessageKind,
}

/// Failure returned when a dispatch cannot be accepted.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DispatchError {
    UnauthorizedControlAction {
        target: OpsdModule,
        action: RuntimeControlAction,
    },
    Backpressure(MailboxBackpressureDiagnostic),
}

/// Per-module startup handoff detail retained for diagnostics.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StartupStep {
    pub module: OpsdModule,
    pub standard_mailbox_capacity: usize,
    pub high_priority_mailbox_capacity: usize,
    pub owned_state_surfaces: Vec<RuntimeStateSurface>,
}

/// Runtime startup report retained for handoff diagnostics.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StartupReport {
    pub booted_modules: Vec<OpsdModule>,
    pub startup_steps: Vec<StartupStep>,
}

/// Operator-facing health report for the in-process daemon.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HealthReport {
    pub mailboxes: Vec<MailboxSnapshot>,
    pub dispatch_count: usize,
    pub state_owners: Vec<(RuntimeStateSurface, OpsdModule)>,
}

/// Deterministic in-process daemon runtime with explicit bounded mailboxes.
#[derive(Clone, Debug)]
pub struct OpsdRuntime {
    mailboxes: BTreeMap<OpsdModule, BoundedMailbox>,
    startup_report: StartupReport,
    dispatch_log: Vec<DispatchReceipt>,
}

impl OpsdRuntime {
    /// Boots the daemon topology with canonical mailbox capacities and state ownership.
    pub fn boot() -> Self {
        let mut mailboxes = BTreeMap::new();
        let mut startup_steps = Vec::new();
        let mut booted_modules = Vec::new();

        for module in [
            OpsdModule::MarketData,
            OpsdModule::StrategyRunner,
            OpsdModule::Risk,
            OpsdModule::Broker,
            OpsdModule::StateStore,
            OpsdModule::Reconciliation,
            OpsdModule::OpsHttp,
        ] {
            let boundary = module_boundary(module);
            mailboxes.insert(
                module,
                BoundedMailbox::new(
                    module,
                    boundary.standard_mailbox_capacity,
                    boundary.high_priority_mailbox_capacity,
                ),
            );
            startup_steps.push(StartupStep {
                module,
                standard_mailbox_capacity: boundary.standard_mailbox_capacity,
                high_priority_mailbox_capacity: boundary.high_priority_mailbox_capacity,
                owned_state_surfaces: boundary.owned_state_surfaces.to_vec(),
            });
            booted_modules.push(module);
        }

        Self {
            mailboxes,
            startup_report: StartupReport {
                booted_modules,
                startup_steps,
            },
            dispatch_log: Vec::new(),
        }
    }

    /// Returns the startup handoff diagnostics for the daemon.
    pub const fn startup_report(&self) -> &StartupReport {
        &self.startup_report
    }

    /// Returns the current mailbox snapshot for a specific module.
    pub fn mailbox_snapshot(&self, module: OpsdModule) -> MailboxSnapshot {
        self.mailboxes
            .get(&module)
            .expect("all modules must own a mailbox")
            .snapshot()
    }

    /// Returns an operator-facing health report for `ops_http`.
    pub fn health_report(&self) -> HealthReport {
        let mut mailboxes = Vec::new();
        for module in self.startup_report.booted_modules.iter().copied() {
            mailboxes.push(self.mailbox_snapshot(module));
        }
        let mut state_owners = Vec::new();
        for surface in [
            RuntimeStateSurface::NormalizedMarketState,
            RuntimeStateSurface::BundleDecisionState,
            RuntimeStateSurface::TradingEligibilityState,
            RuntimeStateSurface::ExposureState,
            RuntimeStateSurface::Orders,
            RuntimeStateSurface::Positions,
            RuntimeStateSurface::Fills,
            RuntimeStateSurface::OrderIntentMappings,
            RuntimeStateSurface::BrokerSessionState,
            RuntimeStateSurface::ReadinessState,
            RuntimeStateSurface::ReconciliationState,
            RuntimeStateSurface::SnapshotStorage,
            RuntimeStateSurface::AppendOnlyJournal,
        ] {
            state_owners.push((surface, state_owner(surface)));
        }
        HealthReport {
            mailboxes,
            dispatch_count: self.dispatch_log.len(),
            state_owners,
        }
    }

    /// Routes a control action through `ops_http` into the target authoritative module.
    pub fn handle_operator_request(
        &mut self,
        request: OperatorRequest,
    ) -> Result<DispatchReceipt, DispatchError> {
        let boundary = module_boundary(request.target);
        if !boundary.allowed_control_actions.contains(&request.action) {
            return Err(DispatchError::UnauthorizedControlAction {
                target: request.target,
                action: request.action,
            });
        }
        let message = RuntimeMessage::control_action(
            request.correlation_id.clone(),
            request.target,
            request.action,
            request.operator_id,
        );
        self.dispatch_message(message)
    }

    /// Routes a standard health probe through `ops_http`.
    pub fn enqueue_health_probe(
        &mut self,
        target: OpsdModule,
        correlation_id: impl Into<String>,
    ) -> Result<DispatchReceipt, DispatchError> {
        let message = RuntimeMessage::health_probe(correlation_id, target);
        self.dispatch_message(message)
    }

    /// Routes high-priority reconciliation traffic into the reconciliation module.
    pub fn publish_reconciliation_tick(
        &mut self,
        correlation_id: impl Into<String>,
        source: OpsdModule,
        summary: impl Into<String>,
    ) -> Result<DispatchReceipt, DispatchError> {
        let message = RuntimeMessage::reconciliation_tick(correlation_id, source, summary);
        self.dispatch_message(message)
    }

    /// Drains the next available message for a module, preserving high-priority ordering.
    pub fn drain_next(&mut self, module: OpsdModule) -> Option<RuntimeMessage> {
        self.mailboxes
            .get_mut(&module)
            .expect("all modules must own a mailbox")
            .pop_next()
    }

    fn dispatch_message(
        &mut self,
        message: RuntimeMessage,
    ) -> Result<DispatchReceipt, DispatchError> {
        let target = message.target;
        let priority = message.priority;
        let message_kind = message.kind.clone();
        let correlation_id = message.correlation_id.clone();
        let mailbox = self
            .mailboxes
            .get_mut(&target)
            .expect("all modules must own a mailbox");
        mailbox
            .try_send(message)
            .map_err(DispatchError::Backpressure)?;
        let snapshot = mailbox.snapshot();
        let accepted_depth = match priority {
            MessagePriority::Standard => snapshot.standard_depth,
            MessagePriority::High => snapshot.high_priority_depth,
        };
        let receipt = DispatchReceipt {
            target,
            priority,
            accepted_depth,
            correlation_id,
            message_kind,
        };
        self.dispatch_log.push(receipt.clone());
        Ok(receipt)
    }
}

#[cfg(test)]
mod tests {
    use crate::{MessageKind, MessagePriority};

    use super::{DispatchError, OperatorRequest, OpsdRuntime};
    use crate::{OpsdModule, RuntimeControlAction, RuntimeStateSurface, module_boundary};

    #[test]
    fn startup_report_covers_all_named_runtime_modules() {
        let runtime = OpsdRuntime::boot();
        let report = runtime.startup_report();
        assert_eq!(7, report.booted_modules.len());
        assert_eq!(OpsdModule::OpsHttp, report.booted_modules[6]);
        assert!(
            report
                .startup_steps
                .iter()
                .any(|step| step.module == OpsdModule::Reconciliation)
        );
    }

    #[test]
    fn operator_requests_route_only_to_authorized_modules() {
        let mut runtime = OpsdRuntime::boot();
        let result = runtime.handle_operator_request(OperatorRequest::new(
            "bad-1",
            OpsdModule::StrategyRunner,
            RuntimeControlAction::CancelOpenOrders,
            "operator-7",
        ));
        assert_eq!(
            Err(DispatchError::UnauthorizedControlAction {
                target: OpsdModule::StrategyRunner,
                action: RuntimeControlAction::CancelOpenOrders,
            }),
            result
        );
    }

    #[test]
    fn ops_http_routes_priority_control_without_shared_mutable_state() {
        let mut runtime = OpsdRuntime::boot();
        runtime
            .enqueue_health_probe(OpsdModule::Broker, "probe-1")
            .expect("health probe should fit");
        let receipt = runtime
            .handle_operator_request(OperatorRequest::new(
                "ctl-1",
                OpsdModule::Broker,
                RuntimeControlAction::CancelOpenOrders,
                "operator-9",
            ))
            .expect("control request should fit");

        assert_eq!(OpsdModule::Broker, receipt.target);
        assert_eq!(MessagePriority::High, receipt.priority);

        let first = runtime
            .drain_next(OpsdModule::Broker)
            .expect("broker should drain high-priority control first");
        let second = runtime
            .drain_next(OpsdModule::Broker)
            .expect("broker should then drain standard health probe");

        assert_eq!(
            MessageKind::ControlAction(RuntimeControlAction::CancelOpenOrders),
            first.kind
        );
        assert_eq!(MessageKind::HealthProbe, second.kind);
    }

    #[test]
    fn reconciliation_traffic_has_reserved_high_priority_path() {
        let mut runtime = OpsdRuntime::boot();
        let receipt = runtime
            .publish_reconciliation_tick(
                "reconcile-1",
                OpsdModule::StateStore,
                "state-store handoff after journal barrier",
            )
            .expect("reconciliation tick should fit");

        assert_eq!(OpsdModule::Reconciliation, receipt.target);
        assert_eq!(MessagePriority::High, receipt.priority);

        let drained = runtime
            .drain_next(OpsdModule::Reconciliation)
            .expect("reconciliation mailbox should drain tick");
        assert_eq!(MessageKind::ReconciliationTick, drained.kind);
        assert_eq!(OpsdModule::StateStore, drained.source);
    }

    #[test]
    fn health_report_keeps_single_writer_state_ownership_visible() {
        let runtime = OpsdRuntime::boot();
        let report = runtime.health_report();
        assert_eq!(13, report.state_owners.len());
        assert!(
            report
                .state_owners
                .contains(&(RuntimeStateSurface::Orders, OpsdModule::Broker))
        );
        assert!(report.state_owners.contains(&(
            RuntimeStateSurface::ReadinessState,
            OpsdModule::Reconciliation
        )));
    }

    #[test]
    fn mailbox_backpressure_returns_structured_diagnostic() {
        let mut runtime = OpsdRuntime::boot();
        for idx in 0..module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity {
            runtime
                .handle_operator_request(OperatorRequest::new(
                    format!("ctl-{idx}"),
                    OpsdModule::Broker,
                    RuntimeControlAction::CancelOpenOrders,
                    "operator-11",
                ))
                .expect("broker high-priority slot should fit");
        }
        let error = runtime
            .handle_operator_request(OperatorRequest::new(
                "ctl-overflow",
                OpsdModule::Broker,
                RuntimeControlAction::FlattenPositions,
                "operator-11",
            ))
            .expect_err("overflow control action should return a diagnostic");

        let DispatchError::Backpressure(diagnostic) = error else {
            panic!("expected backpressure diagnostic");
        };
        assert_eq!(OpsdModule::Broker, diagnostic.mailbox_owner);
        assert_eq!(MessagePriority::High, diagnostic.priority);
        assert_eq!(
            module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity,
            diagnostic.capacity
        );
    }
}
