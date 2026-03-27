//! Operational-daemon runtime backbone for the execution stack.
//!
//! This crate defines the first real `opsd` daemon surface: explicit module
//! boundaries, bounded internal mailboxes, single-writer runtime state
//! ownership, and operator ingress routing through `ops_http`.

mod mailbox;
mod runtime;
mod topology;

pub use mailbox::{
    BoundedMailbox, MailboxBackpressureDiagnostic, MailboxSnapshot, MessageKind, MessagePriority,
    RuntimeMessage,
};
pub use runtime::{
    DispatchError, DispatchReceipt, HealthReport, OperatorRequest, OpsdRuntime, StartupReport,
};
pub use topology::{
    ALL_STATE_SURFACES, CRATE_ROLE, ModuleBoundary, OPSD_BOUNDARY, OPSD_MODULE_BOUNDARIES,
    OPSD_MODULES, OPSD_READABLE_ROOTS, OPSD_WRITABLE_ROOTS, OpsdBoundary, OpsdModule,
    RuntimeControlAction, RuntimeStateSurface, artifact_ingress_allowed, module_boundary,
    state_owner,
};
