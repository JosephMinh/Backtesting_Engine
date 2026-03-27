use std::collections::BTreeMap;

use crate::{
    AccountingLedger, AuthoritativeLedgerCloseArtifact, BoundedMailbox, BrokerAdapterConfig,
    BrokerCallback, BrokerCallbackReceipt, BrokerControlRequest, BrokerMutationArtifact,
    BrokerMutationDecision, BrokerMutationEngine, BrokerMutationError, BrokerMutationKind,
    BrokerOrderIntentRequest, CompiledSessionArtifact, DailyLedgerCloseRequest,
    IntradayReconciliationArtifact, IntradayReconciliationRequest, LedgerEntryReceipt, LedgerError,
    LedgerEvent, LedgerEventRequest, MailboxBackpressureDiagnostic, MailboxSnapshot, MessageKind,
    MessagePriority, NextSessionEligibility, OpsdModule, ReadinessHistoryEntry,
    ReconciliationEngine, ReconciliationError, RuntimeControlAction, RuntimeMessage,
    RuntimeStateSurface, ScheduleCompileRequest, ScheduleError, SessionCloseArtifact,
    SessionCloseRequest, SessionReadinessPacket, SessionReadinessPacketRequest,
    SessionTopologyDecision, assemble_session_readiness_packet, compile_schedule, module_boundary,
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
    BrokerControlRequiresGovernedMutationPath {
        action: RuntimeControlAction,
    },
    BrokerMutation(BrokerMutationError),
    Ledger(Box<LedgerError>),
    Reconciliation(Box<ReconciliationError>),
    Schedule(ScheduleError),
    MissingCompiledSchedule,
    MissingSessionCloseArtifact {
        artifact_id: String,
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
    pub compiled_schedule_artifact_id: Option<String>,
    pub compiled_schedule_slice_count: usize,
    pub ledger_event_count: usize,
    pub latest_session_close_artifact_id: Option<String>,
    pub latest_intraday_reconciliation_artifact_id: Option<String>,
    pub latest_authoritative_close_artifact_id: Option<String>,
    pub latest_session_readiness_packet_id: Option<String>,
    pub latest_session_readiness_packet_digest: Option<String>,
    pub latest_session_readiness_status: Option<String>,
    pub latest_session_readiness_reason_code: Option<String>,
    pub readiness_history_len: usize,
    pub next_session_eligibility: Option<String>,
}

/// Accepted governed broker mutation paired with the runtime dispatch receipt.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerMutationReceipt {
    pub mutation_kind: BrokerMutationKind,
    pub order_intent_id: String,
    pub broker_order_ids: Vec<String>,
    pub reason_code: String,
    pub idempotent_replay: bool,
    pub retained_artifact_id: String,
    pub dispatch: DispatchReceipt,
}

/// Accepted compiled-session topology retained by the runtime.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ScheduleActivationReceipt {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub compiled_from_utc: String,
    pub compiled_to_utc: String,
    pub slice_count: usize,
    pub tradeable_slice_count: usize,
}

/// Deterministic in-process daemon runtime with explicit bounded mailboxes.
#[derive(Clone, Debug)]
pub struct OpsdRuntime {
    mailboxes: BTreeMap<OpsdModule, BoundedMailbox>,
    startup_report: StartupReport,
    dispatch_log: Vec<DispatchReceipt>,
    broker_engine: BrokerMutationEngine,
    ledger: AccountingLedger,
    reconciliation: ReconciliationEngine,
    compiled_schedule: Option<CompiledSessionArtifact>,
    session_close_artifacts: BTreeMap<String, SessionCloseArtifact>,
    latest_session_close_artifact: Option<SessionCloseArtifact>,
    readiness_history: Vec<ReadinessHistoryEntry>,
    latest_session_readiness_packet: Option<SessionReadinessPacket>,
}

impl OpsdRuntime {
    /// Boots the daemon topology with canonical mailbox capacities and state ownership.
    pub fn boot() -> Self {
        Self::boot_with_broker_adapter(BrokerAdapterConfig::default())
    }

    /// Boots the daemon topology with an explicit broker adapter configuration.
    pub fn boot_with_broker_adapter(config: BrokerAdapterConfig) -> Self {
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
            broker_engine: BrokerMutationEngine::new(config),
            ledger: AccountingLedger::new(),
            reconciliation: ReconciliationEngine::new(),
            compiled_schedule: None,
            session_close_artifacts: BTreeMap::new(),
            latest_session_close_artifact: None,
            readiness_history: Vec::new(),
            latest_session_readiness_packet: None,
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
        ] {
            state_owners.push((surface, state_owner(surface)));
        }
        HealthReport {
            mailboxes,
            dispatch_count: self.dispatch_log.len(),
            state_owners,
            compiled_schedule_artifact_id: self
                .compiled_schedule
                .as_ref()
                .map(|artifact| artifact.artifact_id.clone()),
            compiled_schedule_slice_count: self
                .compiled_schedule
                .as_ref()
                .map_or(0, |artifact| artifact.slices.len()),
            ledger_event_count: self.ledger.events().len(),
            latest_session_close_artifact_id: self
                .latest_session_close_artifact
                .as_ref()
                .map(|artifact| artifact.artifact_id.clone()),
            latest_intraday_reconciliation_artifact_id: self
                .reconciliation
                .latest_intraday_artifact()
                .map(|artifact| artifact.artifact_id.clone()),
            latest_authoritative_close_artifact_id: self
                .reconciliation
                .latest_daily_close_artifact()
                .map(|artifact| artifact.artifact_id.clone()),
            latest_session_readiness_packet_id: self
                .latest_session_readiness_packet
                .as_ref()
                .map(|packet| packet.packet_id.clone()),
            latest_session_readiness_packet_digest: self
                .latest_session_readiness_packet
                .as_ref()
                .map(|packet| packet.packet_digest.clone()),
            latest_session_readiness_status: self
                .latest_session_readiness_packet
                .as_ref()
                .map(|packet| packet.status.as_str().to_string()),
            latest_session_readiness_reason_code: self
                .latest_session_readiness_packet
                .as_ref()
                .map(|packet| packet.reason_code.clone()),
            readiness_history_len: self.readiness_history.len(),
            next_session_eligibility: self
                .reconciliation
                .latest_next_session_eligibility()
                .map(NextSessionEligibility::as_str)
                .map(str::to_string),
        }
    }

    /// Returns the currently installed compiled schedule artifact, if any.
    pub fn compiled_schedule(&self) -> Option<&CompiledSessionArtifact> {
        self.compiled_schedule.as_ref()
    }

    /// Returns retained broker mutation artifacts for operator diagnostics.
    pub fn broker_artifacts(&self) -> &[BrokerMutationArtifact] {
        self.broker_engine.artifacts()
    }

    /// Returns retained broker callback diagnostics.
    pub fn broker_callback_log(&self) -> &[BrokerCallbackReceipt] {
        self.broker_engine.callback_log()
    }

    /// Returns append-only ledger events retained by the runtime.
    pub fn ledger_events(&self) -> &[LedgerEvent] {
        self.ledger.events()
    }

    /// Returns the most recent session-close artifact retained by the runtime.
    pub fn latest_session_close_artifact(&self) -> Option<&SessionCloseArtifact> {
        self.latest_session_close_artifact.as_ref()
    }

    /// Returns the latest intraday reconciliation artifact, if any.
    pub fn latest_intraday_reconciliation_artifact(
        &self,
    ) -> Option<&IntradayReconciliationArtifact> {
        self.reconciliation.latest_intraday_artifact()
    }

    /// Returns the latest authoritative daily close artifact, if any.
    pub fn latest_authoritative_close_artifact(&self) -> Option<&AuthoritativeLedgerCloseArtifact> {
        self.reconciliation.latest_daily_close_artifact()
    }

    /// Returns the latest retained session-readiness packet, if any.
    pub fn latest_session_readiness_packet(&self) -> Option<&SessionReadinessPacket> {
        self.latest_session_readiness_packet.as_ref()
    }

    /// Returns the retained readiness history managed by the runtime.
    pub fn readiness_history(&self) -> &[ReadinessHistoryEntry] {
        &self.readiness_history
    }

    /// Routes a control action through `ops_http` into the target authoritative module.
    pub fn handle_operator_request(
        &mut self,
        request: OperatorRequest,
    ) -> Result<DispatchReceipt, DispatchError> {
        if request.target == OpsdModule::Broker {
            return Err(DispatchError::BrokerControlRequiresGovernedMutationPath {
                action: request.action,
            });
        }
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

    /// Accepts a governed order-intent mutation for the broker module.
    pub fn submit_order_intent(
        &mut self,
        request: BrokerOrderIntentRequest,
    ) -> Result<BrokerMutationReceipt, DispatchError> {
        let correlation_id = request.correlation_id.clone();
        let decision = self
            .broker_engine
            .submit_order_intent(request)
            .map_err(DispatchError::BrokerMutation)?;
        let dispatch = self.dispatch_message(RuntimeMessage::broker_mutation(
            correlation_id,
            OpsdModule::StrategyRunner,
            decision.mutation_kind,
            format!(
                "strategy_runner submitted {} as {}",
                decision.order_intent_id,
                decision.mutation_kind.as_str()
            ),
        ))?;
        Ok(BrokerMutationReceipt::from_decision(decision, dispatch))
    }

    /// Accepts a governed operator control request for the broker module.
    pub fn handle_broker_control_request(
        &mut self,
        request: BrokerControlRequest,
    ) -> Result<BrokerMutationReceipt, DispatchError> {
        let correlation_id = request.correlation_id.clone();
        let decision = self
            .broker_engine
            .apply_control_request(request)
            .map_err(DispatchError::BrokerMutation)?;
        let dispatch = self.dispatch_message(RuntimeMessage::broker_mutation(
            correlation_id,
            OpsdModule::OpsHttp,
            decision.mutation_kind,
            format!(
                "ops_http relayed {} for {}",
                decision.reason_code, decision.order_intent_id
            ),
        ))?;
        Ok(BrokerMutationReceipt::from_decision(decision, dispatch))
    }

    /// Records a broker callback against durable intent mapping state.
    pub fn record_broker_callback(
        &mut self,
        callback: BrokerCallback,
    ) -> Result<BrokerCallbackReceipt, DispatchError> {
        self.broker_engine
            .record_callback(callback)
            .map_err(DispatchError::BrokerMutation)
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

    /// Appends a machine-readable internal-ledger event.
    pub fn append_ledger_event(
        &mut self,
        request: LedgerEventRequest,
    ) -> Result<LedgerEntryReceipt, DispatchError> {
        self.ledger
            .append_event(request)
            .map_err(|error| DispatchError::Ledger(Box::new(error)))
    }

    /// Produces a durable intraday reconciliation artifact from broker-state observations.
    pub fn evaluate_intraday_reconciliation(
        &mut self,
        request: IntradayReconciliationRequest,
    ) -> Result<IntradayReconciliationArtifact, DispatchError> {
        self.reconciliation
            .reconcile_intraday(request)
            .map_err(|error| DispatchError::Reconciliation(Box::new(error)))
    }

    /// Builds the as-booked session-close artifact for the specified session.
    pub fn build_session_close_artifact(
        &mut self,
        request: SessionCloseRequest,
    ) -> Result<SessionCloseArtifact, DispatchError> {
        let artifact = self
            .ledger
            .build_session_close_artifact(request)
            .map_err(|error| DispatchError::Ledger(Box::new(error)))?;
        self.session_close_artifacts
            .insert(artifact.artifact_id.clone(), artifact.clone());
        self.latest_session_close_artifact = Some(artifact.clone());
        Ok(artifact)
    }

    /// Builds the authoritative daily close from a prior session-close artifact and broker statement set.
    pub fn build_authoritative_ledger_close(
        &mut self,
        request: DailyLedgerCloseRequest,
    ) -> Result<AuthoritativeLedgerCloseArtifact, DispatchError> {
        let Some(session_close) = self
            .session_close_artifacts
            .get(&request.session_close_artifact_id)
            .cloned()
        else {
            return Err(DispatchError::MissingSessionCloseArtifact {
                artifact_id: request.session_close_artifact_id,
            });
        };
        let scoped_events = self.ledger.scoped_events(
            &session_close.account_id,
            &session_close.symbol,
            &session_close.session_id,
        );
        self.reconciliation
            .reconcile_daily_close(request, &session_close, &scoped_events)
            .map_err(|error| DispatchError::Reconciliation(Box::new(error)))
    }

    /// Assembles and retains one explicit session-readiness packet using runtime-owned history.
    pub fn publish_session_readiness_packet(
        &mut self,
        mut request: SessionReadinessPacketRequest,
    ) -> SessionReadinessPacket {
        request.previous_history = if self.readiness_history.is_empty() {
            request.previous_history.clone()
        } else {
            self.readiness_history.clone()
        };
        let packet = assemble_session_readiness_packet(&request);
        self.readiness_history = packet.history.clone();
        self.latest_session_readiness_packet = Some(packet.clone());
        packet
    }

    /// Compiles and installs the canonical runtime session topology.
    pub fn compile_and_install_schedule(
        &mut self,
        request: ScheduleCompileRequest,
    ) -> Result<ScheduleActivationReceipt, DispatchError> {
        let artifact = compile_schedule(request).map_err(DispatchError::Schedule)?;
        Ok(self.install_compiled_schedule(artifact))
    }

    /// Installs a precompiled session topology artifact into the runtime.
    pub fn install_compiled_schedule(
        &mut self,
        artifact: CompiledSessionArtifact,
    ) -> ScheduleActivationReceipt {
        let receipt = ScheduleActivationReceipt {
            artifact_id: artifact.artifact_id.clone(),
            retained_artifact_id: artifact.retained_artifact_id.clone(),
            compiled_from_utc: artifact.compiled_from_utc.clone(),
            compiled_to_utc: artifact.compiled_to_utc.clone(),
            slice_count: artifact.slices.len(),
            tradeable_slice_count: artifact.tradeable_slice_count(),
        };
        self.compiled_schedule = Some(artifact);
        receipt
    }

    /// Evaluates the installed session topology for an instant in UTC.
    pub fn evaluate_session_topology(
        &self,
        evaluated_at_utc: &str,
    ) -> Result<SessionTopologyDecision, DispatchError> {
        let Some(artifact) = self.compiled_schedule.as_ref() else {
            return Err(DispatchError::MissingCompiledSchedule);
        };
        artifact
            .evaluate_at(evaluated_at_utc)
            .map_err(DispatchError::Schedule)
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

impl BrokerMutationReceipt {
    fn from_decision(decision: BrokerMutationDecision, dispatch: DispatchReceipt) -> Self {
        Self {
            mutation_kind: decision.mutation_kind,
            order_intent_id: decision.order_intent_id,
            broker_order_ids: decision.broker_order_ids,
            reason_code: decision.reason_code,
            idempotent_replay: decision.idempotent_replay,
            retained_artifact_id: decision.retained_artifact_id,
            dispatch,
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::{
        AuthoritativeStatementSet, BrokerCallback, BrokerCallbackKind, BrokerContractDescriptor,
        BrokerControlRequest, BrokerMutationError, BrokerOrderIntentRequest, BrokerOrderType,
        BrokerTimeInForce, CompiledSessionState, DailyLedgerCloseRequest,
        DeliveryFenceWindowDefinition, IntradayControlAction, IntradayReconciliationRequest,
        LedgerEventClass, LedgerEventRequest, MaintenanceWindowDefinition, MessageKind,
        MessagePriority, NextSessionEligibility, OrderIntentIdentity,
        PolicyOverlayWindowDefinition, ScheduleCompileRequest, SessionCalendarEntry,
        SessionCloseRequest, SessionCloseStatus, SessionDayKind, SessionReadinessStatus,
        sample_session_readiness_request,
    };

    use super::{DispatchError, OperatorRequest, OpsdRuntime};
    use crate::{OpsdModule, RuntimeControlAction, RuntimeStateSurface, module_boundary};

    fn sample_submit_request() -> BrokerOrderIntentRequest {
        BrokerOrderIntentRequest::new(
            "submit-1",
            "decision-trace-1",
            "expected-timeline-1",
            "actual-timeline-1",
            "artifact-manifest-1",
            "reason-bundle-1",
            OrderIntentIdentity::new("paper-gold-1", 41, "leg-a", "buy", "entry"),
            BrokerOrderType::Limit,
            BrokerTimeInForce::Day,
            BrokerContractDescriptor::one_oz_comex(),
        )
    }

    fn sample_control_request(action: RuntimeControlAction) -> BrokerControlRequest {
        BrokerControlRequest::new(
            "control-1",
            "operator-9",
            "decision-trace-control",
            "expected-timeline-control",
            "actual-timeline-control",
            "artifact-manifest-control",
            "reason-bundle-control",
            OrderIntentIdentity::new("paper-gold-1", 99, "broker", "flat", action.as_str()),
            action,
            "WITHDRAW_LIVE_OPERATOR_REQUEST",
        )
    }

    fn sample_schedule_request() -> ScheduleCompileRequest {
        ScheduleCompileRequest::new(
            "compiled_schedule_gold_reset_v1",
            "oneoz_comex_v1",
            "1OZ",
            "comex_metals_globex_v1",
            "America/Chicago",
            "compiled_exchange_calendars",
            "resolved_context_bundles",
            vec!["daily_16:00_to_17:00_ct".to_string()],
            "block_tradeability_when_delivery_window_is_active",
            "delivery_window_status",
            "2026-03-15T12:00:00Z",
            vec![
                SessionCalendarEntry::new(
                    "summer-2026-03-17",
                    "globex_2026_03_17",
                    "2026-03-17",
                    "comex_metals_globex_v1",
                    "2026-03-16T22:00:00Z",
                    "2026-03-17T21:00:00Z",
                    SessionDayKind::Regular,
                    -300,
                    "17:00 CT",
                    "16:00 CT",
                ),
                SessionCalendarEntry::new(
                    "summer-2026-03-18",
                    "globex_2026_03_18",
                    "2026-03-18",
                    "comex_metals_globex_v1",
                    "2026-03-17T22:00:00Z",
                    "2026-03-18T21:00:00Z",
                    SessionDayKind::Regular,
                    -300,
                    "17:00 CT",
                    "16:00 CT",
                ),
            ],
            vec![MaintenanceWindowDefinition::new(
                "maintenance-2026-03-17",
                "daily_16:00_to_17:00_ct",
                "2026-03-17T21:00:00Z",
                "2026-03-17T22:00:00Z",
                "DAILY_MAINTENANCE_WINDOW",
            )],
            vec![DeliveryFenceWindowDefinition::new(
                "delivery-2026-03-18",
                "block_tradeability_when_delivery_window_is_active",
                "delivery_window_status",
                "2026-03-18T13:00:00Z",
                "2026-03-18T14:00:00Z",
                "DELIVERY_FENCE_ACTIVE",
            )],
            vec![PolicyOverlayWindowDefinition::new(
                "reset-2026-03-17",
                "resolved_context_bundles",
                "2026-03-17T22:00:00Z",
                "2026-03-17T22:05:00Z",
                CompiledSessionState::ResetBoundary,
                "SESSION_RESET_RECONNECT_WINDOW",
            )],
        )
    }

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
    fn broker_control_path_rejects_legacy_direct_operator_bypass() {
        let mut runtime = OpsdRuntime::boot();
        let result = runtime.handle_operator_request(OperatorRequest::new(
            "ctl-1",
            OpsdModule::Broker,
            RuntimeControlAction::CancelOpenOrders,
            "operator-9",
        ));

        assert_eq!(
            Err(DispatchError::BrokerControlRequiresGovernedMutationPath {
                action: RuntimeControlAction::CancelOpenOrders,
            }),
            result
        );
    }

    #[test]
    fn strategy_order_intent_dispatches_standard_broker_mutation() {
        let mut runtime = OpsdRuntime::boot();
        let receipt = runtime
            .submit_order_intent(sample_submit_request())
            .expect("submit should dispatch through broker mutation path");

        assert_eq!(OpsdModule::Broker, receipt.dispatch.target);
        assert_eq!(MessagePriority::Standard, receipt.dispatch.priority);
        assert_eq!(
            MessageKind::BrokerMutation(crate::BrokerMutationKind::Submit),
            receipt.dispatch.message_kind
        );

        let drained = runtime
            .drain_next(OpsdModule::Broker)
            .expect("broker mailbox should contain the submit mutation");
        assert_eq!(
            MessageKind::BrokerMutation(crate::BrokerMutationKind::Submit),
            drained.kind
        );
    }

    #[test]
    fn governed_broker_control_routes_high_priority_and_retains_artifacts() {
        let mut runtime = OpsdRuntime::boot();
        runtime
            .submit_order_intent(sample_submit_request())
            .expect("submit should succeed before control");
        let receipt = runtime
            .handle_broker_control_request(sample_control_request(
                RuntimeControlAction::CancelOpenOrders,
            ))
            .expect("governed broker control should dispatch");

        assert_eq!(OpsdModule::Broker, receipt.dispatch.target);
        assert_eq!(MessagePriority::High, receipt.dispatch.priority);
        assert_eq!(
            MessageKind::BrokerMutation(crate::BrokerMutationKind::Cancel),
            receipt.dispatch.message_kind
        );
        assert_eq!("WITHDRAW_LIVE_OPERATOR_REQUEST", receipt.reason_code);
        assert!(runtime.broker_artifacts().len() >= 2);
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
        assert_eq!(16, report.state_owners.len());
        assert_eq!(0, report.ledger_event_count);
        assert!(
            report
                .state_owners
                .contains(&(RuntimeStateSurface::Orders, OpsdModule::Broker))
        );
        assert!(report.state_owners.contains(&(
            RuntimeStateSurface::ReadinessState,
            OpsdModule::Reconciliation
        )));
        assert!(report.state_owners.contains(&(
            RuntimeStateSurface::CompiledSessionTopology,
            OpsdModule::Reconciliation
        )));
        assert!(report.state_owners.contains(&(
            RuntimeStateSurface::AccountingLedgerState,
            OpsdModule::Reconciliation
        )));
        assert!(report.state_owners.contains(&(
            RuntimeStateSurface::SessionCloseArtifacts,
            OpsdModule::Reconciliation
        )));
        assert_eq!(None, report.compiled_schedule_artifact_id);
        assert_eq!(0, report.compiled_schedule_slice_count);
        assert_eq!(None, report.latest_session_close_artifact_id);
        assert_eq!(None, report.latest_session_readiness_packet_id);
        assert_eq!(None, report.latest_session_readiness_packet_digest);
        assert_eq!(None, report.latest_session_readiness_status);
        assert_eq!(None, report.latest_session_readiness_reason_code);
        assert_eq!(0, report.readiness_history_len);
    }

    #[test]
    fn mailbox_backpressure_returns_structured_diagnostic() {
        let mut runtime = OpsdRuntime::boot();
        for idx in 0..module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity {
            runtime
                .handle_broker_control_request(BrokerControlRequest::new(
                    format!("ctl-{idx}"),
                    "operator-11",
                    format!("decision-trace-{idx}"),
                    format!("expected-timeline-{idx}"),
                    format!("actual-timeline-{idx}"),
                    format!("artifact-manifest-{idx}"),
                    format!("reason-bundle-{idx}"),
                    OrderIntentIdentity::new(
                        "paper-gold-1",
                        idx as u64,
                        "broker",
                        "flat",
                        "cancel_open_orders",
                    ),
                    RuntimeControlAction::CancelOpenOrders,
                    "WITHDRAW_LIVE_OPERATOR_REQUEST",
                ))
                .expect("broker high-priority slot should fit");
        }
        let error = runtime
            .handle_broker_control_request(BrokerControlRequest::new(
                "ctl-overflow",
                "operator-11",
                "decision-trace-overflow",
                "expected-timeline-overflow",
                "actual-timeline-overflow",
                "artifact-manifest-overflow",
                "reason-bundle-overflow",
                OrderIntentIdentity::new("paper-gold-1", 500, "broker", "flat", "flatten"),
                RuntimeControlAction::FlattenPositions,
                "KILL_SWITCH_FLATTEN_REQUEST",
            ))
            .expect_err("overflow control action should return a diagnostic");

        let diagnostic = match error {
            DispatchError::Backpressure(diagnostic) => Some(diagnostic),
            _ => None,
        };
        assert!(diagnostic.is_some(), "expected backpressure diagnostic");
        let Some(diagnostic) = diagnostic else {
            return;
        };
        assert_eq!(OpsdModule::Broker, diagnostic.mailbox_owner);
        assert_eq!(MessagePriority::High, diagnostic.priority);
        assert_eq!(
            module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity,
            diagnostic.capacity
        );
    }

    #[test]
    fn duplicate_fill_callback_is_visible_through_runtime() {
        let mut runtime = OpsdRuntime::boot();
        let submit = runtime
            .submit_order_intent(sample_submit_request())
            .expect("submit should succeed");
        let broker_order_id = submit.broker_order_ids[0].clone();

        let first = runtime
            .record_broker_callback(BrokerCallback::new(
                "fill-1",
                broker_order_id.clone(),
                BrokerCallbackKind::Fill,
            ))
            .expect("first fill should apply");
        let second = runtime
            .record_broker_callback(BrokerCallback::new(
                "fill-1",
                broker_order_id,
                BrokerCallbackKind::Fill,
            ))
            .expect("duplicate fill should dedupe");

        assert!(!first.deduplicated);
        assert!(second.deduplicated);
        assert_eq!("BROKER_DUPLICATE_CALLBACK_DEDUPED", second.reason_code);
    }

    #[test]
    fn broker_mutation_errors_are_wrapped_by_runtime_dispatch_error() {
        let mut runtime = OpsdRuntime::boot();
        let mut request = sample_submit_request();
        request.requested_contract.symbol = "GC".to_string();

        let error = runtime
            .submit_order_intent(request)
            .expect_err("mismatched contract should reject before dispatch");
        assert_eq!(
            DispatchError::BrokerMutation(BrokerMutationError::ContractInvariantMismatch {
                field: "symbol",
                expected: "MGC".to_string(),
                actual: "GC".to_string(),
            }),
            error
        );
    }

    #[test]
    fn runtime_installs_compiled_schedule_and_evaluates_reset_boundaries() {
        let mut runtime = OpsdRuntime::boot();
        let receipt = runtime
            .compile_and_install_schedule(sample_schedule_request())
            .expect("schedule should compile and install");
        assert_eq!("compiled_schedule_gold_reset_v1", receipt.artifact_id);
        assert!(receipt.slice_count >= 4);
        assert!(receipt.tradeable_slice_count >= 2);

        let maintenance = runtime
            .evaluate_session_topology("2026-03-17T21:15:00Z")
            .expect("maintenance instant should evaluate");
        let reset = runtime
            .evaluate_session_topology("2026-03-17T22:02:00Z")
            .expect("reset instant should evaluate");
        let delivery = runtime
            .evaluate_session_topology("2026-03-18T13:30:00Z")
            .expect("delivery instant should evaluate");

        assert_eq!(CompiledSessionState::Maintenance, maintenance.state);
        assert_eq!("DAILY_MAINTENANCE_WINDOW", maintenance.reason_code);
        assert_eq!(CompiledSessionState::ResetBoundary, reset.state);
        assert_eq!("SESSION_RESET_RECONNECT_WINDOW", reset.reason_code);
        assert_eq!(CompiledSessionState::DeliveryFence, delivery.state);
        assert_eq!("DELIVERY_FENCE_ACTIVE", delivery.reason_code);
    }

    #[test]
    fn installed_schedule_surfaces_in_health_report() {
        let mut runtime = OpsdRuntime::boot();
        runtime
            .compile_and_install_schedule(sample_schedule_request())
            .expect("schedule should compile and install");

        let report = runtime.health_report();
        assert_eq!(
            Some("compiled_schedule_gold_reset_v1".to_string()),
            report.compiled_schedule_artifact_id
        );
        assert!(report.compiled_schedule_slice_count >= 4);
    }

    #[test]
    fn runtime_books_internal_ledger_events_and_builds_session_close_artifact() {
        let mut runtime = OpsdRuntime::boot();
        runtime
            .compile_and_install_schedule(sample_schedule_request())
            .expect("schedule should compile and install");
        let fill = runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BookedFill,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T13:05:00Z".to_string(),
                description: "Booked one-contract fill".to_string(),
                correlation_id: "fill-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: Some("fill-1".to_string()),
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 1,
                cash_delta_usd_cents: -25350,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec![
                    "artifact-0001".to_string(),
                    "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
                ],
            })
            .expect("booked fill should append");
        let duplicate = runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BookedFill,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T13:05:00Z".to_string(),
                description: "Duplicate booked fill".to_string(),
                correlation_id: "fill-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: Some("fill-1".to_string()),
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 1,
                cash_delta_usd_cents: -25350,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec![
                    "artifact-0001".to_string(),
                    "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
                ],
            })
            .expect("duplicate callback should deduplicate");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BookedCommission,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T13:05:01Z".to_string(),
                description: "Booked commission".to_string(),
                correlation_id: "commission-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 55,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec![fill.retained_artifact_id.clone()],
            })
            .expect("commission should append");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BrokerEodPosition,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T22:10:00Z".to_string(),
                description: "Broker EOD position".to_string(),
                correlation_id: "broker-eod-1".to_string(),
                order_intent_id: None,
                broker_order_id: None,
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: Some(1),
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-0004".to_string()],
            })
            .expect("broker EOD position should append");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BrokerEodMarginSnapshot,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T22:10:01Z".to_string(),
                description: "Broker EOD margin".to_string(),
                correlation_id: "broker-margin-1".to_string(),
                order_intent_id: None,
                broker_order_id: None,
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: Some(125_000),
                authoritative_maintenance_margin_requirement_usd_cents: Some(95_000),
                source_artifact_ids: vec!["artifact-0005".to_string()],
            })
            .expect("broker EOD margin should append");

        let close = runtime
            .build_session_close_artifact(SessionCloseRequest {
                close_id: "close-1".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                compiled_schedule_artifact_id:
                    "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
                close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
            })
            .expect("session close should build");

        assert!(duplicate.idempotent_replay);
        assert_eq!(4, runtime.ledger_events().len());
        assert_eq!(SessionCloseStatus::Pass, close.status);
        assert_eq!(1, close.as_booked_totals.position_contracts);
        assert_eq!(55, close.as_booked_totals.commission_total_usd_cents);
        assert_eq!(
            Some("ledger-close-0001".to_string()),
            runtime.health_report().latest_session_close_artifact_id
        );
        assert!(runtime.latest_session_close_artifact().is_some());
    }

    #[test]
    fn runtime_retains_intraday_and_authoritative_reconciliation_artifacts() {
        let mut runtime = OpsdRuntime::boot();
        runtime
            .compile_and_install_schedule(sample_schedule_request())
            .expect("schedule should compile and install");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BookedFill,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T13:05:00Z".to_string(),
                description: "Booked one-contract fill".to_string(),
                correlation_id: "fill-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: Some("fill-1".to_string()),
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 1,
                cash_delta_usd_cents: -25_350,
                realized_pnl_delta_usd_cents: 12_500,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-0001".to_string()],
            })
            .expect("fill should append");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BookedCommission,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T13:05:01Z".to_string(),
                description: "Booked commission".to_string(),
                correlation_id: "commission-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 45,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-0002".to_string()],
            })
            .expect("commission should append");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BrokerEodPosition,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T22:10:00Z".to_string(),
                description: "Broker EOD position".to_string(),
                correlation_id: "broker-eod-1".to_string(),
                order_intent_id: None,
                broker_order_id: None,
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: Some(1),
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-0003".to_string()],
            })
            .expect("broker EOD position should append");
        runtime
            .append_ledger_event(LedgerEventRequest {
                event_class: LedgerEventClass::BrokerEodMarginSnapshot,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T22:10:01Z".to_string(),
                description: "Broker EOD margin".to_string(),
                correlation_id: "broker-margin-1".to_string(),
                order_intent_id: None,
                broker_order_id: None,
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: None,
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: Some(125_000),
                authoritative_maintenance_margin_requirement_usd_cents: Some(95_000),
                source_artifact_ids: vec!["artifact-0004".to_string()],
            })
            .expect("broker EOD margin should append");
        let session_close = runtime
            .build_session_close_artifact(SessionCloseRequest {
                close_id: "close-2".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                compiled_schedule_artifact_id:
                    "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
                close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
            })
            .expect("session close should build");

        let intraday = runtime
            .evaluate_intraday_reconciliation(IntradayReconciliationRequest {
                reconciliation_id: "intraday-1".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                evaluated_at_utc: "2026-03-18T20:00:00Z".to_string(),
                correlation_id: "intraday-corr-1".to_string(),
                position_tolerance_contracts: 0,
                local_position_contracts: 1,
                broker_position_contracts: 1,
                local_working_order_ids: vec!["broker-order-1".to_string()],
                broker_working_order_ids: vec![
                    "broker-order-1".to_string(),
                    "broker-order-2".to_string(),
                ],
                local_fill_ids: vec!["fill-1".to_string()],
                broker_fill_ids: vec!["fill-1".to_string()],
                local_trading_permission_state: "tradeable".to_string(),
                broker_trading_permission_state: "tradeable".to_string(),
                source_artifact_ids: vec!["evidence/broker/intraday-1.json".to_string()],
            })
            .expect("intraday reconciliation should succeed");
        let close = runtime
            .build_authoritative_ledger_close(DailyLedgerCloseRequest {
                ledger_close_id: "daily-close-1".to_string(),
                session_close_artifact_id: session_close.artifact_id.clone(),
                statement_set: AuthoritativeStatementSet {
                    statement_set_id: "statement-set-2026-03-18".to_string(),
                    account_id: "acct-1".to_string(),
                    symbol: "1OZ".to_string(),
                    session_id: "globex_2026_03_18".to_string(),
                    ledger_close_date: "2026-03-18".to_string(),
                    ingested_at_utc: "2026-03-18T22:20:00Z".to_string(),
                    fill_execution_ids: vec!["fill-1".to_string(), "fill-2".to_string()],
                    position_contracts: 1,
                    cash_movement_total_usd_cents: -25_350,
                    commission_total_usd_cents: 45,
                    fee_total_usd_cents: 0,
                    realized_pnl_usd_cents: 12_500,
                    unrealized_pnl_usd_cents: 8_750,
                    initial_margin_requirement_usd_cents: 125_000,
                    maintenance_margin_requirement_usd_cents: 95_000,
                    source_artifact_ids: vec![
                        "evidence/broker/statement-set-2026-03-18.csv".to_string(),
                    ],
                },
                runtime_unrealized_pnl_usd_cents: Some(8_750),
                reviewed_or_waived: false,
                review_or_waiver_id: None,
                correlation_id: "daily-corr-1".to_string(),
                evaluated_at_utc: "2026-03-18T22:25:00Z".to_string(),
            })
            .expect("authoritative close should build");

        assert_eq!(IntradayControlAction::Restrict, intraday.required_action);
        assert_eq!(
            NextSessionEligibility::Blocked,
            close.next_session_eligibility
        );
        let health = runtime.health_report();
        assert!(runtime.latest_intraday_reconciliation_artifact().is_some());
        assert!(runtime.latest_authoritative_close_artifact().is_some());
        assert_eq!(
            Some(close.artifact_id.clone()),
            health.latest_authoritative_close_artifact_id
        );
        assert_eq!(Some("blocked".to_string()), health.next_session_eligibility);
    }

    #[test]
    fn runtime_retains_latest_session_readiness_packet_in_health_report() {
        let mut runtime = OpsdRuntime::boot();
        let packet = runtime.publish_session_readiness_packet(
            sample_session_readiness_request("green-readiness-pass")
                .expect("green readiness scenario should exist"),
        );
        let health = runtime.health_report();

        assert_eq!(SessionReadinessStatus::Green, packet.status);
        assert_eq!(
            Some(packet.packet_id.clone()),
            health.latest_session_readiness_packet_id
        );
        assert_eq!(
            Some(packet.packet_digest.clone()),
            health.latest_session_readiness_packet_digest
        );
        assert_eq!(
            Some(packet.status.as_str().to_string()),
            health.latest_session_readiness_status
        );
        assert_eq!(
            Some(packet.reason_code.clone()),
            health.latest_session_readiness_reason_code
        );
        assert_eq!(packet.history.len(), health.readiness_history_len);
        assert_eq!(Some(&packet), runtime.latest_session_readiness_packet());
        assert_eq!(packet.history.as_slice(), runtime.readiness_history());
    }

    #[test]
    fn followup_readiness_packets_use_runtime_retained_history() {
        let mut runtime = OpsdRuntime::boot();
        let first_packet = runtime.publish_session_readiness_packet(
            sample_session_readiness_request("green-readiness-pass")
                .expect("green readiness scenario should exist"),
        );
        let second_packet = runtime.publish_session_readiness_packet(
            sample_session_readiness_request("clock-stale-blocked")
                .expect("blocked readiness scenario should exist"),
        );

        assert_eq!(2, first_packet.history.len());
        assert_eq!(SessionReadinessStatus::Blocked, second_packet.status);
        assert_eq!(3, second_packet.history.len());
        assert_eq!(
            vec!["clock-check-001".to_string()],
            second_packet.blocked_provider_ids
        );
        assert_eq!(
            second_packet.history.as_slice(),
            runtime.readiness_history()
        );
        assert_eq!(
            second_packet.packet_id,
            runtime
                .latest_session_readiness_packet()
                .expect("latest readiness packet should be retained")
                .packet_id
        );
    }
}
