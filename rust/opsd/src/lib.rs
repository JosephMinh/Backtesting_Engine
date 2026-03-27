//! Operational-daemon runtime backbone for the execution stack.
//!
//! This crate defines the first real `opsd` daemon surface: explicit module
//! boundaries, bounded internal mailboxes, single-writer runtime state
//! ownership, and operator ingress routing through `ops_http`.

mod broker;
mod ledger;
mod mailbox;
mod readiness;
mod reconciliation;
mod runtime;
mod schedule;
mod topology;

pub use broker::{
    BrokerAckState, BrokerAdapterConfig, BrokerCallback, BrokerCallbackKind, BrokerCallbackReceipt,
    BrokerCapabilityDescriptor, BrokerContractDescriptor, BrokerControlRequest,
    BrokerMutationArtifact, BrokerMutationDecision, BrokerMutationEngine, BrokerMutationError,
    BrokerMutationKind, BrokerOrderIntentRequest, BrokerOrderType, BrokerTimeInForce,
    OrderIntentIdentity,
};
pub use ledger::{
    AccountingLedger, AppendOnlyIntegrityReport, BrokerAuthoritativeSnapshot, LedgerDifference,
    LedgerEntryReceipt, LedgerError, LedgerEvent, LedgerEventClass, LedgerEventRequest,
    LedgerTotals, SessionCloseArtifact, SessionCloseManifest, SessionCloseRequest,
    SessionCloseStatus, validate_append_only_ledger,
};
pub use mailbox::{
    BoundedMailbox, MailboxBackpressureDiagnostic, MailboxSnapshot, MessageKind, MessagePriority,
    RuntimeMessage,
};
pub use readiness::{
    ReadinessHistoryEntry, ReadinessProviderKind, ReadinessProviderOutput, SessionReadinessPacket,
    SessionReadinessPacketRequest, SessionReadinessStatus, assemble_session_readiness_packet,
    sample_session_readiness_request, write_session_readiness_artifacts,
};
pub use reconciliation::{
    AuthoritativeLedgerCloseArtifact, AuthoritativeStatementSet, DailyLedgerCloseRequest,
    DiscrepancyCategory, DiscrepancySummary, IntradayControlAction, IntradayReconciliationArtifact,
    IntradayReconciliationRequest, NextSessionEligibility, ReconciliationEngine,
    ReconciliationError, ReconciliationManifest, ReconciliationStatus,
};
pub use runtime::{
    BrokerMutationReceipt, DispatchError, DispatchReceipt, HealthReport, OperatorRequest,
    OpsdRuntime, StartupReport,
};
pub use schedule::{
    CompiledSessionArtifact, CompiledSessionSlice, CompiledSessionState,
    DeliveryFenceWindowDefinition, MaintenanceWindowDefinition, PolicyOverlayWindowDefinition,
    ScheduleCompileRequest, ScheduleError, SessionCalendarEntry, SessionDayKind,
    SessionTopologyDecision, compile_schedule,
};
pub use topology::{
    ALL_STATE_SURFACES, CRATE_ROLE, ModuleBoundary, OPSD_BOUNDARY, OPSD_MODULE_BOUNDARIES,
    OPSD_MODULES, OPSD_READABLE_ROOTS, OPSD_WRITABLE_ROOTS, OpsdBoundary, OpsdModule,
    RuntimeControlAction, RuntimeStateSurface, artifact_ingress_allowed, module_boundary,
    state_owner,
};
