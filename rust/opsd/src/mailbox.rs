use std::collections::VecDeque;

use crate::{OpsdModule, RuntimeControlAction};

/// Priority lane inside a bounded mailbox.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MessagePriority {
    Standard,
    High,
}

impl MessagePriority {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Standard => "standard",
            Self::High => "high",
        }
    }
}

/// Canonical message types exchanged between daemon modules.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum MessageKind {
    MarketStateUpdate,
    HealthProbe,
    ReconciliationTick,
    ControlAction(RuntimeControlAction),
}

impl MessageKind {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(&self) -> &'static str {
        match self {
            Self::MarketStateUpdate => "market_state_update",
            Self::HealthProbe => "health_probe",
            Self::ReconciliationTick => "reconciliation_tick",
            Self::ControlAction(action) => action.as_str(),
        }
    }
}

/// Runtime message routed through a bounded mailbox.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuntimeMessage {
    pub correlation_id: String,
    pub source: OpsdModule,
    pub target: OpsdModule,
    pub kind: MessageKind,
    pub priority: MessagePriority,
    pub summary: String,
}

impl RuntimeMessage {
    /// Creates a control message emitted by `ops_http`.
    pub fn control_action(
        correlation_id: impl Into<String>,
        target: OpsdModule,
        action: RuntimeControlAction,
        operator_id: impl Into<String>,
    ) -> Self {
        let priority = match action {
            RuntimeControlAction::CancelOpenOrders
            | RuntimeControlAction::FlattenPositions
            | RuntimeControlAction::MarkSessionNotReady
            | RuntimeControlAction::PublishSessionReadinessPacket => MessagePriority::High,
            RuntimeControlAction::HaltNewOrders | RuntimeControlAction::AssertKillSwitch => {
                MessagePriority::Standard
            }
        };
        let operator_id = operator_id.into();
        Self {
            correlation_id: correlation_id.into(),
            source: OpsdModule::OpsHttp,
            target,
            kind: MessageKind::ControlAction(action),
            priority,
            summary: format!("ops_http relayed {} for {operator_id}", action.as_str()),
        }
    }

    /// Creates a standard health probe routed through `ops_http`.
    pub fn health_probe(correlation_id: impl Into<String>, target: OpsdModule) -> Self {
        Self {
            correlation_id: correlation_id.into(),
            source: OpsdModule::OpsHttp,
            target,
            kind: MessageKind::HealthProbe,
            priority: MessagePriority::Standard,
            summary: format!("ops_http health probe for {}", target.as_str()),
        }
    }

    /// Creates a high-priority reconciliation tick.
    pub fn reconciliation_tick(
        correlation_id: impl Into<String>,
        source: OpsdModule,
        summary: impl Into<String>,
    ) -> Self {
        Self {
            correlation_id: correlation_id.into(),
            source,
            target: OpsdModule::Reconciliation,
            kind: MessageKind::ReconciliationTick,
            priority: MessagePriority::High,
            summary: summary.into(),
        }
    }
}

/// Structured diagnostic retained when mailbox backpressure rejects a message.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MailboxBackpressureDiagnostic {
    pub mailbox_owner: OpsdModule,
    pub priority: MessagePriority,
    pub capacity: usize,
    pub depth: usize,
    pub correlation_id: String,
    pub message_kind: MessageKind,
}

/// Snapshot of a mailbox's current queue depths.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MailboxSnapshot {
    pub owner: OpsdModule,
    pub standard_depth: usize,
    pub high_priority_depth: usize,
    pub rejected_messages: usize,
}

/// In-process bounded mailbox with a reserved high-priority lane.
#[derive(Clone, Debug)]
pub struct BoundedMailbox {
    owner: OpsdModule,
    standard_capacity: usize,
    high_priority_capacity: usize,
    standard_queue: VecDeque<RuntimeMessage>,
    high_priority_queue: VecDeque<RuntimeMessage>,
    rejected_messages: usize,
}

impl BoundedMailbox {
    /// Creates a bounded mailbox for a single daemon module.
    pub fn new(owner: OpsdModule, standard_capacity: usize, high_priority_capacity: usize) -> Self {
        Self {
            owner,
            standard_capacity,
            high_priority_capacity,
            standard_queue: VecDeque::with_capacity(standard_capacity),
            high_priority_queue: VecDeque::with_capacity(high_priority_capacity),
            rejected_messages: 0,
        }
    }

    /// Attempts to enqueue a message and returns structured backpressure diagnostics on failure.
    pub fn try_send(
        &mut self,
        message: RuntimeMessage,
    ) -> Result<(), MailboxBackpressureDiagnostic> {
        let (queue, capacity) = match message.priority {
            MessagePriority::Standard => (&mut self.standard_queue, self.standard_capacity),
            MessagePriority::High => (&mut self.high_priority_queue, self.high_priority_capacity),
        };
        if queue.len() >= capacity {
            self.rejected_messages += 1;
            return Err(MailboxBackpressureDiagnostic {
                mailbox_owner: self.owner,
                priority: message.priority,
                capacity,
                depth: queue.len(),
                correlation_id: message.correlation_id,
                message_kind: message.kind,
            });
        }
        queue.push_back(message);
        Ok(())
    }

    /// Pops the next message, always prioritizing the high-priority lane.
    pub fn pop_next(&mut self) -> Option<RuntimeMessage> {
        self.high_priority_queue
            .pop_front()
            .or_else(|| self.standard_queue.pop_front())
    }

    /// Returns a queue-depth snapshot for health reporting.
    pub fn snapshot(&self) -> MailboxSnapshot {
        MailboxSnapshot {
            owner: self.owner,
            standard_depth: self.standard_queue.len(),
            high_priority_depth: self.high_priority_queue.len(),
            rejected_messages: self.rejected_messages,
        }
    }

    /// Returns the owner module for the mailbox.
    pub const fn owner(&self) -> OpsdModule {
        self.owner
    }
}

#[cfg(test)]
mod tests {
    use crate::RuntimeControlAction;

    use super::{BoundedMailbox, MessageKind, MessagePriority, RuntimeMessage};
    use crate::OpsdModule;

    #[test]
    fn high_priority_messages_drain_before_standard_messages() {
        let mut mailbox = BoundedMailbox::new(OpsdModule::Broker, 2, 2);
        mailbox
            .try_send(RuntimeMessage::health_probe("probe-1", OpsdModule::Broker))
            .expect("health probe should fit");
        mailbox
            .try_send(RuntimeMessage::control_action(
                "control-1",
                OpsdModule::Broker,
                RuntimeControlAction::CancelOpenOrders,
                "operator",
            ))
            .expect("high-priority control should fit");

        let first = mailbox.pop_next().expect("first message should exist");
        let second = mailbox.pop_next().expect("second message should exist");

        assert_eq!(MessagePriority::High, first.priority);
        assert_eq!(
            MessageKind::ControlAction(RuntimeControlAction::CancelOpenOrders),
            first.kind
        );
        assert_eq!(MessagePriority::Standard, second.priority);
        assert_eq!(MessageKind::HealthProbe, second.kind);
    }

    #[test]
    fn mailbox_rejects_when_priority_lane_is_full() {
        let mut mailbox = BoundedMailbox::new(OpsdModule::Reconciliation, 1, 1);
        mailbox
            .try_send(RuntimeMessage::reconciliation_tick(
                "reconcile-1",
                OpsdModule::StateStore,
                "state-store handoff",
            ))
            .expect("first tick should fit");

        let diagnostic = mailbox
            .try_send(RuntimeMessage::reconciliation_tick(
                "reconcile-2",
                OpsdModule::Broker,
                "broker handoff",
            ))
            .expect_err("second high-priority message should overflow");

        assert_eq!(OpsdModule::Reconciliation, diagnostic.mailbox_owner);
        assert_eq!(MessagePriority::High, diagnostic.priority);
        assert_eq!(1, diagnostic.capacity);
        assert_eq!(1, diagnostic.depth);
        assert_eq!(MessageKind::ReconciliationTick, diagnostic.message_kind);
    }
}
