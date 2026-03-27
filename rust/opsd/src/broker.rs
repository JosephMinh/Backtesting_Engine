use std::collections::{BTreeMap, BTreeSet};

use crate::RuntimeControlAction;

/// Supported broker order types for the governed adapter contract.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BrokerOrderType {
    Market,
    Limit,
    Stop,
}

impl BrokerOrderType {
    /// Stable identifier for logs and smoke scenarios.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Market => "market",
            Self::Limit => "limit",
            Self::Stop => "stop",
        }
    }
}

/// Supported time-in-force modes for the governed adapter contract.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BrokerTimeInForce {
    Day,
    Gtc,
    Ioc,
    Opg,
}

impl BrokerTimeInForce {
    /// Stable identifier for logs and smoke scenarios.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Day => "day",
            Self::Gtc => "gtc",
            Self::Ioc => "ioc",
            Self::Opg => "opg",
        }
    }
}

/// Canonical mutation types for broker-facing runtime changes.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BrokerMutationKind {
    Submit,
    Cancel,
    Flatten,
}

impl BrokerMutationKind {
    /// Stable identifier for logs and smoke scenarios.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Submit => "submit",
            Self::Cancel => "cancel",
            Self::Flatten => "flatten",
        }
    }
}

/// Known acknowledgement states for a broker mutation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BrokerAckState {
    Unknown,
    Pending,
    Acknowledged,
}

impl BrokerAckState {
    /// Stable identifier for diagnostics.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unknown => "unknown",
            Self::Pending => "pending",
            Self::Acknowledged => "acknowledged",
        }
    }
}

/// Broker callback kinds retained for replayable evidence.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BrokerCallbackKind {
    Acknowledged,
    Fill,
    Cancelled,
}

impl BrokerCallbackKind {
    /// Stable identifier for diagnostics.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Acknowledged => "acknowledged",
            Self::Fill => "fill",
            Self::Cancelled => "cancelled",
        }
    }
}

/// Canonical active contract descriptor enforced before mutation.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerContractDescriptor {
    pub symbol: String,
    pub exchange: String,
    pub currency: String,
    pub contract_size_oz: u32,
    pub minimum_price_fluctuation_usd_per_oz: f64,
    pub settlement_type: String,
    pub session_calendar_id: String,
}

impl BrokerContractDescriptor {
    /// Deterministic one-ounce COMEX gold contract used by the smoke path.
    pub fn one_oz_comex() -> Self {
        Self {
            symbol: "MGC".to_string(),
            exchange: "COMEX".to_string(),
            currency: "USD".to_string(),
            contract_size_oz: 10,
            minimum_price_fluctuation_usd_per_oz: 0.1,
            settlement_type: "physical".to_string(),
            session_calendar_id: "comex.metals.v1".to_string(),
        }
    }
}

/// Active broker capability descriptor used for runtime conformance checks.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerCapabilityDescriptor {
    pub descriptor_id: String,
    pub adapter_id: String,
    pub broker: String,
    pub supported_order_types: Vec<BrokerOrderType>,
    pub supported_time_in_force: Vec<BrokerTimeInForce>,
    pub modify_cancel_supported: bool,
    pub flatten_supported: bool,
    pub session_definition_supported: bool,
    pub contract_conformance_required: bool,
    pub message_rate_limit_per_second: u32,
}

/// Live broker adapter configuration used by the in-process runtime.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerAdapterConfig {
    pub descriptor: BrokerCapabilityDescriptor,
    pub active_contract: BrokerContractDescriptor,
}

impl Default for BrokerAdapterConfig {
    fn default() -> Self {
        Self {
            descriptor: BrokerCapabilityDescriptor {
                descriptor_id: "ibkr.mgc.paper.v1".to_string(),
                adapter_id: "ibkr-paper".to_string(),
                broker: "ibkr".to_string(),
                supported_order_types: vec![BrokerOrderType::Market, BrokerOrderType::Limit],
                supported_time_in_force: vec![BrokerTimeInForce::Day, BrokerTimeInForce::Gtc],
                modify_cancel_supported: true,
                flatten_supported: true,
                session_definition_supported: true,
                contract_conformance_required: true,
                message_rate_limit_per_second: 25,
            },
            active_contract: BrokerContractDescriptor::one_oz_comex(),
        }
    }
}

/// Deterministic order-intent identity shared across retries and recovery.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OrderIntentIdentity {
    pub deployment_instance_id: String,
    pub decision_sequence_number: u64,
    pub leg_id: String,
    pub side: String,
    pub intent_purpose: String,
}

impl OrderIntentIdentity {
    /// Creates a deterministic identity for a broker mutation.
    pub fn new(
        deployment_instance_id: impl Into<String>,
        decision_sequence_number: u64,
        leg_id: impl Into<String>,
        side: impl Into<String>,
        intent_purpose: impl Into<String>,
    ) -> Self {
        Self {
            deployment_instance_id: deployment_instance_id.into(),
            decision_sequence_number,
            leg_id: leg_id.into(),
            side: side.into(),
            intent_purpose: intent_purpose.into(),
        }
    }

    /// Returns the canonical deterministic intent id.
    pub fn deterministic_id(&self) -> String {
        format!(
            "{}:{}:{}:{}:{}",
            self.deployment_instance_id,
            self.decision_sequence_number,
            self.leg_id,
            self.side,
            self.intent_purpose
        )
    }
}

/// Broker order-intent mutation requested by the strategy runner.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerOrderIntentRequest {
    pub correlation_id: String,
    pub decision_trace_id: String,
    pub expected_timeline_id: String,
    pub actual_timeline_id: String,
    pub artifact_manifest_id: String,
    pub operator_reason_bundle_id: String,
    pub order_intent_identity: OrderIntentIdentity,
    pub order_type: BrokerOrderType,
    pub time_in_force: BrokerTimeInForce,
    pub requested_contract: BrokerContractDescriptor,
}

impl BrokerOrderIntentRequest {
    /// Creates a deterministic order-intent request for the broker module.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        correlation_id: impl Into<String>,
        decision_trace_id: impl Into<String>,
        expected_timeline_id: impl Into<String>,
        actual_timeline_id: impl Into<String>,
        artifact_manifest_id: impl Into<String>,
        operator_reason_bundle_id: impl Into<String>,
        order_intent_identity: OrderIntentIdentity,
        order_type: BrokerOrderType,
        time_in_force: BrokerTimeInForce,
        requested_contract: BrokerContractDescriptor,
    ) -> Self {
        Self {
            correlation_id: correlation_id.into(),
            decision_trace_id: decision_trace_id.into(),
            expected_timeline_id: expected_timeline_id.into(),
            actual_timeline_id: actual_timeline_id.into(),
            artifact_manifest_id: artifact_manifest_id.into(),
            operator_reason_bundle_id: operator_reason_bundle_id.into(),
            order_intent_identity,
            order_type,
            time_in_force,
            requested_contract,
        }
    }
}

/// Governed operator control request that must flow through broker mutation evidence.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerControlRequest {
    pub correlation_id: String,
    pub operator_id: String,
    pub decision_trace_id: String,
    pub expected_timeline_id: String,
    pub actual_timeline_id: String,
    pub artifact_manifest_id: String,
    pub operator_reason_bundle_id: String,
    pub order_intent_identity: OrderIntentIdentity,
    pub action: RuntimeControlAction,
    pub reason_code: String,
}

impl BrokerControlRequest {
    /// Creates a governed operator control request for the broker module.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        correlation_id: impl Into<String>,
        operator_id: impl Into<String>,
        decision_trace_id: impl Into<String>,
        expected_timeline_id: impl Into<String>,
        actual_timeline_id: impl Into<String>,
        artifact_manifest_id: impl Into<String>,
        operator_reason_bundle_id: impl Into<String>,
        order_intent_identity: OrderIntentIdentity,
        action: RuntimeControlAction,
        reason_code: impl Into<String>,
    ) -> Self {
        Self {
            correlation_id: correlation_id.into(),
            operator_id: operator_id.into(),
            decision_trace_id: decision_trace_id.into(),
            expected_timeline_id: expected_timeline_id.into(),
            actual_timeline_id: actual_timeline_id.into(),
            artifact_manifest_id: artifact_manifest_id.into(),
            operator_reason_bundle_id: operator_reason_bundle_id.into(),
            order_intent_identity,
            action,
            reason_code: reason_code.into(),
        }
    }
}

/// Broker callback retained for callback-race and duplicate-fill handling.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrokerCallback {
    pub callback_id: String,
    pub broker_order_id: String,
    pub kind: BrokerCallbackKind,
}

impl BrokerCallback {
    /// Creates a deterministic callback event.
    pub fn new(
        callback_id: impl Into<String>,
        broker_order_id: impl Into<String>,
        kind: BrokerCallbackKind,
    ) -> Self {
        Self {
            callback_id: callback_id.into(),
            broker_order_id: broker_order_id.into(),
            kind,
        }
    }
}

/// Retained broker-mutation artifact for replayable operator evidence.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerMutationArtifact {
    pub artifact_id: String,
    pub mutation_kind: BrokerMutationKind,
    pub order_intent_id: String,
    pub broker_order_ids: Vec<String>,
    pub correlation_id: String,
    pub decision_trace_id: String,
    pub expected_timeline_id: String,
    pub actual_timeline_id: String,
    pub artifact_manifest_id: String,
    pub operator_reason_bundle_id: String,
    pub reason_code: String,
    pub control_path: bool,
}

/// Result of a governed broker mutation before mailbox dispatch.
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerMutationDecision {
    pub mutation_kind: BrokerMutationKind,
    pub order_intent_id: String,
    pub broker_order_ids: Vec<String>,
    pub reason_code: String,
    pub idempotent_replay: bool,
    pub retained_artifact_id: String,
}

/// Result of broker callback processing.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrokerCallbackReceipt {
    pub broker_order_id: String,
    pub order_intent_id: String,
    pub callback_id: String,
    pub callback_kind: BrokerCallbackKind,
    pub deduplicated: bool,
    pub reason_code: String,
}

/// Contract or adapter failure returned when broker mutation cannot proceed.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BrokerMutationError {
    DescriptorRateLimitRequired,
    RequiredOrderTypeUnsupported(BrokerOrderType),
    RequiredTimeInForceUnsupported(BrokerTimeInForce),
    ModifyCancelSupportRequired,
    FlattenSupportRequired,
    SessionDefinitionRequired,
    ContractInvariantMismatch {
        field: &'static str,
        expected: String,
        actual: String,
    },
    UnsupportedControlAction(RuntimeControlAction),
    UnknownBrokerOrder {
        broker_order_id: String,
    },
    CorruptIntentMapping {
        order_intent_id: String,
    },
}

impl BrokerMutationError {
    /// Stable reason code retained in tests and operator logs.
    pub const fn reason_code(&self) -> &'static str {
        match self {
            Self::DescriptorRateLimitRequired => "BROKER_DESCRIPTOR_RATE_LIMIT_REQUIRED",
            Self::RequiredOrderTypeUnsupported(_) => "BROKER_REQUIRED_ORDER_TYPE_UNSUPPORTED",
            Self::RequiredTimeInForceUnsupported(_) => "BROKER_REQUIRED_TIME_IN_FORCE_UNSUPPORTED",
            Self::ModifyCancelSupportRequired => "BROKER_MODIFY_CANCEL_SUPPORT_REQUIRED",
            Self::FlattenSupportRequired => "BROKER_FLATTEN_SUPPORT_REQUIRED",
            Self::SessionDefinitionRequired => "BROKER_SESSION_DEFINITION_REQUIRED",
            Self::ContractInvariantMismatch { .. } => "BROKER_CONTRACT_INVARIANT_MISMATCH",
            Self::UnsupportedControlAction(_) => "BROKER_CONTROL_ACTION_UNSUPPORTED",
            Self::UnknownBrokerOrder { .. } => "BROKER_ORDER_UNKNOWN",
            Self::CorruptIntentMapping { .. } => "BROKER_ORDER_INTENT_MAPPING_CORRUPT",
        }
    }
}

#[derive(Clone, Debug)]
struct IntentRecord {
    broker_order_ids: Vec<String>,
    ack_state: BrokerAckState,
    fill_callback_ids: BTreeSet<String>,
    open_order: bool,
    control_path: bool,
}

/// In-memory governed broker mutation engine used by the runtime skeleton.
#[derive(Clone, Debug)]
pub struct BrokerMutationEngine {
    config: BrokerAdapterConfig,
    intent_records: BTreeMap<String, IntentRecord>,
    broker_order_to_intent: BTreeMap<String, String>,
    artifacts: Vec<BrokerMutationArtifact>,
    callback_log: Vec<BrokerCallbackReceipt>,
    next_broker_order_sequence: usize,
    next_artifact_sequence: usize,
}

impl BrokerMutationEngine {
    /// Creates a governed broker mutation engine with the provided adapter config.
    pub fn new(config: BrokerAdapterConfig) -> Self {
        Self {
            config,
            intent_records: BTreeMap::new(),
            broker_order_to_intent: BTreeMap::new(),
            artifacts: Vec::new(),
            callback_log: Vec::new(),
            next_broker_order_sequence: 1,
            next_artifact_sequence: 1,
        }
    }

    /// Returns the active adapter configuration.
    pub fn config(&self) -> &BrokerAdapterConfig {
        &self.config
    }

    /// Returns retained broker-mutation artifacts.
    pub fn artifacts(&self) -> &[BrokerMutationArtifact] {
        &self.artifacts
    }

    /// Returns processed broker callbacks retained for diagnostics.
    pub fn callback_log(&self) -> &[BrokerCallbackReceipt] {
        &self.callback_log
    }

    /// Returns the number of durable intent records currently retained.
    pub fn intent_record_count(&self) -> usize {
        self.intent_records.len()
    }

    /// Returns active broker order ids that still represent open working state.
    pub fn active_open_order_ids(&self) -> Vec<String> {
        let mut order_ids = Vec::new();
        for record in self.intent_records.values() {
            if record.open_order && !record.control_path {
                order_ids.extend(record.broker_order_ids.iter().cloned());
            }
        }
        order_ids
    }

    /// Accepts a governed strategy order-intent mutation.
    pub fn submit_order_intent(
        &mut self,
        request: BrokerOrderIntentRequest,
    ) -> Result<BrokerMutationDecision, BrokerMutationError> {
        self.validate_submit_request(&request)?;
        let order_intent_id = request.order_intent_identity.deterministic_id();
        if let Some(existing) = self.intent_records.get(&order_intent_id) {
            let broker_order_ids = existing.broker_order_ids.clone();
            let artifact_id = self.retain_artifact(BrokerMutationArtifact {
                artifact_id: String::new(),
                mutation_kind: BrokerMutationKind::Submit,
                order_intent_id: order_intent_id.clone(),
                broker_order_ids: broker_order_ids.clone(),
                correlation_id: request.correlation_id,
                decision_trace_id: request.decision_trace_id,
                expected_timeline_id: request.expected_timeline_id,
                actual_timeline_id: request.actual_timeline_id,
                artifact_manifest_id: request.artifact_manifest_id,
                operator_reason_bundle_id: request.operator_reason_bundle_id,
                reason_code: "BROKER_IDEMPOTENT_REPLAY".to_string(),
                control_path: false,
            });
            return Ok(BrokerMutationDecision {
                mutation_kind: BrokerMutationKind::Submit,
                order_intent_id,
                broker_order_ids,
                reason_code: "BROKER_IDEMPOTENT_REPLAY".to_string(),
                idempotent_replay: true,
                retained_artifact_id: artifact_id,
            });
        }

        let broker_order_id = self.allocate_broker_order_id();
        self.broker_order_to_intent
            .insert(broker_order_id.clone(), order_intent_id.clone());
        self.intent_records.insert(
            order_intent_id.clone(),
            IntentRecord {
                broker_order_ids: vec![broker_order_id.clone()],
                ack_state: BrokerAckState::Pending,
                fill_callback_ids: BTreeSet::new(),
                open_order: true,
                control_path: false,
            },
        );
        let artifact_id = self.retain_artifact(BrokerMutationArtifact {
            artifact_id: String::new(),
            mutation_kind: BrokerMutationKind::Submit,
            order_intent_id: order_intent_id.clone(),
            broker_order_ids: vec![broker_order_id.clone()],
            correlation_id: request.correlation_id,
            decision_trace_id: request.decision_trace_id,
            expected_timeline_id: request.expected_timeline_id,
            actual_timeline_id: request.actual_timeline_id,
            artifact_manifest_id: request.artifact_manifest_id,
            operator_reason_bundle_id: request.operator_reason_bundle_id,
            reason_code: "BROKER_MUTATION_ACCEPTED".to_string(),
            control_path: false,
        });
        Ok(BrokerMutationDecision {
            mutation_kind: BrokerMutationKind::Submit,
            order_intent_id,
            broker_order_ids: vec![broker_order_id],
            reason_code: "BROKER_MUTATION_ACCEPTED".to_string(),
            idempotent_replay: false,
            retained_artifact_id: artifact_id,
        })
    }

    /// Accepts a governed operator control request for the broker module.
    pub fn apply_control_request(
        &mut self,
        request: BrokerControlRequest,
    ) -> Result<BrokerMutationDecision, BrokerMutationError> {
        let mutation_kind = match request.action {
            RuntimeControlAction::CancelOpenOrders => {
                if !self.config.descriptor.modify_cancel_supported {
                    return Err(BrokerMutationError::ModifyCancelSupportRequired);
                }
                BrokerMutationKind::Cancel
            }
            RuntimeControlAction::FlattenPositions => {
                if !self.config.descriptor.flatten_supported {
                    return Err(BrokerMutationError::FlattenSupportRequired);
                }
                BrokerMutationKind::Flatten
            }
            action => return Err(BrokerMutationError::UnsupportedControlAction(action)),
        };

        let order_intent_id = request.order_intent_identity.deterministic_id();
        if let Some(existing) = self.intent_records.get(&order_intent_id) {
            let broker_order_ids = existing.broker_order_ids.clone();
            let artifact_id = self.retain_artifact(BrokerMutationArtifact {
                artifact_id: String::new(),
                mutation_kind,
                order_intent_id: order_intent_id.clone(),
                broker_order_ids: broker_order_ids.clone(),
                correlation_id: request.correlation_id,
                decision_trace_id: request.decision_trace_id,
                expected_timeline_id: request.expected_timeline_id,
                actual_timeline_id: request.actual_timeline_id,
                artifact_manifest_id: request.artifact_manifest_id,
                operator_reason_bundle_id: request.operator_reason_bundle_id,
                reason_code: request.reason_code.clone(),
                control_path: true,
            });
            return Ok(BrokerMutationDecision {
                mutation_kind,
                order_intent_id,
                broker_order_ids,
                reason_code: request.reason_code,
                idempotent_replay: true,
                retained_artifact_id: artifact_id,
            });
        }

        let broker_order_ids = match mutation_kind {
            BrokerMutationKind::Cancel => {
                let order_ids = self.active_open_order_ids();
                for order_id in &order_ids {
                    if let Some(intent_id) = self.broker_order_to_intent.get(order_id).cloned() {
                        if let Some(record) = self.intent_records.get_mut(&intent_id) {
                            record.open_order = false;
                        }
                    }
                }
                order_ids
            }
            BrokerMutationKind::Flatten => {
                let broker_order_id = self.allocate_broker_order_id();
                self.broker_order_to_intent
                    .insert(broker_order_id.clone(), order_intent_id.clone());
                vec![broker_order_id]
            }
            BrokerMutationKind::Submit => unreachable!("submit is not a control action"),
        };

        self.intent_records.insert(
            order_intent_id.clone(),
            IntentRecord {
                broker_order_ids: broker_order_ids.clone(),
                ack_state: BrokerAckState::Pending,
                fill_callback_ids: BTreeSet::new(),
                open_order: false,
                control_path: true,
            },
        );
        let artifact_id = self.retain_artifact(BrokerMutationArtifact {
            artifact_id: String::new(),
            mutation_kind,
            order_intent_id: order_intent_id.clone(),
            broker_order_ids: broker_order_ids.clone(),
            correlation_id: request.correlation_id,
            decision_trace_id: request.decision_trace_id,
            expected_timeline_id: request.expected_timeline_id,
            actual_timeline_id: request.actual_timeline_id,
            artifact_manifest_id: request.artifact_manifest_id,
            operator_reason_bundle_id: request.operator_reason_bundle_id,
            reason_code: request.reason_code.clone(),
            control_path: true,
        });
        Ok(BrokerMutationDecision {
            mutation_kind,
            order_intent_id,
            broker_order_ids,
            reason_code: request.reason_code,
            idempotent_replay: false,
            retained_artifact_id: artifact_id,
        })
    }

    /// Applies a broker callback to known mutation state.
    pub fn record_callback(
        &mut self,
        callback: BrokerCallback,
    ) -> Result<BrokerCallbackReceipt, BrokerMutationError> {
        let Some(order_intent_id) = self
            .broker_order_to_intent
            .get(&callback.broker_order_id)
            .cloned()
        else {
            return Err(BrokerMutationError::UnknownBrokerOrder {
                broker_order_id: callback.broker_order_id,
            });
        };

        let Some(record) = self.intent_records.get_mut(&order_intent_id) else {
            return Err(BrokerMutationError::CorruptIntentMapping { order_intent_id });
        };
        let (deduplicated, reason_code) = match callback.kind {
            BrokerCallbackKind::Acknowledged => {
                let duplicate = record.ack_state == BrokerAckState::Acknowledged;
                record.ack_state = BrokerAckState::Acknowledged;
                (
                    duplicate,
                    if duplicate {
                        "BROKER_DUPLICATE_ACK_DEDUPED"
                    } else {
                        "BROKER_CALLBACK_ACKNOWLEDGED"
                    },
                )
            }
            BrokerCallbackKind::Fill => {
                let duplicate = !record
                    .fill_callback_ids
                    .insert(callback.callback_id.clone());
                if !duplicate {
                    record.open_order = false;
                }
                (
                    duplicate,
                    if duplicate {
                        "BROKER_DUPLICATE_CALLBACK_DEDUPED"
                    } else {
                        "BROKER_CALLBACK_FILL_APPLIED"
                    },
                )
            }
            BrokerCallbackKind::Cancelled => {
                let duplicate = !record.open_order;
                record.open_order = false;
                (
                    duplicate,
                    if duplicate {
                        "BROKER_DUPLICATE_CANCEL_DEDUPED"
                    } else {
                        "BROKER_CALLBACK_CANCEL_APPLIED"
                    },
                )
            }
        };

        let receipt = BrokerCallbackReceipt {
            broker_order_id: callback.broker_order_id,
            order_intent_id,
            callback_id: callback.callback_id,
            callback_kind: callback.kind,
            deduplicated,
            reason_code: reason_code.to_string(),
        };
        self.callback_log.push(receipt.clone());
        Ok(receipt)
    }

    fn validate_submit_request(
        &self,
        request: &BrokerOrderIntentRequest,
    ) -> Result<(), BrokerMutationError> {
        if self.config.descriptor.message_rate_limit_per_second == 0 {
            return Err(BrokerMutationError::DescriptorRateLimitRequired);
        }
        if !self
            .config
            .descriptor
            .supported_order_types
            .contains(&request.order_type)
        {
            return Err(BrokerMutationError::RequiredOrderTypeUnsupported(
                request.order_type,
            ));
        }
        if !self
            .config
            .descriptor
            .supported_time_in_force
            .contains(&request.time_in_force)
        {
            return Err(BrokerMutationError::RequiredTimeInForceUnsupported(
                request.time_in_force,
            ));
        }
        if !self.config.descriptor.session_definition_supported {
            return Err(BrokerMutationError::SessionDefinitionRequired);
        }
        if self.config.descriptor.contract_conformance_required {
            self.validate_contract_descriptor(&request.requested_contract)?;
        }
        Ok(())
    }

    fn validate_contract_descriptor(
        &self,
        requested: &BrokerContractDescriptor,
    ) -> Result<(), BrokerMutationError> {
        let active = &self.config.active_contract;
        if requested.symbol != active.symbol {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "symbol",
                expected: active.symbol.clone(),
                actual: requested.symbol.clone(),
            });
        }
        if requested.exchange != active.exchange {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "exchange",
                expected: active.exchange.clone(),
                actual: requested.exchange.clone(),
            });
        }
        if requested.currency != active.currency {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "currency",
                expected: active.currency.clone(),
                actual: requested.currency.clone(),
            });
        }
        if requested.contract_size_oz != active.contract_size_oz {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "contract_size_oz",
                expected: active.contract_size_oz.to_string(),
                actual: requested.contract_size_oz.to_string(),
            });
        }
        if requested.minimum_price_fluctuation_usd_per_oz
            != active.minimum_price_fluctuation_usd_per_oz
        {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "minimum_price_fluctuation_usd_per_oz",
                expected: active.minimum_price_fluctuation_usd_per_oz.to_string(),
                actual: requested.minimum_price_fluctuation_usd_per_oz.to_string(),
            });
        }
        if requested.settlement_type != active.settlement_type {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "settlement_type",
                expected: active.settlement_type.clone(),
                actual: requested.settlement_type.clone(),
            });
        }
        if requested.session_calendar_id != active.session_calendar_id {
            return Err(BrokerMutationError::ContractInvariantMismatch {
                field: "session_calendar_id",
                expected: active.session_calendar_id.clone(),
                actual: requested.session_calendar_id.clone(),
            });
        }
        Ok(())
    }

    fn allocate_broker_order_id(&mut self) -> String {
        let broker_order_id = format!(
            "{}-order-{:04}",
            self.config.descriptor.adapter_id, self.next_broker_order_sequence
        );
        self.next_broker_order_sequence += 1;
        broker_order_id
    }

    fn retain_artifact(&mut self, mut artifact: BrokerMutationArtifact) -> String {
        let artifact_id = format!("artifact-{:04}", self.next_artifact_sequence);
        self.next_artifact_sequence += 1;
        artifact.artifact_id = artifact_id.clone();
        self.artifacts.push(artifact);
        artifact_id
    }
}

#[cfg(test)]
mod tests {
    use super::{
        BrokerAdapterConfig, BrokerCallback, BrokerCallbackKind, BrokerContractDescriptor,
        BrokerControlRequest, BrokerMutationEngine, BrokerMutationError, BrokerOrderIntentRequest,
        BrokerOrderType, BrokerTimeInForce, OrderIntentIdentity,
    };
    use crate::RuntimeControlAction;

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
            "operator-7",
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

    #[test]
    fn retry_before_ack_reuses_single_order_intent_mapping() {
        let mut engine = BrokerMutationEngine::new(BrokerAdapterConfig::default());
        let first = engine
            .submit_order_intent(sample_submit_request())
            .expect("initial submit should succeed");
        let second = engine
            .submit_order_intent(sample_submit_request())
            .expect("retry should reuse the existing mapping");

        assert_eq!(first.order_intent_id, second.order_intent_id);
        assert_eq!(first.broker_order_ids, second.broker_order_ids);
        assert!(!first.idempotent_replay);
        assert!(second.idempotent_replay);
        assert_eq!(2, engine.artifacts().len());
    }

    #[test]
    fn duplicate_fill_callback_is_deduplicated() {
        let mut engine = BrokerMutationEngine::new(BrokerAdapterConfig::default());
        let submit = engine
            .submit_order_intent(sample_submit_request())
            .expect("submit should succeed");
        let broker_order_id = submit
            .broker_order_ids
            .first()
            .expect("submit should emit one broker order id")
            .clone();

        let first = engine
            .record_callback(BrokerCallback::new(
                "fill-1",
                broker_order_id.clone(),
                BrokerCallbackKind::Fill,
            ))
            .expect("first fill should apply");
        let second = engine
            .record_callback(BrokerCallback::new(
                "fill-1",
                broker_order_id,
                BrokerCallbackKind::Fill,
            ))
            .expect("duplicate fill should be deduplicated");

        assert!(!first.deduplicated);
        assert!(second.deduplicated);
        assert_eq!("BROKER_DUPLICATE_CALLBACK_DEDUPED", second.reason_code);
        assert!(engine.active_open_order_ids().is_empty());
    }

    #[test]
    fn submit_rejects_contract_mismatch() {
        let mut engine = BrokerMutationEngine::new(BrokerAdapterConfig::default());
        let mut request = sample_submit_request();
        request.requested_contract.symbol = "GC".to_string();

        let error = engine
            .submit_order_intent(request)
            .expect_err("contract mismatch should reject the mutation");
        assert_eq!(
            BrokerMutationError::ContractInvariantMismatch {
                field: "symbol",
                expected: "MGC".to_string(),
                actual: "GC".to_string(),
            },
            error
        );
    }

    #[test]
    fn cancel_control_requires_modify_cancel_support() {
        let mut config = BrokerAdapterConfig::default();
        config.descriptor.modify_cancel_supported = false;
        let mut engine = BrokerMutationEngine::new(config);

        let error = engine
            .apply_control_request(sample_control_request(
                RuntimeControlAction::CancelOpenOrders,
            ))
            .expect_err("cancel control should reject without cancel capability");
        assert_eq!(BrokerMutationError::ModifyCancelSupportRequired, error);
    }

    #[test]
    fn flatten_control_requires_flatten_support() {
        let mut config = BrokerAdapterConfig::default();
        config.descriptor.flatten_supported = false;
        let mut engine = BrokerMutationEngine::new(config);

        let error = engine
            .apply_control_request(sample_control_request(
                RuntimeControlAction::FlattenPositions,
            ))
            .expect_err("flatten control should reject without flatten support");
        assert_eq!(BrokerMutationError::FlattenSupportRequired, error);
    }

    #[test]
    fn late_fill_after_cancel_keeps_original_mapping_count_stable() {
        let mut engine = BrokerMutationEngine::new(BrokerAdapterConfig::default());
        let submit = engine
            .submit_order_intent(sample_submit_request())
            .expect("submit should succeed");
        let broker_order_id = submit.broker_order_ids[0].clone();
        engine
            .apply_control_request(sample_control_request(
                RuntimeControlAction::CancelOpenOrders,
            ))
            .expect("cancel control should succeed");
        let receipt = engine
            .record_callback(BrokerCallback::new(
                "late-fill-1",
                broker_order_id,
                BrokerCallbackKind::Fill,
            ))
            .expect("late fill should still resolve to the original mapping");

        assert_eq!(2, engine.intent_record_count());
        assert_eq!(submit.order_intent_id, receipt.order_intent_id);
        assert!(!receipt.deduplicated);
    }
}
