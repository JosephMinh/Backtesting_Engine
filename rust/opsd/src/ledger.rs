use std::collections::{BTreeMap, BTreeSet};

/// Session-close result retained before authoritative statement ingestion runs.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionCloseStatus {
    Pass,
    ReviewRequired,
    Violation,
}

impl SessionCloseStatus {
    /// Stable identifier for logs and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "pass",
            Self::ReviewRequired => "review_required",
            Self::Violation => "violation",
        }
    }
}

/// Canonical internal-ledger event classes aligned with the plan contract.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LedgerEventClass {
    BookedFill,
    BookedFee,
    BookedCommission,
    BookedCashMovement,
    BrokerEodPosition,
    BrokerEodMarginSnapshot,
    ReconciliationAdjustment,
    Restatement,
    UnresolvedDiscrepancy,
}

impl LedgerEventClass {
    /// Stable identifier for diagnostics and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::BookedFill => "booked_fill",
            Self::BookedFee => "booked_fee",
            Self::BookedCommission => "booked_commission",
            Self::BookedCashMovement => "booked_cash_movement",
            Self::BrokerEodPosition => "broker_eod_position",
            Self::BrokerEodMarginSnapshot => "broker_eod_margin_snapshot",
            Self::ReconciliationAdjustment => "reconciliation_adjustment",
            Self::Restatement => "restatement",
            Self::UnresolvedDiscrepancy => "unresolved_discrepancy",
        }
    }

    const fn is_booked(self) -> bool {
        matches!(
            self,
            Self::BookedFill | Self::BookedFee | Self::BookedCommission | Self::BookedCashMovement
        )
    }

    const fn is_reconciling(self) -> bool {
        matches!(self, Self::ReconciliationAdjustment | Self::Restatement)
    }
}

/// Incoming event request booked by the runtime before authoritative reconciliation.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LedgerEventRequest {
    pub event_class: LedgerEventClass,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub occurred_at_utc: String,
    pub description: String,
    pub correlation_id: String,
    pub order_intent_id: Option<String>,
    pub broker_order_id: Option<String>,
    pub source_callback_id: Option<String>,
    pub reference_event_id: Option<String>,
    pub discrepancy_id: Option<String>,
    pub position_delta_contracts: i64,
    pub cash_delta_usd_cents: i64,
    pub realized_pnl_delta_usd_cents: i64,
    pub fee_delta_usd_cents: i64,
    pub commission_delta_usd_cents: i64,
    pub authoritative_position_contracts: Option<i64>,
    pub authoritative_initial_margin_requirement_usd_cents: Option<i64>,
    pub authoritative_maintenance_margin_requirement_usd_cents: Option<i64>,
    pub source_artifact_ids: Vec<String>,
}

/// Append-only event recorded by the runtime ledger.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LedgerEvent {
    pub sequence_id: u64,
    pub event_id: String,
    pub event_class: LedgerEventClass,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub occurred_at_utc: String,
    pub description: String,
    pub correlation_id: String,
    pub order_intent_id: Option<String>,
    pub broker_order_id: Option<String>,
    pub source_callback_id: Option<String>,
    pub reference_event_id: Option<String>,
    pub discrepancy_id: Option<String>,
    pub position_delta_contracts: i64,
    pub cash_delta_usd_cents: i64,
    pub realized_pnl_delta_usd_cents: i64,
    pub fee_delta_usd_cents: i64,
    pub commission_delta_usd_cents: i64,
    pub authoritative_position_contracts: Option<i64>,
    pub authoritative_initial_margin_requirement_usd_cents: Option<i64>,
    pub authoritative_maintenance_margin_requirement_usd_cents: Option<i64>,
    pub source_artifact_ids: Vec<String>,
}

/// Aggregated internal totals exposed by a ledger close.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LedgerTotals {
    pub position_contracts: i64,
    pub cash_balance_usd_cents: i64,
    pub realized_pnl_usd_cents: i64,
    pub fee_total_usd_cents: i64,
    pub commission_total_usd_cents: i64,
}

/// Latest authoritative broker snapshot carried through session close assembly.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrokerAuthoritativeSnapshot {
    pub position_contracts: Option<i64>,
    pub initial_margin_requirement_usd_cents: Option<i64>,
    pub maintenance_margin_requirement_usd_cents: Option<i64>,
    pub position_event_id: Option<String>,
    pub margin_event_id: Option<String>,
    pub source_timestamp_utc: Option<String>,
}

/// Machine-readable difference retained for later reconciliation review.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LedgerDifference {
    pub metric: String,
    pub as_booked: Option<i64>,
    pub as_reconciled: Option<i64>,
    pub authoritative: Option<i64>,
    pub booked_vs_reconciled_delta: Option<i64>,
    pub reconciled_vs_authoritative_delta: Option<i64>,
    pub explanation: String,
}

/// Append-only integrity check retained in the session-close artifact.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AppendOnlyIntegrityReport {
    pub valid: bool,
    pub reason_code: String,
    pub explanation: String,
    pub duplicate_event_id: Option<String>,
    pub violating_sequence_id: Option<u64>,
}

/// Session-close manifest for users and later reconciliation consumers.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionCloseManifest {
    pub manifest_id: String,
    pub close_id: String,
    pub trace_event_ids: Vec<String>,
    pub event_artifact_ids: Vec<String>,
    pub source_callback_ids: Vec<String>,
}

/// As-booked session-close artifact retained before authoritative statement reconciliation.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionCloseArtifact {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub close_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub compiled_schedule_artifact_id: String,
    pub status: SessionCloseStatus,
    pub reason_code: String,
    pub append_only_integrity: AppendOnlyIntegrityReport,
    pub event_classes_present: Vec<String>,
    pub trace_event_ids: Vec<String>,
    pub as_booked_totals: LedgerTotals,
    pub as_reconciled_totals: LedgerTotals,
    pub broker_authoritative_snapshot: BrokerAuthoritativeSnapshot,
    pub differences: Vec<LedgerDifference>,
    pub unresolved_discrepancy_ids: Vec<String>,
    pub restatement_event_ids: Vec<String>,
    pub manifest: SessionCloseManifest,
    pub explanation: String,
    pub close_completed_at_utc: String,
}

/// External request to build a session-close artifact.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionCloseRequest {
    pub close_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub compiled_schedule_artifact_id: String,
    pub close_completed_at_utc: String,
}

/// Receipt for an event booked into the append-only ledger.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LedgerEntryReceipt {
    pub event_id: String,
    pub sequence_id: u64,
    pub idempotent_replay: bool,
    pub retained_artifact_id: String,
}

/// Ledger booking and close-building failures.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum LedgerError {
    InvalidTimestamp {
        field: &'static str,
        value: String,
    },
    MissingRequiredField {
        field: &'static str,
    },
    EmptySourceArtifactIds,
    NoEventsForSessionClose {
        account_id: String,
        symbol: String,
        session_id: String,
    },
}

/// Append-only internal accounting ledger retained inside the runtime.
#[derive(Clone, Debug, Default)]
pub struct AccountingLedger {
    events: Vec<LedgerEvent>,
    retained_event_artifact_ids: BTreeMap<String, String>,
    callback_receipts: BTreeMap<String, LedgerEntryReceipt>,
    next_sequence_id: u64,
    next_manifest_sequence: usize,
    next_close_sequence: usize,
}

impl AccountingLedger {
    pub fn new() -> Self {
        Self {
            events: Vec::new(),
            retained_event_artifact_ids: BTreeMap::new(),
            callback_receipts: BTreeMap::new(),
            next_sequence_id: 1,
            next_manifest_sequence: 1,
            next_close_sequence: 1,
        }
    }

    /// Returns booked append-only events in insertion order.
    pub fn events(&self) -> &[LedgerEvent] {
        &self.events
    }

    /// Returns cloned events for a single account, symbol, and session scope.
    pub fn scoped_events(
        &self,
        account_id: &str,
        symbol: &str,
        session_id: &str,
    ) -> Vec<LedgerEvent> {
        self.events
            .iter()
            .filter(|event| {
                event.account_id == account_id
                    && event.symbol == symbol
                    && event.session_id == session_id
            })
            .cloned()
            .collect()
    }

    /// Appends an internal-ledger event or returns the original receipt for a duplicate callback.
    pub fn append_event(
        &mut self,
        request: LedgerEventRequest,
    ) -> Result<LedgerEntryReceipt, LedgerError> {
        validate_utc_timestamp("occurred_at_utc", &request.occurred_at_utc)?;
        ensure_non_empty("account_id", &request.account_id)?;
        ensure_non_empty("symbol", &request.symbol)?;
        ensure_non_empty("session_id", &request.session_id)?;
        ensure_non_empty("description", &request.description)?;
        if request.source_artifact_ids.is_empty() {
            return Err(LedgerError::EmptySourceArtifactIds);
        }
        if let Some(callback_id) = request.source_callback_id.as_ref() {
            if let Some(existing) = self.callback_receipts.get(callback_id) {
                return Ok(LedgerEntryReceipt {
                    event_id: existing.event_id.clone(),
                    sequence_id: existing.sequence_id,
                    idempotent_replay: true,
                    retained_artifact_id: existing.retained_artifact_id.clone(),
                });
            }
        }

        let sequence_id = self.next_sequence_id;
        self.next_sequence_id += 1;
        let event_id = format!("ledger-event-{sequence_id:06}");
        let retained_artifact_id = format!("runtime_state/ledger/events/{event_id}.json");
        let event = LedgerEvent {
            sequence_id,
            event_id: event_id.clone(),
            event_class: request.event_class,
            account_id: request.account_id,
            symbol: request.symbol,
            session_id: request.session_id,
            occurred_at_utc: request.occurred_at_utc,
            description: request.description,
            correlation_id: request.correlation_id,
            order_intent_id: request.order_intent_id,
            broker_order_id: request.broker_order_id,
            source_callback_id: request.source_callback_id.clone(),
            reference_event_id: request.reference_event_id,
            discrepancy_id: request.discrepancy_id,
            position_delta_contracts: request.position_delta_contracts,
            cash_delta_usd_cents: request.cash_delta_usd_cents,
            realized_pnl_delta_usd_cents: request.realized_pnl_delta_usd_cents,
            fee_delta_usd_cents: request.fee_delta_usd_cents,
            commission_delta_usd_cents: request.commission_delta_usd_cents,
            authoritative_position_contracts: request.authoritative_position_contracts,
            authoritative_initial_margin_requirement_usd_cents: request
                .authoritative_initial_margin_requirement_usd_cents,
            authoritative_maintenance_margin_requirement_usd_cents: request
                .authoritative_maintenance_margin_requirement_usd_cents,
            source_artifact_ids: request.source_artifact_ids,
        };
        let receipt = LedgerEntryReceipt {
            event_id: event_id.clone(),
            sequence_id,
            idempotent_replay: false,
            retained_artifact_id: retained_artifact_id.clone(),
        };
        if let Some(callback_id) = event.source_callback_id.as_ref() {
            self.callback_receipts
                .insert(callback_id.clone(), receipt.clone());
        }
        self.retained_event_artifact_ids
            .insert(event_id.clone(), retained_artifact_id);
        self.events.push(event);
        Ok(receipt)
    }

    /// Builds the as-booked session-close artifact for a single session scope.
    pub fn build_session_close_artifact(
        &mut self,
        request: SessionCloseRequest,
    ) -> Result<SessionCloseArtifact, LedgerError> {
        validate_utc_timestamp("close_completed_at_utc", &request.close_completed_at_utc)?;
        ensure_non_empty("close_id", &request.close_id)?;
        ensure_non_empty("account_id", &request.account_id)?;
        ensure_non_empty("symbol", &request.symbol)?;
        ensure_non_empty("session_id", &request.session_id)?;
        ensure_non_empty(
            "compiled_schedule_artifact_id",
            &request.compiled_schedule_artifact_id,
        )?;

        let scoped = self
            .events
            .iter()
            .filter(|event| {
                event.account_id == request.account_id
                    && event.symbol == request.symbol
                    && event.session_id == request.session_id
            })
            .cloned()
            .collect::<Vec<_>>();
        if scoped.is_empty() {
            return Err(LedgerError::NoEventsForSessionClose {
                account_id: request.account_id,
                symbol: request.symbol,
                session_id: request.session_id,
            });
        }

        let integrity = validate_append_only_ledger(&scoped);
        let as_booked_totals = aggregate_totals(&scoped, |class| class.is_booked());
        let as_reconciled_totals =
            aggregate_totals(&scoped, |class| class.is_booked() || class.is_reconciling());
        let broker_authoritative_snapshot = latest_broker_snapshot(&scoped);
        let unresolved_discrepancy_ids = unresolved_discrepancy_ids(&scoped);
        let status = if !integrity.valid {
            SessionCloseStatus::Violation
        } else if !unresolved_discrepancy_ids.is_empty() {
            SessionCloseStatus::ReviewRequired
        } else {
            SessionCloseStatus::Pass
        };
        let (reason_code, explanation) = match status {
            SessionCloseStatus::Pass => (
                "SESSION_CLOSE_BOOKED_ARTIFACT_READY".to_string(),
                "The append-only internal ledger is clean and the as-booked session-close artifact is ready for authoritative reconciliation.".to_string(),
            ),
            SessionCloseStatus::ReviewRequired => (
                "SESSION_CLOSE_UNRESOLVED_DISCREPANCY".to_string(),
                "The as-booked session close retained unresolved discrepancy state and must be reviewed before the next-session path trusts it.".to_string(),
            ),
            SessionCloseStatus::Violation => (
                integrity.reason_code.clone(),
                integrity.explanation.clone(),
            ),
        };

        let manifest_id = format!("ledger-manifest-{:04}", self.next_manifest_sequence);
        self.next_manifest_sequence += 1;
        let artifact_id = format!("ledger-close-{:04}", self.next_close_sequence);
        self.next_close_sequence += 1;
        let close_id = request.close_id.clone();
        let trace_event_ids = scoped
            .iter()
            .map(|event| event.event_id.clone())
            .collect::<Vec<_>>();
        let event_artifact_ids = trace_event_ids
            .iter()
            .filter_map(|event_id| self.retained_event_artifact_ids.get(event_id).cloned())
            .collect::<Vec<_>>();
        let source_callback_ids = scoped
            .iter()
            .filter_map(|event| event.source_callback_id.clone())
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect::<Vec<_>>();

        Ok(SessionCloseArtifact {
            artifact_id: artifact_id.clone(),
            retained_artifact_id: format!("runtime_state/ledger/closes/{artifact_id}.json"),
            close_id: close_id.clone(),
            account_id: request.account_id,
            symbol: request.symbol,
            session_id: request.session_id,
            compiled_schedule_artifact_id: request.compiled_schedule_artifact_id,
            status,
            reason_code,
            append_only_integrity: integrity,
            event_classes_present: scoped
                .iter()
                .map(|event| event.event_class.as_str().to_string())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect(),
            trace_event_ids: trace_event_ids.clone(),
            as_booked_totals: as_booked_totals.clone(),
            as_reconciled_totals: as_reconciled_totals.clone(),
            broker_authoritative_snapshot: broker_authoritative_snapshot.clone(),
            differences: build_differences(
                &as_booked_totals,
                &as_reconciled_totals,
                &broker_authoritative_snapshot,
            ),
            unresolved_discrepancy_ids: unresolved_discrepancy_ids.clone(),
            restatement_event_ids: scoped
                .iter()
                .filter(|event| event.event_class == LedgerEventClass::Restatement)
                .map(|event| event.event_id.clone())
                .collect(),
            manifest: SessionCloseManifest {
                manifest_id: manifest_id.clone(),
                close_id: close_id.clone(),
                trace_event_ids,
                event_artifact_ids,
                source_callback_ids,
            },
            explanation,
            close_completed_at_utc: request.close_completed_at_utc,
        })
    }
}

/// Validates append-only integrity for a session-scoped event stream.
pub fn validate_append_only_ledger(events: &[LedgerEvent]) -> AppendOnlyIntegrityReport {
    let mut previous_sequence = None;
    let mut seen_event_ids = BTreeSet::new();
    for event in events {
        if previous_sequence.is_some_and(|previous| event.sequence_id <= previous) {
            return AppendOnlyIntegrityReport {
                valid: false,
                reason_code: "LEDGER_SEQUENCE_OUT_OF_ORDER".to_string(),
                explanation: "Append-only ledger sequence must remain strictly increasing."
                    .to_string(),
                duplicate_event_id: None,
                violating_sequence_id: Some(event.sequence_id),
            };
        }
        if !seen_event_ids.insert(event.event_id.clone()) {
            return AppendOnlyIntegrityReport {
                valid: false,
                reason_code: "LEDGER_EVENT_ID_DUPLICATE".to_string(),
                explanation: "Ledger event identifiers must remain unique.".to_string(),
                duplicate_event_id: Some(event.event_id.clone()),
                violating_sequence_id: Some(event.sequence_id),
            };
        }
        previous_sequence = Some(event.sequence_id);
    }
    AppendOnlyIntegrityReport {
        valid: true,
        reason_code: "LEDGER_APPEND_ONLY_VALID".to_string(),
        explanation: "Ledger sequence is append-only and uniquely identified.".to_string(),
        duplicate_event_id: None,
        violating_sequence_id: None,
    }
}

fn aggregate_totals(
    events: &[LedgerEvent],
    include: impl Fn(LedgerEventClass) -> bool,
) -> LedgerTotals {
    let mut totals = LedgerTotals {
        position_contracts: 0,
        cash_balance_usd_cents: 0,
        realized_pnl_usd_cents: 0,
        fee_total_usd_cents: 0,
        commission_total_usd_cents: 0,
    };
    for event in events {
        if !include(event.event_class) {
            continue;
        }
        totals.position_contracts += event.position_delta_contracts;
        totals.cash_balance_usd_cents += event.cash_delta_usd_cents;
        totals.realized_pnl_usd_cents += event.realized_pnl_delta_usd_cents;
        totals.fee_total_usd_cents += event.fee_delta_usd_cents;
        totals.commission_total_usd_cents += event.commission_delta_usd_cents;
    }
    totals
}

fn latest_broker_snapshot(events: &[LedgerEvent]) -> BrokerAuthoritativeSnapshot {
    let mut snapshot = BrokerAuthoritativeSnapshot {
        position_contracts: None,
        initial_margin_requirement_usd_cents: None,
        maintenance_margin_requirement_usd_cents: None,
        position_event_id: None,
        margin_event_id: None,
        source_timestamp_utc: None,
    };
    for event in events {
        if event.event_class == LedgerEventClass::BrokerEodPosition {
            snapshot.position_contracts = event.authoritative_position_contracts;
            snapshot.position_event_id = Some(event.event_id.clone());
            snapshot.source_timestamp_utc = Some(event.occurred_at_utc.clone());
        }
        if event.event_class == LedgerEventClass::BrokerEodMarginSnapshot {
            snapshot.initial_margin_requirement_usd_cents =
                event.authoritative_initial_margin_requirement_usd_cents;
            snapshot.maintenance_margin_requirement_usd_cents =
                event.authoritative_maintenance_margin_requirement_usd_cents;
            snapshot.margin_event_id = Some(event.event_id.clone());
            snapshot.source_timestamp_utc = Some(event.occurred_at_utc.clone());
        }
    }
    snapshot
}

fn unresolved_discrepancy_ids(events: &[LedgerEvent]) -> Vec<String> {
    let mut opened = Vec::new();
    let mut resolved = BTreeSet::new();
    for event in events {
        let Some(discrepancy_id) = event.discrepancy_id.as_ref() else {
            continue;
        };
        if event.event_class == LedgerEventClass::UnresolvedDiscrepancy {
            opened.push(discrepancy_id.clone());
        }
        if event.event_class.is_reconciling() {
            resolved.insert(discrepancy_id.clone());
        }
    }
    opened
        .into_iter()
        .filter(|discrepancy_id| !resolved.contains(discrepancy_id))
        .collect()
}

fn build_differences(
    as_booked: &LedgerTotals,
    as_reconciled: &LedgerTotals,
    snapshot: &BrokerAuthoritativeSnapshot,
) -> Vec<LedgerDifference> {
    vec![
        difference(
            "position_contracts",
            Some(as_booked.position_contracts),
            Some(as_reconciled.position_contracts),
            snapshot.position_contracts,
            "Open-contract count must reconcile to broker-close position state.",
        ),
        difference(
            "cash_balance_usd_cents",
            Some(as_booked.cash_balance_usd_cents),
            Some(as_reconciled.cash_balance_usd_cents),
            None,
            "Cash balance remains explicit as booked versus reconciled runtime truth.",
        ),
        difference(
            "realized_pnl_usd_cents",
            Some(as_booked.realized_pnl_usd_cents),
            Some(as_reconciled.realized_pnl_usd_cents),
            None,
            "Realized PnL stays distinguishable from later corrections and restatements.",
        ),
        difference(
            "fee_total_usd_cents",
            Some(as_booked.fee_total_usd_cents),
            Some(as_reconciled.fee_total_usd_cents),
            None,
            "Booked fees remain explicit instead of disappearing inside net PnL.",
        ),
        difference(
            "commission_total_usd_cents",
            Some(as_booked.commission_total_usd_cents),
            Some(as_reconciled.commission_total_usd_cents),
            None,
            "Booked commissions remain explicit instead of disappearing inside net PnL.",
        ),
        difference(
            "broker_initial_margin_requirement_usd_cents",
            None,
            None,
            snapshot.initial_margin_requirement_usd_cents,
            "Broker initial margin remains an authoritative snapshot rather than a booked cash event.",
        ),
        difference(
            "broker_maintenance_margin_requirement_usd_cents",
            None,
            None,
            snapshot.maintenance_margin_requirement_usd_cents,
            "Broker maintenance margin remains an authoritative snapshot rather than a booked cash event.",
        ),
    ]
}

fn difference(
    metric: &str,
    as_booked: Option<i64>,
    as_reconciled: Option<i64>,
    authoritative: Option<i64>,
    explanation: &str,
) -> LedgerDifference {
    let booked_vs_reconciled_delta = as_booked.zip(as_reconciled).map(|(lhs, rhs)| rhs - lhs);
    let reconciled_vs_authoritative_delta =
        as_reconciled.zip(authoritative).map(|(lhs, rhs)| lhs - rhs);
    LedgerDifference {
        metric: metric.to_string(),
        as_booked,
        as_reconciled,
        authoritative,
        booked_vs_reconciled_delta,
        reconciled_vs_authoritative_delta,
        explanation: explanation.to_string(),
    }
}

fn ensure_non_empty(field: &'static str, value: &str) -> Result<(), LedgerError> {
    if value.is_empty() {
        Err(LedgerError::MissingRequiredField { field })
    } else {
        Ok(())
    }
}

fn validate_utc_timestamp(field: &'static str, value: &str) -> Result<(), LedgerError> {
    let bytes = value.as_bytes();
    let valid = bytes.len() == 20
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes[10] == b'T'
        && bytes[13] == b':'
        && bytes[16] == b':'
        && bytes[19] == b'Z'
        && bytes.iter().enumerate().all(|(index, byte)| {
            matches!(index, 4 | 7 | 10 | 13 | 16 | 19) || byte.is_ascii_digit()
        });
    if valid {
        Ok(())
    } else {
        Err(LedgerError::InvalidTimestamp {
            field,
            value: value.to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AccountingLedger, LedgerEventClass, LedgerEventRequest, SessionCloseRequest,
        SessionCloseStatus,
    };

    fn booked_fill_request() -> LedgerEventRequest {
        LedgerEventRequest {
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
        }
    }

    #[test]
    fn duplicate_callback_booking_is_idempotent() {
        let mut ledger = AccountingLedger::new();
        let first = ledger
            .append_event(booked_fill_request())
            .expect("first booked fill should append");
        let second = ledger
            .append_event(booked_fill_request())
            .expect("duplicate callback should reuse the first ledger receipt");

        assert!(!first.idempotent_replay);
        assert!(second.idempotent_replay);
        assert_eq!(first.event_id, second.event_id);
        assert_eq!(1, ledger.events().len());
    }

    #[test]
    fn session_close_distinguishes_as_booked_from_as_reconciled() {
        let mut ledger = AccountingLedger::new();
        ledger
            .append_event(booked_fill_request())
            .expect("booked fill should append");
        ledger
            .append_event(LedgerEventRequest {
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
                source_artifact_ids: vec!["artifact-0002".to_string()],
            })
            .expect("booked commission should append");
        ledger
            .append_event(LedgerEventRequest {
                event_class: LedgerEventClass::ReconciliationAdjustment,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T22:05:00Z".to_string(),
                description: "Late commission correction".to_string(),
                correlation_id: "reconcile-corr-1".to_string(),
                order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
                broker_order_id: Some("broker-order-1".to_string()),
                source_callback_id: None,
                reference_event_id: Some("ledger-event-000002".to_string()),
                discrepancy_id: Some("disc-1".to_string()),
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: -10,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-0003".to_string()],
            })
            .expect("reconciliation adjustment should append");
        ledger
            .append_event(LedgerEventRequest {
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
        ledger
            .append_event(LedgerEventRequest {
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

        let close = ledger
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

        assert_eq!(SessionCloseStatus::Pass, close.status);
        assert_eq!(1, close.as_booked_totals.position_contracts);
        assert_eq!(55, close.as_booked_totals.commission_total_usd_cents);
        assert_eq!(45, close.as_reconciled_totals.commission_total_usd_cents);
        assert_eq!(
            Some(125_000),
            close
                .broker_authoritative_snapshot
                .initial_margin_requirement_usd_cents
        );
        assert!(
            close
                .differences
                .iter()
                .any(|difference| difference.metric == "commission_total_usd_cents")
        );
    }

    #[test]
    fn unresolved_discrepancy_forces_review_required_session_close() {
        let mut ledger = AccountingLedger::new();
        ledger
            .append_event(LedgerEventRequest {
                event_class: LedgerEventClass::UnresolvedDiscrepancy,
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                occurred_at_utc: "2026-03-18T20:00:00Z".to_string(),
                description: "Unresolved discrepancy".to_string(),
                correlation_id: "disc-corr-1".to_string(),
                order_intent_id: None,
                broker_order_id: None,
                source_callback_id: None,
                reference_event_id: None,
                discrepancy_id: Some("disc-1".to_string()),
                position_delta_contracts: 0,
                cash_delta_usd_cents: 0,
                realized_pnl_delta_usd_cents: 0,
                fee_delta_usd_cents: 0,
                commission_delta_usd_cents: 0,
                authoritative_position_contracts: None,
                authoritative_initial_margin_requirement_usd_cents: None,
                authoritative_maintenance_margin_requirement_usd_cents: None,
                source_artifact_ids: vec!["artifact-disc-1".to_string()],
            })
            .expect("discrepancy should append");

        let close = ledger
            .build_session_close_artifact(SessionCloseRequest {
                close_id: "close-disc".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                compiled_schedule_artifact_id:
                    "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
                close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
            })
            .expect("session close should build");

        assert_eq!(SessionCloseStatus::ReviewRequired, close.status);
        assert_eq!(vec!["disc-1".to_string()], close.unresolved_discrepancy_ids);
    }
}
