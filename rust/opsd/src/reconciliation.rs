use std::collections::BTreeSet;

use crate::{LedgerEvent, LedgerEventClass, SessionCloseArtifact, SessionCloseStatus};

/// Stable reconciliation status used by intraday and end-of-day artifacts.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReconciliationStatus {
    Pass,
    ReviewRequired,
    Violation,
}

impl ReconciliationStatus {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "pass",
            Self::ReviewRequired => "review_required",
            Self::Violation => "violation",
        }
    }
}

/// Explicit operator-facing action required by an intraday mismatch.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IntradayControlAction {
    None,
    Restrict,
    ExitOnly,
    FlattenAndWithdraw,
}

impl IntradayControlAction {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::None => "none",
            Self::Restrict => "restrict",
            Self::ExitOnly => "exit_only",
            Self::FlattenAndWithdraw => "flatten_and_withdraw",
        }
    }
}

/// Next-session disposition emitted by the authoritative daily close.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NextSessionEligibility {
    Eligible,
    Blocked,
    ReviewRequired,
}

impl NextSessionEligibility {
    /// Stable identifier for diagnostics and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Eligible => "eligible",
            Self::Blocked => "blocked",
            Self::ReviewRequired => "review_required",
        }
    }
}

/// Machine-readable discrepancy classes retained for runtime review.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DiscrepancyCategory {
    PositionContracts,
    WorkingOrders,
    FillExecutionIds,
    TradingPermissions,
    CashMovements,
    Fees,
    Commissions,
    RealizedPnl,
    UnrealizedPnl,
    InitialMargin,
    MaintenanceMargin,
    UnresolvedDiscrepancy,
}

impl DiscrepancyCategory {
    /// Stable identifier for diagnostics and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::PositionContracts => "position_contracts",
            Self::WorkingOrders => "working_orders",
            Self::FillExecutionIds => "fill_execution_ids",
            Self::TradingPermissions => "trading_permissions",
            Self::CashMovements => "cash_movements",
            Self::Fees => "fees",
            Self::Commissions => "commissions",
            Self::RealizedPnl => "realized_pnl",
            Self::UnrealizedPnl => "unrealized_pnl",
            Self::InitialMargin => "initial_margin_requirement",
            Self::MaintenanceMargin => "maintenance_margin_requirement",
            Self::UnresolvedDiscrepancy => "unresolved_discrepancy",
        }
    }
}

/// Durable discrepancy summary retained in intraday and daily-close artifacts.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DiscrepancySummary {
    pub discrepancy_id: String,
    pub category: DiscrepancyCategory,
    pub local_value: String,
    pub authoritative_value: String,
    pub delta: Option<i64>,
    pub above_tolerance: bool,
    pub provenance_artifact_ids: Vec<String>,
    pub explanation: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct DiscrepancyDraft {
    category: DiscrepancyCategory,
    local_value: String,
    authoritative_value: String,
    delta: Option<i64>,
    above_tolerance: bool,
    provenance_artifact_ids: Vec<String>,
    explanation: String,
}

/// Manifest linking retained reconciliation artifacts back to their inputs.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReconciliationManifest {
    pub manifest_id: String,
    pub root_artifact_id: String,
    pub input_artifact_ids: Vec<String>,
    pub emitted_artifact_ids: Vec<String>,
    pub discrepancy_summary_ids: Vec<String>,
}

/// Periodic or event-driven intraday broker-state comparison request.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IntradayReconciliationRequest {
    pub reconciliation_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub evaluated_at_utc: String,
    pub correlation_id: String,
    pub position_tolerance_contracts: i64,
    pub local_position_contracts: i64,
    pub broker_position_contracts: i64,
    pub local_working_order_ids: Vec<String>,
    pub broker_working_order_ids: Vec<String>,
    pub local_fill_ids: Vec<String>,
    pub broker_fill_ids: Vec<String>,
    pub local_trading_permission_state: String,
    pub broker_trading_permission_state: String,
    pub source_artifact_ids: Vec<String>,
}

/// Durable intraday mismatch artifact retained by the reconciliation module.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IntradayReconciliationArtifact {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub reconciliation_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub status: ReconciliationStatus,
    pub reason_code: String,
    pub blocking_new_entries: bool,
    pub required_action: IntradayControlAction,
    pub discrepancy_summaries: Vec<DiscrepancySummary>,
    pub manifest: ReconciliationManifest,
    pub explanation: String,
    pub evaluated_at_utc: String,
    pub correlation_id: String,
}

/// Authoritative broker statement set used for end-of-day reconciliation.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AuthoritativeStatementSet {
    pub statement_set_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub ledger_close_date: String,
    pub ingested_at_utc: String,
    pub fill_execution_ids: Vec<String>,
    pub position_contracts: i64,
    pub cash_movement_total_usd_cents: i64,
    pub commission_total_usd_cents: i64,
    pub fee_total_usd_cents: i64,
    pub realized_pnl_usd_cents: i64,
    pub unrealized_pnl_usd_cents: i64,
    pub initial_margin_requirement_usd_cents: i64,
    pub maintenance_margin_requirement_usd_cents: i64,
    pub source_artifact_ids: Vec<String>,
}

/// Runtime request to turn a session-close artifact into authoritative close truth.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DailyLedgerCloseRequest {
    pub ledger_close_id: String,
    pub session_close_artifact_id: String,
    pub statement_set: AuthoritativeStatementSet,
    pub runtime_unrealized_pnl_usd_cents: Option<i64>,
    pub reviewed_or_waived: bool,
    pub review_or_waiver_id: Option<String>,
    pub correlation_id: String,
    pub evaluated_at_utc: String,
}

/// Durable authoritative daily close retained after statement ingestion and comparison.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AuthoritativeLedgerCloseArtifact {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub ledger_close_id: String,
    pub session_close_artifact_id: String,
    pub authoritative_statement_set_id: String,
    pub account_id: String,
    pub symbol: String,
    pub session_id: String,
    pub ledger_close_date: String,
    pub status: ReconciliationStatus,
    pub reason_code: String,
    pub next_session_eligibility: NextSessionEligibility,
    pub discrepancy_summary_ids: Vec<String>,
    pub discrepancy_summaries: Vec<DiscrepancySummary>,
    pub restatement_event_ids: Vec<String>,
    pub as_booked_pnl_usd_cents: i64,
    pub as_reconciled_pnl_usd_cents: i64,
    pub positions_reconciled: bool,
    pub fills_reconciled: bool,
    pub cash_movements_reconciled: bool,
    pub commissions_reconciled: bool,
    pub fees_reconciled: bool,
    pub realized_pnl_reconciled: bool,
    pub unrealized_pnl_reconciled: bool,
    pub margin_reconciled: bool,
    pub reviewed_or_waived: bool,
    pub review_or_waiver_id: Option<String>,
    pub authoritative_unrealized_pnl_usd_cents: i64,
    pub runtime_unrealized_pnl_usd_cents: Option<i64>,
    pub manifest: ReconciliationManifest,
    pub explanation: String,
    pub evaluated_at_utc: String,
    pub correlation_id: String,
}

/// Reconciliation workflow failures.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ReconciliationError {
    InvalidTimestamp { field: &'static str, value: String },
    MissingRequiredField { field: &'static str },
    EmptySourceArtifactIds { field: &'static str },
    ReviewOrWaiverIdRequired,
}

/// Stateful reconciliation engine retaining the latest intraday and daily-close artifacts.
#[derive(Clone, Debug, Default)]
pub struct ReconciliationEngine {
    next_intraday_sequence: usize,
    next_daily_close_sequence: usize,
    next_manifest_sequence: usize,
    next_discrepancy_sequence: usize,
    latest_intraday_artifact: Option<IntradayReconciliationArtifact>,
    latest_daily_close_artifact: Option<AuthoritativeLedgerCloseArtifact>,
}

impl ReconciliationEngine {
    pub fn new() -> Self {
        Self {
            next_intraday_sequence: 1,
            next_daily_close_sequence: 1,
            next_manifest_sequence: 1,
            next_discrepancy_sequence: 1,
            latest_intraday_artifact: None,
            latest_daily_close_artifact: None,
        }
    }

    /// Returns the latest intraday artifact, if present.
    pub fn latest_intraday_artifact(&self) -> Option<&IntradayReconciliationArtifact> {
        self.latest_intraday_artifact.as_ref()
    }

    /// Returns the latest daily authoritative close, if present.
    pub fn latest_daily_close_artifact(&self) -> Option<&AuthoritativeLedgerCloseArtifact> {
        self.latest_daily_close_artifact.as_ref()
    }

    /// Returns the latest next-session eligibility, if present.
    pub fn latest_next_session_eligibility(&self) -> Option<NextSessionEligibility> {
        self.latest_daily_close_artifact
            .as_ref()
            .map(|artifact| artifact.next_session_eligibility)
    }

    /// Produces a durable intraday mismatch artifact from local-versus-broker runtime state.
    pub fn reconcile_intraday(
        &mut self,
        request: IntradayReconciliationRequest,
    ) -> Result<IntradayReconciliationArtifact, ReconciliationError> {
        validate_utc_timestamp("evaluated_at_utc", &request.evaluated_at_utc)?;
        ensure_non_empty("reconciliation_id", &request.reconciliation_id)?;
        ensure_non_empty("account_id", &request.account_id)?;
        ensure_non_empty("symbol", &request.symbol)?;
        ensure_non_empty("session_id", &request.session_id)?;
        ensure_non_empty("correlation_id", &request.correlation_id)?;
        ensure_non_empty(
            "local_trading_permission_state",
            &request.local_trading_permission_state,
        )?;
        ensure_non_empty(
            "broker_trading_permission_state",
            &request.broker_trading_permission_state,
        )?;
        if request.source_artifact_ids.is_empty() {
            return Err(ReconciliationError::EmptySourceArtifactIds {
                field: "source_artifact_ids",
            });
        }

        let mut discrepancy_summaries = Vec::new();
        let local_working_orders = unique_sorted(request.local_working_order_ids.clone());
        let broker_working_orders = unique_sorted(request.broker_working_order_ids.clone());
        let local_fill_ids = unique_sorted(request.local_fill_ids.clone());
        let broker_fill_ids = unique_sorted(request.broker_fill_ids.clone());
        let position_delta = request.broker_position_contracts - request.local_position_contracts;

        if position_delta.abs() > request.position_tolerance_contracts {
            discrepancy_summaries.push(
                self.new_discrepancy_summary(DiscrepancyDraft {
                    category: DiscrepancyCategory::PositionContracts,
                    local_value: request.local_position_contracts.to_string(),
                    authoritative_value: request.broker_position_contracts.to_string(),
                    delta: Some(position_delta),
                    above_tolerance: true,
                    provenance_artifact_ids: request.source_artifact_ids.clone(),
                    explanation:
                        "Local net position does not match the broker intraday position snapshot."
                            .to_string(),
                }),
            );
        }
        if local_working_orders != broker_working_orders {
            discrepancy_summaries.push(self.new_discrepancy_summary(DiscrepancyDraft {
                category: DiscrepancyCategory::WorkingOrders,
                local_value: local_working_orders.join(","),
                authoritative_value: broker_working_orders.join(","),
                delta: None,
                above_tolerance: true,
                provenance_artifact_ids: request.source_artifact_ids.clone(),
                explanation:
                    "Working-order identifiers differ between the local runtime and broker state."
                        .to_string(),
            }));
        }
        if local_fill_ids != broker_fill_ids {
            discrepancy_summaries.push(self.new_discrepancy_summary(DiscrepancyDraft {
                category: DiscrepancyCategory::FillExecutionIds,
                local_value: local_fill_ids.join(","),
                authoritative_value: broker_fill_ids.join(","),
                delta: None,
                above_tolerance: true,
                provenance_artifact_ids: request.source_artifact_ids.clone(),
                explanation:
                    "Fill or execution identifiers differ between the local runtime and broker state."
                        .to_string(),
            }));
        }
        if request.local_trading_permission_state != request.broker_trading_permission_state {
            discrepancy_summaries.push(self.new_discrepancy_summary(DiscrepancyDraft {
                category: DiscrepancyCategory::TradingPermissions,
                local_value: request.local_trading_permission_state.clone(),
                authoritative_value: request.broker_trading_permission_state.clone(),
                delta: None,
                above_tolerance: true,
                provenance_artifact_ids: request.source_artifact_ids.clone(),
                explanation:
                    "Trading permissions differ between the local runtime and the broker session."
                        .to_string(),
            }));
        }

        let (status, reason_code, required_action, explanation) = if discrepancy_summaries
            .is_empty()
        {
            (
                ReconciliationStatus::Pass,
                "INTRADAY_RECONCILIATION_CLEAN".to_string(),
                IntradayControlAction::None,
                "Intraday reconciliation matched broker state for position, working orders, fill ids, and trading permissions.".to_string(),
            )
        } else if discrepancy_summaries
            .iter()
            .any(|summary| summary.category == DiscrepancyCategory::TradingPermissions)
        {
            (
                ReconciliationStatus::ReviewRequired,
                "INTRADAY_TRADING_PERMISSION_MISMATCH".to_string(),
                IntradayControlAction::FlattenAndWithdraw,
                "Broker trading-permission state disagrees with the runtime, so new entries are blocked and operator intervention must govern continuation.".to_string(),
            )
        } else if discrepancy_summaries
            .iter()
            .any(|summary| summary.category == DiscrepancyCategory::PositionContracts)
        {
            (
                ReconciliationStatus::ReviewRequired,
                "INTRADAY_POSITION_MISMATCH_ABOVE_TOLERANCE".to_string(),
                IntradayControlAction::ExitOnly,
                "Net position drift exceeded tolerance, so the runtime must stop new entries until reconciliation is reviewed or resolved.".to_string(),
            )
        } else {
            (
                ReconciliationStatus::ReviewRequired,
                "INTRADAY_RECONCILIATION_RESTRICTED".to_string(),
                IntradayControlAction::Restrict,
                "Intraday reconciliation found broker-state differences and must block new entries until the discrepancy is resolved.".to_string(),
            )
        };

        let artifact_id = format!("intraday-reconciliation-{:04}", self.next_intraday_sequence);
        self.next_intraday_sequence += 1;
        let retained_artifact_id =
            format!("runtime_state/reconciliation/intraday/{artifact_id}.json");
        let discrepancy_summary_ids = discrepancy_summaries
            .iter()
            .map(|summary| summary.discrepancy_id.clone())
            .collect::<Vec<_>>();
        let manifest = self.new_manifest(
            &artifact_id,
            request.source_artifact_ids.clone(),
            vec![retained_artifact_id.clone()],
            discrepancy_summary_ids.clone(),
        );
        let artifact = IntradayReconciliationArtifact {
            artifact_id,
            retained_artifact_id,
            reconciliation_id: request.reconciliation_id,
            account_id: request.account_id,
            symbol: request.symbol,
            session_id: request.session_id,
            status,
            reason_code,
            blocking_new_entries: !discrepancy_summaries.is_empty(),
            required_action,
            discrepancy_summaries,
            manifest,
            explanation,
            evaluated_at_utc: request.evaluated_at_utc,
            correlation_id: request.correlation_id,
        };
        self.latest_intraday_artifact = Some(artifact.clone());
        Ok(artifact)
    }

    /// Produces an authoritative daily close from a prior session-close artifact and statement set.
    pub fn reconcile_daily_close(
        &mut self,
        request: DailyLedgerCloseRequest,
        session_close: &SessionCloseArtifact,
        scoped_events: &[LedgerEvent],
    ) -> Result<AuthoritativeLedgerCloseArtifact, ReconciliationError> {
        validate_utc_timestamp("evaluated_at_utc", &request.evaluated_at_utc)?;
        validate_utc_timestamp(
            "statement_set.ingested_at_utc",
            &request.statement_set.ingested_at_utc,
        )?;
        ensure_non_empty("ledger_close_id", &request.ledger_close_id)?;
        ensure_non_empty(
            "session_close_artifact_id",
            &request.session_close_artifact_id,
        )?;
        ensure_non_empty(
            "statement_set.statement_set_id",
            &request.statement_set.statement_set_id,
        )?;
        ensure_non_empty(
            "statement_set.account_id",
            &request.statement_set.account_id,
        )?;
        ensure_non_empty("statement_set.symbol", &request.statement_set.symbol)?;
        ensure_non_empty(
            "statement_set.session_id",
            &request.statement_set.session_id,
        )?;
        ensure_non_empty(
            "statement_set.ledger_close_date",
            &request.statement_set.ledger_close_date,
        )?;
        ensure_non_empty("correlation_id", &request.correlation_id)?;
        if request.statement_set.source_artifact_ids.is_empty() {
            return Err(ReconciliationError::EmptySourceArtifactIds {
                field: "statement_set.source_artifact_ids",
            });
        }
        if request.reviewed_or_waived && request.review_or_waiver_id.is_none() {
            return Err(ReconciliationError::ReviewOrWaiverIdRequired);
        }
        ensure_matching_scope(
            "account_id",
            &session_close.account_id,
            &request.statement_set.account_id,
        )?;
        ensure_matching_scope(
            "symbol",
            &session_close.symbol,
            &request.statement_set.symbol,
        )?;
        ensure_matching_scope(
            "session_id",
            &session_close.session_id,
            &request.statement_set.session_id,
        )?;

        let local_fill_ids = unique_sorted(
            scoped_events
                .iter()
                .filter(|event| event.event_class == LedgerEventClass::BookedFill)
                .filter_map(|event| event.source_callback_id.clone())
                .collect(),
        );
        let authoritative_fill_ids =
            unique_sorted(request.statement_set.fill_execution_ids.clone());
        let positions_reconciled = session_close.as_reconciled_totals.position_contracts
            == request.statement_set.position_contracts;
        let fills_reconciled = local_fill_ids == authoritative_fill_ids;
        let cash_movements_reconciled = session_close.as_reconciled_totals.cash_balance_usd_cents
            == request.statement_set.cash_movement_total_usd_cents;
        let commissions_reconciled = session_close
            .as_reconciled_totals
            .commission_total_usd_cents
            == request.statement_set.commission_total_usd_cents;
        let fees_reconciled = session_close.as_reconciled_totals.fee_total_usd_cents
            == request.statement_set.fee_total_usd_cents;
        let realized_pnl_reconciled = session_close.as_reconciled_totals.realized_pnl_usd_cents
            == request.statement_set.realized_pnl_usd_cents;
        let unrealized_pnl_reconciled = request.runtime_unrealized_pnl_usd_cents
            == Some(request.statement_set.unrealized_pnl_usd_cents);
        let margin_reconciled = session_close
            .broker_authoritative_snapshot
            .initial_margin_requirement_usd_cents
            == Some(request.statement_set.initial_margin_requirement_usd_cents)
            && session_close
                .broker_authoritative_snapshot
                .maintenance_margin_requirement_usd_cents
                == Some(
                    request
                        .statement_set
                        .maintenance_margin_requirement_usd_cents,
                );

        let mut discrepancy_summaries = Vec::new();
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            positions_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::PositionContracts,
                local_value: session_close
                    .as_reconciled_totals
                    .position_contracts
                    .to_string(),
                authoritative_value: request.statement_set.position_contracts.to_string(),
                delta: Some(
                    request.statement_set.position_contracts
                        - session_close.as_reconciled_totals.position_contracts,
                ),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative statement position must match reconciled runtime position."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            fills_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::FillExecutionIds,
                local_value: local_fill_ids.join(","),
                authoritative_value: authoritative_fill_ids.join(","),
                delta: None,
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative statement execution ids must match locally booked fills."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            cash_movements_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::CashMovements,
                local_value: session_close
                    .as_reconciled_totals
                    .cash_balance_usd_cents
                    .to_string(),
                authoritative_value: request
                    .statement_set
                    .cash_movement_total_usd_cents
                    .to_string(),
                delta: Some(
                    request.statement_set.cash_movement_total_usd_cents
                        - session_close.as_reconciled_totals.cash_balance_usd_cents,
                ),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative cash-movement totals must match the reconciled internal ledger."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            commissions_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::Commissions,
                local_value: session_close
                    .as_reconciled_totals
                    .commission_total_usd_cents
                    .to_string(),
                authoritative_value: request.statement_set.commission_total_usd_cents.to_string(),
                delta: Some(
                    request.statement_set.commission_total_usd_cents
                        - session_close
                            .as_reconciled_totals
                            .commission_total_usd_cents,
                ),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation: "Authoritative commissions must match the reconciled internal ledger."
                    .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            fees_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::Fees,
                local_value: session_close
                    .as_reconciled_totals
                    .fee_total_usd_cents
                    .to_string(),
                authoritative_value: request.statement_set.fee_total_usd_cents.to_string(),
                delta: Some(
                    request.statement_set.fee_total_usd_cents
                        - session_close.as_reconciled_totals.fee_total_usd_cents,
                ),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative exchange or clearing fees must match the reconciled internal ledger."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            realized_pnl_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::RealizedPnl,
                local_value: session_close
                    .as_reconciled_totals
                    .realized_pnl_usd_cents
                    .to_string(),
                authoritative_value: request.statement_set.realized_pnl_usd_cents.to_string(),
                delta: Some(
                    request.statement_set.realized_pnl_usd_cents
                        - session_close.as_reconciled_totals.realized_pnl_usd_cents,
                ),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative realized PnL must match the reconciled runtime ledger close."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            unrealized_pnl_reconciled,
            DiscrepancyDraft {
                category: DiscrepancyCategory::UnrealizedPnl,
                local_value: request.runtime_unrealized_pnl_usd_cents.map_or_else(
                    || "missing".to_string(),
                    |value| value.to_string(),
                ),
                authoritative_value: request.statement_set.unrealized_pnl_usd_cents.to_string(),
                delta: request
                    .runtime_unrealized_pnl_usd_cents
                    .map(|value| request.statement_set.unrealized_pnl_usd_cents - value),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative unrealized PnL must match the runtime mark-to-close value provided to reconciliation."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            session_close
                .broker_authoritative_snapshot
                .initial_margin_requirement_usd_cents
                == Some(request.statement_set.initial_margin_requirement_usd_cents),
            DiscrepancyDraft {
                category: DiscrepancyCategory::InitialMargin,
                local_value: session_close
                    .broker_authoritative_snapshot
                    .initial_margin_requirement_usd_cents
                    .map_or_else(|| "missing".to_string(), |value| value.to_string()),
                authoritative_value: request
                    .statement_set
                    .initial_margin_requirement_usd_cents
                    .to_string(),
                delta: session_close
                    .broker_authoritative_snapshot
                    .initial_margin_requirement_usd_cents
                    .map(|value| request.statement_set.initial_margin_requirement_usd_cents - value),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative initial margin requirement must match the runtime end-of-day margin snapshot."
                        .to_string(),
            },
        );
        add_metric_discrepancy(
            &mut discrepancy_summaries,
            self,
            session_close
                .broker_authoritative_snapshot
                .maintenance_margin_requirement_usd_cents
                == Some(
                    request
                        .statement_set
                        .maintenance_margin_requirement_usd_cents,
                ),
            DiscrepancyDraft {
                category: DiscrepancyCategory::MaintenanceMargin,
                local_value: session_close
                    .broker_authoritative_snapshot
                    .maintenance_margin_requirement_usd_cents
                    .map_or_else(|| "missing".to_string(), |value| value.to_string()),
                authoritative_value: request
                    .statement_set
                    .maintenance_margin_requirement_usd_cents
                    .to_string(),
                delta: session_close
                    .broker_authoritative_snapshot
                    .maintenance_margin_requirement_usd_cents
                    .map(|value| {
                        request
                            .statement_set
                            .maintenance_margin_requirement_usd_cents
                            - value
                    }),
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "Authoritative maintenance margin requirement must match the runtime end-of-day margin snapshot."
                        .to_string(),
            },
        );
        for discrepancy_id in &session_close.unresolved_discrepancy_ids {
            discrepancy_summaries.push(self.new_discrepancy_summary(DiscrepancyDraft {
                category: DiscrepancyCategory::UnresolvedDiscrepancy,
                local_value: discrepancy_id.clone(),
                authoritative_value: discrepancy_id.clone(),
                delta: None,
                above_tolerance: true,
                provenance_artifact_ids: request.statement_set.source_artifact_ids.clone(),
                explanation:
                    "An unresolved discrepancy remained open in the session-close artifact and must govern next-session eligibility.".to_string(),
            }));
        }

        let discrepancy_summary_ids = discrepancy_summaries
            .iter()
            .map(|summary| summary.discrepancy_id.clone())
            .collect::<Vec<_>>();
        let status = if session_close.status == SessionCloseStatus::Violation
            || !session_close.append_only_integrity.valid
        {
            ReconciliationStatus::Violation
        } else if discrepancy_summaries.is_empty() {
            ReconciliationStatus::Pass
        } else {
            ReconciliationStatus::ReviewRequired
        };
        let next_session_eligibility = if status == ReconciliationStatus::Pass {
            NextSessionEligibility::Eligible
        } else if request.reviewed_or_waived {
            NextSessionEligibility::ReviewRequired
        } else {
            NextSessionEligibility::Blocked
        };
        let reason_code = match (status, next_session_eligibility) {
            (ReconciliationStatus::Pass, NextSessionEligibility::Eligible) => {
                "AUTHORITATIVE_LEDGER_CLOSE_RECONCILED".to_string()
            }
            (_, NextSessionEligibility::ReviewRequired) => {
                "AUTHORITATIVE_LEDGER_CLOSE_WAIVER_APPLIED".to_string()
            }
            (ReconciliationStatus::Violation, _) => {
                "AUTHORITATIVE_LEDGER_CLOSE_SESSION_ARTIFACT_INVALID".to_string()
            }
            _ => "AUTHORITATIVE_LEDGER_CLOSE_BLOCKED".to_string(),
        };
        let explanation = match next_session_eligibility {
            NextSessionEligibility::Eligible => {
                "Authoritative statement ingestion reconciled the as-booked session close and left the next session eligible.".to_string()
            }
            NextSessionEligibility::ReviewRequired => {
                "Authoritative statement ingestion found differences, but a reviewed waiver keeps the next session in explicit operator review.".to_string()
            }
            NextSessionEligibility::Blocked => {
                "Authoritative statement ingestion found unresolved or unexplained differences, so the next session remains blocked until review, waiver, or repair.".to_string()
            }
        };

        let artifact_id = format!(
            "authoritative-ledger-close-{:04}",
            self.next_daily_close_sequence
        );
        self.next_daily_close_sequence += 1;
        let retained_artifact_id =
            format!("runtime_state/reconciliation/daily_close/{artifact_id}.json");
        let manifest = self.new_manifest(
            &artifact_id,
            unique_sorted(
                request
                    .statement_set
                    .source_artifact_ids
                    .iter()
                    .cloned()
                    .chain(std::iter::once(session_close.retained_artifact_id.clone()))
                    .collect(),
            ),
            vec![retained_artifact_id.clone()],
            discrepancy_summary_ids.clone(),
        );
        let as_booked_pnl_usd_cents = session_close.as_booked_totals.realized_pnl_usd_cents
            + request.runtime_unrealized_pnl_usd_cents.unwrap_or(0)
            - session_close.as_booked_totals.fee_total_usd_cents
            - session_close.as_booked_totals.commission_total_usd_cents;
        let as_reconciled_pnl_usd_cents = request.statement_set.realized_pnl_usd_cents
            + request.statement_set.unrealized_pnl_usd_cents
            - request.statement_set.fee_total_usd_cents
            - request.statement_set.commission_total_usd_cents;

        let artifact = AuthoritativeLedgerCloseArtifact {
            artifact_id,
            retained_artifact_id,
            ledger_close_id: request.ledger_close_id,
            session_close_artifact_id: request.session_close_artifact_id,
            authoritative_statement_set_id: request.statement_set.statement_set_id,
            account_id: request.statement_set.account_id,
            symbol: request.statement_set.symbol,
            session_id: request.statement_set.session_id,
            ledger_close_date: request.statement_set.ledger_close_date,
            status,
            reason_code,
            next_session_eligibility,
            discrepancy_summary_ids,
            discrepancy_summaries,
            restatement_event_ids: session_close.restatement_event_ids.clone(),
            as_booked_pnl_usd_cents,
            as_reconciled_pnl_usd_cents,
            positions_reconciled,
            fills_reconciled,
            cash_movements_reconciled,
            commissions_reconciled,
            fees_reconciled,
            realized_pnl_reconciled,
            unrealized_pnl_reconciled,
            margin_reconciled,
            reviewed_or_waived: request.reviewed_or_waived,
            review_or_waiver_id: request.review_or_waiver_id,
            authoritative_unrealized_pnl_usd_cents: request.statement_set.unrealized_pnl_usd_cents,
            runtime_unrealized_pnl_usd_cents: request.runtime_unrealized_pnl_usd_cents,
            manifest,
            explanation,
            evaluated_at_utc: request.evaluated_at_utc,
            correlation_id: request.correlation_id,
        };
        self.latest_daily_close_artifact = Some(artifact.clone());
        Ok(artifact)
    }

    fn new_manifest(
        &mut self,
        root_artifact_id: &str,
        input_artifact_ids: Vec<String>,
        emitted_artifact_ids: Vec<String>,
        discrepancy_summary_ids: Vec<String>,
    ) -> ReconciliationManifest {
        let manifest_id = format!("reconciliation-manifest-{:04}", self.next_manifest_sequence);
        self.next_manifest_sequence += 1;
        ReconciliationManifest {
            manifest_id,
            root_artifact_id: root_artifact_id.to_string(),
            input_artifact_ids: unique_sorted(input_artifact_ids),
            emitted_artifact_ids: unique_sorted(emitted_artifact_ids),
            discrepancy_summary_ids,
        }
    }

    fn new_discrepancy_summary(&mut self, draft: DiscrepancyDraft) -> DiscrepancySummary {
        let discrepancy_id = format!(
            "reconciliation-discrepancy-{:04}",
            self.next_discrepancy_sequence
        );
        self.next_discrepancy_sequence += 1;
        DiscrepancySummary {
            discrepancy_id,
            category: draft.category,
            local_value: draft.local_value,
            authoritative_value: draft.authoritative_value,
            delta: draft.delta,
            above_tolerance: draft.above_tolerance,
            provenance_artifact_ids: unique_sorted(draft.provenance_artifact_ids),
            explanation: draft.explanation,
        }
    }
}

fn add_metric_discrepancy(
    discrepancy_summaries: &mut Vec<DiscrepancySummary>,
    engine: &mut ReconciliationEngine,
    metric_reconciled: bool,
    draft: DiscrepancyDraft,
) {
    if !metric_reconciled {
        discrepancy_summaries.push(engine.new_discrepancy_summary(draft));
    }
}

fn unique_sorted(values: Vec<String>) -> Vec<String> {
    values
        .into_iter()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn ensure_non_empty(field: &'static str, value: &str) -> Result<(), ReconciliationError> {
    if value.is_empty() {
        Err(ReconciliationError::MissingRequiredField { field })
    } else {
        Ok(())
    }
}

fn ensure_matching_scope(
    field: &'static str,
    expected: &str,
    actual: &str,
) -> Result<(), ReconciliationError> {
    if expected == actual {
        Ok(())
    } else {
        Err(ReconciliationError::MissingRequiredField { field })
    }
}

fn validate_utc_timestamp(field: &'static str, value: &str) -> Result<(), ReconciliationError> {
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
        Err(ReconciliationError::InvalidTimestamp {
            field,
            value: value.to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use crate::{
        AppendOnlyIntegrityReport, BrokerAuthoritativeSnapshot, LedgerTotals, SessionCloseArtifact,
        SessionCloseManifest, SessionCloseStatus,
    };

    use super::{
        AuthoritativeStatementSet, DailyLedgerCloseRequest, DiscrepancyCategory,
        IntradayControlAction, IntradayReconciliationRequest, NextSessionEligibility,
        ReconciliationEngine, ReconciliationStatus,
    };

    fn sample_session_close() -> SessionCloseArtifact {
        SessionCloseArtifact {
            artifact_id: "ledger-close-0001".to_string(),
            retained_artifact_id: "runtime_state/ledger/closes/ledger-close-0001.json".to_string(),
            close_id: "close-1".to_string(),
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            compiled_schedule_artifact_id:
                "runtime_state/schedules/compiled_schedule_gold_reset_v1.json".to_string(),
            status: SessionCloseStatus::Pass,
            reason_code: "SESSION_CLOSE_BOOKED_ARTIFACT_READY".to_string(),
            append_only_integrity: AppendOnlyIntegrityReport {
                valid: true,
                reason_code: "LEDGER_APPEND_ONLY_VALID".to_string(),
                explanation: "Ledger sequence is append-only and uniquely identified.".to_string(),
                duplicate_event_id: None,
                violating_sequence_id: None,
            },
            event_classes_present: vec![
                "booked_fill".to_string(),
                "booked_commission".to_string(),
                "reconciliation_adjustment".to_string(),
            ],
            trace_event_ids: vec![
                "ledger-event-000001".to_string(),
                "ledger-event-000002".to_string(),
                "ledger-event-000003".to_string(),
            ],
            as_booked_totals: LedgerTotals {
                position_contracts: 1,
                cash_balance_usd_cents: -25_350,
                realized_pnl_usd_cents: 12_500,
                fee_total_usd_cents: 25,
                commission_total_usd_cents: 55,
            },
            as_reconciled_totals: LedgerTotals {
                position_contracts: 1,
                cash_balance_usd_cents: -25_360,
                realized_pnl_usd_cents: 12_500,
                fee_total_usd_cents: 25,
                commission_total_usd_cents: 45,
            },
            broker_authoritative_snapshot: BrokerAuthoritativeSnapshot {
                position_contracts: Some(1),
                initial_margin_requirement_usd_cents: Some(125_000),
                maintenance_margin_requirement_usd_cents: Some(95_000),
                position_event_id: Some("ledger-event-000004".to_string()),
                margin_event_id: Some("ledger-event-000005".to_string()),
                source_timestamp_utc: Some("2026-03-18T22:10:01Z".to_string()),
            },
            differences: Vec::new(),
            unresolved_discrepancy_ids: Vec::new(),
            restatement_event_ids: vec!["ledger-event-000003".to_string()],
            manifest: SessionCloseManifest {
                manifest_id: "ledger-manifest-0001".to_string(),
                close_id: "close-1".to_string(),
                trace_event_ids: vec![
                    "ledger-event-000001".to_string(),
                    "ledger-event-000002".to_string(),
                    "ledger-event-000003".to_string(),
                ],
                event_artifact_ids: vec![
                    "runtime_state/ledger/events/ledger-event-000001.json".to_string(),
                    "runtime_state/ledger/events/ledger-event-000002.json".to_string(),
                    "runtime_state/ledger/events/ledger-event-000003.json".to_string(),
                ],
                source_callback_ids: vec!["fill-1".to_string()],
            },
            explanation: "Session close ready".to_string(),
            close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
        }
    }

    fn sample_statement_set() -> AuthoritativeStatementSet {
        AuthoritativeStatementSet {
            statement_set_id: "statement-set-2026-03-18".to_string(),
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            ledger_close_date: "2026-03-18".to_string(),
            ingested_at_utc: "2026-03-18T22:20:00Z".to_string(),
            fill_execution_ids: vec!["fill-1".to_string()],
            position_contracts: 1,
            cash_movement_total_usd_cents: -25_360,
            commission_total_usd_cents: 45,
            fee_total_usd_cents: 25,
            realized_pnl_usd_cents: 12_500,
            unrealized_pnl_usd_cents: 8_750,
            initial_margin_requirement_usd_cents: 125_000,
            maintenance_margin_requirement_usd_cents: 95_000,
            source_artifact_ids: vec![
                "evidence/broker/statement-set-2026-03-18.csv".to_string(),
                "evidence/broker/statement-set-2026-03-18.sha256".to_string(),
            ],
        }
    }

    fn sample_fill_event() -> crate::LedgerEvent {
        crate::LedgerEvent {
            sequence_id: 1,
            event_id: "ledger-event-000001".to_string(),
            event_class: crate::LedgerEventClass::BookedFill,
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            occurred_at_utc: "2026-03-18T13:05:00Z".to_string(),
            description: "Booked fill".to_string(),
            correlation_id: "fill-corr-1".to_string(),
            order_intent_id: Some("paper-gold-1:77:leg-a:buy:entry".to_string()),
            broker_order_id: Some("broker-order-1".to_string()),
            source_callback_id: Some("fill-1".to_string()),
            reference_event_id: None,
            discrepancy_id: None,
            position_delta_contracts: 1,
            cash_delta_usd_cents: -25_350,
            realized_pnl_delta_usd_cents: 0,
            fee_delta_usd_cents: 0,
            commission_delta_usd_cents: 0,
            authoritative_position_contracts: None,
            authoritative_initial_margin_requirement_usd_cents: None,
            authoritative_maintenance_margin_requirement_usd_cents: None,
            source_artifact_ids: vec!["artifact-0001".to_string()],
        }
    }

    #[test]
    fn intraday_reconciliation_blocks_new_entries_on_runtime_drift() {
        let mut engine = ReconciliationEngine::new();
        let artifact = engine
            .reconcile_intraday(IntradayReconciliationRequest {
                reconciliation_id: "intraday-1".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                evaluated_at_utc: "2026-03-18T20:00:00Z".to_string(),
                correlation_id: "intraday-corr-1".to_string(),
                position_tolerance_contracts: 0,
                local_position_contracts: 1,
                broker_position_contracts: 2,
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

        assert_eq!(ReconciliationStatus::ReviewRequired, artifact.status);
        assert_eq!(IntradayControlAction::ExitOnly, artifact.required_action);
        assert!(artifact.blocking_new_entries);
        assert!(
            artifact
                .discrepancy_summaries
                .iter()
                .any(|summary| summary.category == DiscrepancyCategory::PositionContracts)
        );
        assert!(
            artifact
                .discrepancy_summaries
                .iter()
                .any(|summary| summary.category == DiscrepancyCategory::WorkingOrders)
        );
    }

    #[test]
    fn authoritative_daily_close_blocks_next_session_on_statement_mismatch() {
        let mut engine = ReconciliationEngine::new();
        let mut statement = sample_statement_set();
        statement.commission_total_usd_cents = 60;

        let artifact = engine
            .reconcile_daily_close(
                DailyLedgerCloseRequest {
                    ledger_close_id: "daily-close-1".to_string(),
                    session_close_artifact_id: "ledger-close-0001".to_string(),
                    statement_set: statement,
                    runtime_unrealized_pnl_usd_cents: Some(8_750),
                    reviewed_or_waived: false,
                    review_or_waiver_id: None,
                    correlation_id: "daily-corr-1".to_string(),
                    evaluated_at_utc: "2026-03-18T22:25:00Z".to_string(),
                },
                &sample_session_close(),
                &[sample_fill_event()],
            )
            .expect("daily close should build");

        assert_eq!(ReconciliationStatus::ReviewRequired, artifact.status);
        assert_eq!(
            NextSessionEligibility::Blocked,
            artifact.next_session_eligibility
        );
        assert!(!artifact.commissions_reconciled);
        assert!(
            artifact
                .discrepancy_summaries
                .iter()
                .any(|summary| summary.category == DiscrepancyCategory::Commissions)
        );
    }

    #[test]
    fn reviewed_waiver_downgrades_block_to_review_required() {
        let mut engine = ReconciliationEngine::new();
        let mut statement = sample_statement_set();
        statement.fill_execution_ids = vec!["fill-1".to_string(), "fill-2".to_string()];

        let artifact = engine
            .reconcile_daily_close(
                DailyLedgerCloseRequest {
                    ledger_close_id: "daily-close-2".to_string(),
                    session_close_artifact_id: "ledger-close-0001".to_string(),
                    statement_set: statement,
                    runtime_unrealized_pnl_usd_cents: Some(8_750),
                    reviewed_or_waived: true,
                    review_or_waiver_id: Some("waiver-77".to_string()),
                    correlation_id: "daily-corr-2".to_string(),
                    evaluated_at_utc: "2026-03-18T22:25:00Z".to_string(),
                },
                &sample_session_close(),
                &[sample_fill_event()],
            )
            .expect("daily close should build");

        assert_eq!(
            NextSessionEligibility::ReviewRequired,
            artifact.next_session_eligibility
        );
        assert_eq!(
            "waiver-77",
            artifact.review_or_waiver_id.as_deref().unwrap_or("")
        );
        assert!(!artifact.fills_reconciled);
    }
}
