//! Runtime risk and trading-eligibility engine for the execution lane.
//!
//! This module is intentionally self-contained so the runtime risk contract can
//! be implemented and exercised without coupling to unrelated in-flight `opsd`
//! runtime work.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// Operator-facing risk action emitted by the runtime.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RiskAction {
    Allow,
    Restrict,
    ExitOnly,
    Flatten,
    Halt,
}

impl RiskAction {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Allow => "allow",
            Self::Restrict => "restrict",
            Self::ExitOnly => "exit_only",
            Self::Flatten => "flatten",
            Self::Halt => "halt",
        }
    }
}

/// Runtime trading-eligibility state owned by the risk lane.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EligibilityStatus {
    Eligible,
    Restricted,
    ExitOnly,
    Flatten,
    Halted,
    Invalid,
}

impl EligibilityStatus {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Eligible => "eligible",
            Self::Restricted => "restricted",
            Self::ExitOnly => "exit_only",
            Self::Flatten => "flatten",
            Self::Halted => "halted",
            Self::Invalid => "invalid",
        }
    }
}

/// Entry-mode restriction exposed to the strategy runner.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EntryMode {
    Normal,
    PassiveOnly,
    NoNewEntries,
    ExitOnly,
    ForcedFlatten,
}

impl EntryMode {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Normal => "normal",
            Self::PassiveOnly => "passive_only",
            Self::NoNewEntries => "no_new_entries",
            Self::ExitOnly => "exit_only",
            Self::ForcedFlatten => "forced_flatten",
        }
    }
}

/// Operating-envelope actions inherited by the runtime risk lane.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OperatingEnvelopeAction {
    Maintain,
    SizeReduction,
    PassiveEntrySuppression,
    NoNewOvernightCarry,
    LowerMaxTrades,
    EntrySuppression,
    ExitOnly,
    ForcedFlatten,
}

impl OperatingEnvelopeAction {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Maintain => "maintain",
            Self::SizeReduction => "size_reduction",
            Self::PassiveEntrySuppression => "passive_entry_suppression",
            Self::NoNewOvernightCarry => "no_new_overnight_carry",
            Self::LowerMaxTrades => "lower_max_trades",
            Self::EntrySuppression => "entry_suppression",
            Self::ExitOnly => "exit_only",
            Self::ForcedFlatten => "forced_flatten",
        }
    }
}

/// Baseline runtime thresholds inherited from the approved policy plane.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuntimeRiskLimits {
    pub max_position_contracts: i64,
    pub max_concurrent_order_intents: usize,
    pub degraded_data_stale_quote_bps: u32,
    pub max_behavior_drift_bps: u32,
    pub max_fill_slippage_drift_bps: u32,
    pub severe_behavior_drift_bps: u32,
    pub severe_fill_slippage_drift_bps: u32,
    pub max_data_quality_drift_bps: u32,
    pub severe_data_quality_drift_bps: u32,
    pub min_operating_envelope_fit_bps: u32,
    pub hard_stop_operating_envelope_fit_bps: u32,
    pub daily_loss_lockout_usd_cents: i64,
    pub max_drawdown_usd_cents: i64,
    pub max_initial_margin_requirement_usd_cents: i64,
    pub max_maintenance_margin_requirement_usd_cents: i64,
    pub warmup_min_history_bars: usize,
    pub warmup_min_history_minutes: usize,
    pub warmup_requires_state_seed: bool,
    pub overnight_only_with_strict_posture: bool,
    pub required_overnight_posture: String,
}

/// Exposure and PnL state that the risk lane consumes from authoritative surfaces.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuntimeExposureSnapshot {
    pub current_position_contracts: i64,
    pub projected_position_contracts: i64,
    pub pending_order_intent_count: usize,
    pub realized_loss_usd_cents: i64,
    pub drawdown_usd_cents: i64,
    pub initial_margin_requirement_usd_cents: i64,
    pub maintenance_margin_requirement_usd_cents: i64,
}

/// Market-data health inputs inherited from the live-bar builder lane.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MarketDataHealthSnapshot {
    pub market_data_fresh: bool,
    pub stale_quote_rate_bps: u32,
    pub parity_healthy: bool,
}

/// Warm-up state needed before the first live trade becomes eligible.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct WarmupSnapshot {
    pub history_bars_observed: usize,
    pub history_minutes_observed: usize,
    pub state_seed_loaded: bool,
}

/// Strategy-health drift inputs consumed by the runtime risk lane.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StrategyHealthSnapshot {
    pub behavior_drift_bps: u32,
    pub fill_slippage_drift_bps: u32,
    pub data_quality_drift_bps: u32,
    pub operating_envelope_fit_bps: u32,
    pub recalibration_required: bool,
    pub reference_window_id: String,
    pub reason_code: String,
}

/// Session-conditioned envelope overlay consumed by the runtime risk lane.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OperatingEnvelopeSnapshot {
    pub session_class: String,
    pub reason_code: String,
    pub actions: Vec<OperatingEnvelopeAction>,
    pub size_multiplier_bps: u32,
    pub max_trade_count_multiplier_bps: u32,
    pub required_operating_posture: String,
    pub overnight_carry_allowed: bool,
}

/// Full request evaluated by the runtime risk engine.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuntimeRiskRequest {
    pub request_id: String,
    pub symbol: String,
    pub session_id: String,
    pub session_tradeable: bool,
    pub delivery_window_active: bool,
    pub operating_posture: String,
    pub proposed_order_increases_risk: bool,
    pub overnight_requested: bool,
    pub overnight_approval_granted: bool,
    pub limits: RuntimeRiskLimits,
    pub exposure: RuntimeExposureSnapshot,
    pub market_data: MarketDataHealthSnapshot,
    pub warmup: WarmupSnapshot,
    pub strategy_health: StrategyHealthSnapshot,
    pub envelope: OperatingEnvelopeSnapshot,
}

/// Per-control decision retained in the runtime eligibility artifact.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RiskControlDecision {
    pub control_id: String,
    pub control_name: String,
    pub passed: bool,
    pub action: RiskAction,
    pub entry_mode: EntryMode,
    pub reason_code: Option<String>,
    pub diagnostic: String,
    pub context: BTreeMap<String, String>,
}

/// Operator-facing runtime risk report.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuntimeRiskReport {
    pub request_id: String,
    pub status: EligibilityStatus,
    pub action: RiskAction,
    pub entry_mode: EntryMode,
    pub reason_code: String,
    pub retained_artifact_id: String,
    pub trading_eligible: bool,
    pub allow_new_risk: bool,
    pub require_flatten: bool,
    pub effective_max_position_contracts: i64,
    pub effective_max_concurrent_order_intents: usize,
    pub effective_size_multiplier_bps: u32,
    pub effective_max_trade_count_multiplier_bps: u32,
    pub triggered_control_ids: Vec<String>,
    pub triggered_reason_codes: Vec<String>,
    pub decisions: Vec<RiskControlDecision>,
    pub explanation: String,
}

fn action_severity(action: RiskAction) -> u8 {
    match action {
        RiskAction::Allow => 0,
        RiskAction::Restrict => 1,
        RiskAction::ExitOnly => 2,
        RiskAction::Flatten => 3,
        RiskAction::Halt => 4,
    }
}

fn entry_mode_severity(mode: EntryMode) -> u8 {
    match mode {
        EntryMode::Normal => 0,
        EntryMode::PassiveOnly => 1,
        EntryMode::NoNewEntries => 2,
        EntryMode::ExitOnly => 3,
        EntryMode::ForcedFlatten => 4,
    }
}

fn scaled_contract_limit(base: i64, multiplier_bps: u32) -> i64 {
    let scaled = (base.saturating_mul(i64::from(multiplier_bps)) + 9_999) / 10_000;
    scaled.max(1)
}

fn scaled_count_limit(base: usize, multiplier_bps: u32) -> usize {
    let scaled = (base.saturating_mul(multiplier_bps as usize) + 9_999) / 10_000;
    scaled.max(1)
}

fn format_actions(actions: &[OperatingEnvelopeAction]) -> String {
    actions
        .iter()
        .map(|action| action.as_str())
        .collect::<Vec<_>>()
        .join(",")
}

fn format_context(context: &BTreeMap<String, String>) -> String {
    context
        .iter()
        .map(|(key, value)| format!("{key}={value}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn pass_control(
    control_id: &str,
    control_name: &str,
    diagnostic: &str,
    context: BTreeMap<String, String>,
) -> RiskControlDecision {
    RiskControlDecision {
        control_id: control_id.to_string(),
        control_name: control_name.to_string(),
        passed: true,
        action: RiskAction::Allow,
        entry_mode: EntryMode::Normal,
        reason_code: None,
        diagnostic: diagnostic.to_string(),
        context,
    }
}

fn fail_control(
    control_id: &str,
    control_name: &str,
    action: RiskAction,
    entry_mode: EntryMode,
    reason_code: &str,
    diagnostic: &str,
    context: BTreeMap<String, String>,
) -> RiskControlDecision {
    RiskControlDecision {
        control_id: control_id.to_string(),
        control_name: control_name.to_string(),
        passed: false,
        action,
        entry_mode,
        reason_code: Some(reason_code.to_string()),
        diagnostic: diagnostic.to_string(),
        context,
    }
}

fn invalid_report(request: &RuntimeRiskRequest, issues: Vec<&str>) -> RuntimeRiskReport {
    RuntimeRiskReport {
        request_id: request.request_id.clone(),
        status: EligibilityStatus::Invalid,
        action: RiskAction::Halt,
        entry_mode: EntryMode::NoNewEntries,
        reason_code: "RUNTIME_RISK_INVALID".to_string(),
        retained_artifact_id: format!("runtime_state/risk/{}", request.request_id),
        trading_eligible: false,
        allow_new_risk: false,
        require_flatten: false,
        effective_max_position_contracts: 0,
        effective_max_concurrent_order_intents: 0,
        effective_size_multiplier_bps: 0,
        effective_max_trade_count_multiplier_bps: 0,
        triggered_control_ids: Vec::new(),
        triggered_reason_codes: Vec::new(),
        decisions: Vec::new(),
        explanation: format!(
            "The runtime risk request was invalid because these fields or thresholds were not usable: {}.",
            issues.join(", ")
        ),
    }
}

fn render_request(request: &RuntimeRiskRequest) -> String {
    [
        format!("request_id={}", request.request_id),
        format!("symbol={}", request.symbol),
        format!("session_id={}", request.session_id),
        format!("session_tradeable={}", request.session_tradeable),
        format!("delivery_window_active={}", request.delivery_window_active),
        format!("operating_posture={}", request.operating_posture),
        format!(
            "proposed_order_increases_risk={}",
            request.proposed_order_increases_risk
        ),
        format!("overnight_requested={}", request.overnight_requested),
        format!(
            "overnight_approval_granted={}",
            request.overnight_approval_granted
        ),
        format!(
            "max_position_contracts={}",
            request.limits.max_position_contracts
        ),
        format!(
            "max_concurrent_order_intents={}",
            request.limits.max_concurrent_order_intents
        ),
        format!(
            "degraded_data_stale_quote_bps={}",
            request.limits.degraded_data_stale_quote_bps
        ),
        format!(
            "max_behavior_drift_bps={}",
            request.limits.max_behavior_drift_bps
        ),
        format!(
            "max_fill_slippage_drift_bps={}",
            request.limits.max_fill_slippage_drift_bps
        ),
        format!(
            "severe_behavior_drift_bps={}",
            request.limits.severe_behavior_drift_bps
        ),
        format!(
            "severe_fill_slippage_drift_bps={}",
            request.limits.severe_fill_slippage_drift_bps
        ),
        format!(
            "max_data_quality_drift_bps={}",
            request.limits.max_data_quality_drift_bps
        ),
        format!(
            "severe_data_quality_drift_bps={}",
            request.limits.severe_data_quality_drift_bps
        ),
        format!(
            "min_operating_envelope_fit_bps={}",
            request.limits.min_operating_envelope_fit_bps
        ),
        format!(
            "hard_stop_operating_envelope_fit_bps={}",
            request.limits.hard_stop_operating_envelope_fit_bps
        ),
        format!(
            "daily_loss_lockout_usd_cents={}",
            request.limits.daily_loss_lockout_usd_cents
        ),
        format!(
            "max_drawdown_usd_cents={}",
            request.limits.max_drawdown_usd_cents
        ),
        format!(
            "max_initial_margin_requirement_usd_cents={}",
            request.limits.max_initial_margin_requirement_usd_cents
        ),
        format!(
            "max_maintenance_margin_requirement_usd_cents={}",
            request.limits.max_maintenance_margin_requirement_usd_cents
        ),
        format!(
            "warmup_min_history_bars={}",
            request.limits.warmup_min_history_bars
        ),
        format!(
            "warmup_min_history_minutes={}",
            request.limits.warmup_min_history_minutes
        ),
        format!(
            "warmup_requires_state_seed={}",
            request.limits.warmup_requires_state_seed
        ),
        format!(
            "overnight_only_with_strict_posture={}",
            request.limits.overnight_only_with_strict_posture
        ),
        format!(
            "required_overnight_posture={}",
            request.limits.required_overnight_posture
        ),
        format!(
            "current_position_contracts={}",
            request.exposure.current_position_contracts
        ),
        format!(
            "projected_position_contracts={}",
            request.exposure.projected_position_contracts
        ),
        format!(
            "pending_order_intent_count={}",
            request.exposure.pending_order_intent_count
        ),
        format!(
            "realized_loss_usd_cents={}",
            request.exposure.realized_loss_usd_cents
        ),
        format!("drawdown_usd_cents={}", request.exposure.drawdown_usd_cents),
        format!(
            "initial_margin_requirement_usd_cents={}",
            request.exposure.initial_margin_requirement_usd_cents
        ),
        format!(
            "maintenance_margin_requirement_usd_cents={}",
            request.exposure.maintenance_margin_requirement_usd_cents
        ),
        format!(
            "market_data_fresh={}",
            request.market_data.market_data_fresh
        ),
        format!(
            "stale_quote_rate_bps={}",
            request.market_data.stale_quote_rate_bps
        ),
        format!("parity_healthy={}", request.market_data.parity_healthy),
        format!(
            "history_bars_observed={}",
            request.warmup.history_bars_observed
        ),
        format!(
            "history_minutes_observed={}",
            request.warmup.history_minutes_observed
        ),
        format!("state_seed_loaded={}", request.warmup.state_seed_loaded),
        format!(
            "behavior_drift_bps={}",
            request.strategy_health.behavior_drift_bps
        ),
        format!(
            "fill_slippage_drift_bps={}",
            request.strategy_health.fill_slippage_drift_bps
        ),
        format!(
            "data_quality_drift_bps={}",
            request.strategy_health.data_quality_drift_bps
        ),
        format!(
            "operating_envelope_fit_bps={}",
            request.strategy_health.operating_envelope_fit_bps
        ),
        format!(
            "recalibration_required={}",
            request.strategy_health.recalibration_required
        ),
        format!(
            "strategy_health_reference_window_id={}",
            request.strategy_health.reference_window_id
        ),
        format!(
            "strategy_health_reason_code={}",
            request.strategy_health.reason_code
        ),
        format!("session_class={}", request.envelope.session_class),
        format!("envelope_reason_code={}", request.envelope.reason_code),
        format!(
            "envelope_actions={}",
            format_actions(&request.envelope.actions)
        ),
        format!(
            "size_multiplier_bps={}",
            request.envelope.size_multiplier_bps
        ),
        format!(
            "max_trade_count_multiplier_bps={}",
            request.envelope.max_trade_count_multiplier_bps
        ),
        format!(
            "required_operating_posture={}",
            request.envelope.required_operating_posture
        ),
        format!(
            "envelope_overnight_carry_allowed={}",
            request.envelope.overnight_carry_allowed
        ),
    ]
    .join("\n")
}

fn render_report(report: &RuntimeRiskReport) -> String {
    let mut lines = vec![
        format!("request_id={}", report.request_id),
        format!("status={}", report.status.as_str()),
        format!("action={}", report.action.as_str()),
        format!("entry_mode={}", report.entry_mode.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("retained_artifact_id={}", report.retained_artifact_id),
        format!("trading_eligible={}", report.trading_eligible),
        format!("allow_new_risk={}", report.allow_new_risk),
        format!("require_flatten={}", report.require_flatten),
        format!(
            "effective_max_position_contracts={}",
            report.effective_max_position_contracts
        ),
        format!(
            "effective_max_concurrent_order_intents={}",
            report.effective_max_concurrent_order_intents
        ),
        format!(
            "effective_size_multiplier_bps={}",
            report.effective_size_multiplier_bps
        ),
        format!(
            "effective_max_trade_count_multiplier_bps={}",
            report.effective_max_trade_count_multiplier_bps
        ),
        format!(
            "triggered_control_ids={}",
            report.triggered_control_ids.join(",")
        ),
        format!(
            "triggered_reason_codes={}",
            report.triggered_reason_codes.join(",")
        ),
        format!("explanation={}", report.explanation),
    ];

    for (index, decision) in report.decisions.iter().enumerate() {
        lines.push(format!(
            "decision[{index}].control_id={}",
            decision.control_id
        ));
        lines.push(format!("decision[{index}].passed={}", decision.passed));
        lines.push(format!(
            "decision[{index}].action={}",
            decision.action.as_str()
        ));
        lines.push(format!(
            "decision[{index}].entry_mode={}",
            decision.entry_mode.as_str()
        ));
        lines.push(format!(
            "decision[{index}].reason_code={}",
            decision.reason_code.as_deref().unwrap_or("")
        ));
        lines.push(format!(
            "decision[{index}].diagnostic={}",
            decision.diagnostic
        ));
        lines.push(format!(
            "decision[{index}].context={}",
            format_context(&decision.context)
        ));
    }

    lines.join("\n")
}

fn write_report_artifacts(
    root: &Path,
    request: &RuntimeRiskRequest,
    report: &RuntimeRiskReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("runtime_risk_request.txt"),
        render_request(request),
    )?;
    fs::write(root.join("runtime_risk_report.txt"), render_report(report))?;
    Ok(())
}

fn dominant_action(decisions: &[RiskControlDecision]) -> RiskAction {
    decisions
        .iter()
        .filter(|decision| !decision.passed)
        .map(|decision| decision.action)
        .max_by_key(|action| action_severity(*action))
        .unwrap_or(RiskAction::Allow)
}

fn dominant_entry_mode(decisions: &[RiskControlDecision], action: RiskAction) -> EntryMode {
    let strongest = decisions
        .iter()
        .filter(|decision| !decision.passed)
        .map(|decision| decision.entry_mode)
        .max_by_key(|mode| entry_mode_severity(*mode))
        .unwrap_or(EntryMode::Normal);

    match action {
        RiskAction::Flatten => EntryMode::ForcedFlatten,
        RiskAction::ExitOnly => EntryMode::ExitOnly,
        RiskAction::Halt => EntryMode::NoNewEntries,
        RiskAction::Restrict => strongest,
        RiskAction::Allow => EntryMode::Normal,
    }
}

fn envelope_control(
    request: &RuntimeRiskRequest,
    effective_max_position_contracts: i64,
    effective_max_concurrent_order_intents: usize,
) -> RiskControlDecision {
    let actions = &request.envelope.actions;
    let posture_mismatch = request.envelope.required_operating_posture != request.operating_posture;
    let has_action = |needle: OperatingEnvelopeAction| actions.contains(&needle);
    let mut context = BTreeMap::from([
        (
            "session_class".to_string(),
            request.envelope.session_class.clone(),
        ),
        (
            "envelope_reason_code".to_string(),
            request.envelope.reason_code.clone(),
        ),
        ("actions".to_string(), format_actions(actions)),
        (
            "required_operating_posture".to_string(),
            request.envelope.required_operating_posture.clone(),
        ),
        (
            "current_operating_posture".to_string(),
            request.operating_posture.clone(),
        ),
        (
            "effective_max_position_contracts".to_string(),
            effective_max_position_contracts.to_string(),
        ),
        (
            "effective_max_concurrent_order_intents".to_string(),
            effective_max_concurrent_order_intents.to_string(),
        ),
        (
            "overnight_carry_allowed".to_string(),
            request.envelope.overnight_carry_allowed.to_string(),
        ),
    ]);

    if has_action(OperatingEnvelopeAction::ForcedFlatten) {
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::Flatten,
            EntryMode::ForcedFlatten,
            "OPERATING_ENVELOPE_FORCED_FLATTEN",
            "The session-conditioned operating envelope requires immediate flattening.",
            context,
        );
    }
    if has_action(OperatingEnvelopeAction::ExitOnly) {
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::ExitOnly,
            EntryMode::ExitOnly,
            "OPERATING_ENVELOPE_EXIT_ONLY",
            "The session-conditioned operating envelope limited the runtime to exit-only behavior.",
            context,
        );
    }
    if has_action(OperatingEnvelopeAction::NoNewOvernightCarry) && request.overnight_requested {
        let (action, entry_mode) = if request.exposure.current_position_contracts != 0 {
            (RiskAction::ExitOnly, EntryMode::ExitOnly)
        } else {
            (RiskAction::Restrict, EntryMode::NoNewEntries)
        };
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            action,
            entry_mode,
            "OPERATING_ENVELOPE_NO_NEW_OVERNIGHT_CARRY",
            "The session-conditioned operating envelope forbids new overnight carry in this state.",
            context,
        );
    }
    if has_action(OperatingEnvelopeAction::EntrySuppression) {
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "OPERATING_ENVELOPE_ENTRY_SUPPRESSION",
            "The session-conditioned operating envelope suppressed new entries.",
            context,
        );
    }
    if has_action(OperatingEnvelopeAction::PassiveEntrySuppression) {
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::Restrict,
            EntryMode::PassiveOnly,
            "OPERATING_ENVELOPE_PASSIVE_ONLY",
            "The session-conditioned operating envelope allows only passive entry behavior.",
            context,
        );
    }
    if posture_mismatch {
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "OPERATING_ENVELOPE_POSTURE_MISMATCH",
            "The runtime posture does not match the required session-conditioned operating posture.",
            context,
        );
    }
    if has_action(OperatingEnvelopeAction::SizeReduction)
        || has_action(OperatingEnvelopeAction::LowerMaxTrades)
    {
        context.insert(
            "size_multiplier_bps".to_string(),
            request.envelope.size_multiplier_bps.to_string(),
        );
        context.insert(
            "max_trade_count_multiplier_bps".to_string(),
            request.envelope.max_trade_count_multiplier_bps.to_string(),
        );
        return fail_control(
            "session_operating_envelope",
            "Session-conditioned operating-envelope gate",
            RiskAction::Restrict,
            EntryMode::Normal,
            "OPERATING_ENVELOPE_RESTRICTED",
            "The session-conditioned operating envelope reduced the allowed size or trade count.",
            context,
        );
    }

    pass_control(
        "session_operating_envelope",
        "Session-conditioned operating-envelope gate",
        "The session-conditioned operating envelope remained in maintain posture.",
        context,
    )
}

fn strategy_behavior_drift_control(
    request: &RuntimeRiskRequest,
    current_abs_position: i64,
) -> RiskControlDecision {
    let health = &request.strategy_health;
    let limits = &request.limits;
    let behavior_exceeded = health.behavior_drift_bps > limits.max_behavior_drift_bps;
    let slippage_exceeded =
        health.fill_slippage_drift_bps > limits.max_fill_slippage_drift_bps;
    let severe = health.behavior_drift_bps > limits.severe_behavior_drift_bps
        || health.fill_slippage_drift_bps > limits.severe_fill_slippage_drift_bps;
    let context = BTreeMap::from([
        (
            "behavior_drift_bps".to_string(),
            health.behavior_drift_bps.to_string(),
        ),
        (
            "max_behavior_drift_bps".to_string(),
            limits.max_behavior_drift_bps.to_string(),
        ),
        (
            "severe_behavior_drift_bps".to_string(),
            limits.severe_behavior_drift_bps.to_string(),
        ),
        (
            "fill_slippage_drift_bps".to_string(),
            health.fill_slippage_drift_bps.to_string(),
        ),
        (
            "max_fill_slippage_drift_bps".to_string(),
            limits.max_fill_slippage_drift_bps.to_string(),
        ),
        (
            "severe_fill_slippage_drift_bps".to_string(),
            limits.severe_fill_slippage_drift_bps.to_string(),
        ),
        (
            "reference_window_id".to_string(),
            health.reference_window_id.clone(),
        ),
        ("reason_code".to_string(), health.reason_code.clone()),
    ]);

    if severe {
        let (action, entry_mode, reason_code, diagnostic) = if current_abs_position > 0 {
            (
                RiskAction::ExitOnly,
                EntryMode::ExitOnly,
                "STRATEGY_HEALTH_BEHAVIOR_DRIFT_EXIT_ONLY",
                "Strategy behavior drift exceeded the severe threshold while exposure was open, so the runtime moved to exit-only until recalibration.",
            )
        } else {
            (
                RiskAction::Restrict,
                EntryMode::NoNewEntries,
                "STRATEGY_HEALTH_BEHAVIOR_DRIFT_RESTRICT",
                "Strategy behavior drift exceeded the severe threshold, so new risk was suppressed until recalibration.",
            )
        };
        return fail_control(
            "strategy_behavior_drift",
            "Strategy behavior drift monitor",
            action,
            entry_mode,
            reason_code,
            diagnostic,
            context,
        );
    }

    if behavior_exceeded || slippage_exceeded {
        return fail_control(
            "strategy_behavior_drift",
            "Strategy behavior drift monitor",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "STRATEGY_HEALTH_BEHAVIOR_DRIFT_RESTRICT",
            "Strategy behavior drift exceeded the approved threshold and the runtime suppressed new risk pending review.",
            context,
        );
    }

    pass_control(
        "strategy_behavior_drift",
        "Strategy behavior drift monitor",
        "Behavior drift and fill slippage stayed within the approved runtime thresholds.",
        context,
    )
}

fn strategy_data_quality_control(request: &RuntimeRiskRequest) -> RiskControlDecision {
    let health = &request.strategy_health;
    let limits = &request.limits;
    let context = BTreeMap::from([
        (
            "data_quality_drift_bps".to_string(),
            health.data_quality_drift_bps.to_string(),
        ),
        (
            "max_data_quality_drift_bps".to_string(),
            limits.max_data_quality_drift_bps.to_string(),
        ),
        (
            "severe_data_quality_drift_bps".to_string(),
            limits.severe_data_quality_drift_bps.to_string(),
        ),
        (
            "reference_window_id".to_string(),
            health.reference_window_id.clone(),
        ),
        ("reason_code".to_string(), health.reason_code.clone()),
    ]);

    if health.data_quality_drift_bps > limits.severe_data_quality_drift_bps {
        return fail_control(
            "strategy_data_quality_drift",
            "Strategy data-quality drift monitor",
            RiskAction::Halt,
            EntryMode::NoNewEntries,
            "STRATEGY_HEALTH_DATA_QUALITY_HALT",
            "Strategy-health data quality drift exceeded the severe threshold and the runtime halted new trading decisions until operator review.",
            context,
        );
    }

    if health.data_quality_drift_bps > limits.max_data_quality_drift_bps {
        return fail_control(
            "strategy_data_quality_drift",
            "Strategy data-quality drift monitor",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "STRATEGY_HEALTH_DATA_QUALITY_RESTRICT",
            "Strategy-health data quality drift exceeded the approved threshold and the runtime restricted new risk pending review.",
            context,
        );
    }

    pass_control(
        "strategy_data_quality_drift",
        "Strategy data-quality drift monitor",
        "Strategy-health data quality remained within the approved runtime drift thresholds.",
        context,
    )
}

fn operating_envelope_fit_control(
    request: &RuntimeRiskRequest,
    current_abs_position: i64,
) -> RiskControlDecision {
    let health = &request.strategy_health;
    let limits = &request.limits;
    let context = BTreeMap::from([
        (
            "operating_envelope_fit_bps".to_string(),
            health.operating_envelope_fit_bps.to_string(),
        ),
        (
            "min_operating_envelope_fit_bps".to_string(),
            limits.min_operating_envelope_fit_bps.to_string(),
        ),
        (
            "hard_stop_operating_envelope_fit_bps".to_string(),
            limits.hard_stop_operating_envelope_fit_bps.to_string(),
        ),
        (
            "recalibration_required".to_string(),
            health.recalibration_required.to_string(),
        ),
        (
            "reference_window_id".to_string(),
            health.reference_window_id.clone(),
        ),
        ("reason_code".to_string(), health.reason_code.clone()),
        (
            "required_operating_posture".to_string(),
            request.envelope.required_operating_posture.clone(),
        ),
        (
            "current_operating_posture".to_string(),
            request.operating_posture.clone(),
        ),
    ]);

    if health.operating_envelope_fit_bps <= limits.hard_stop_operating_envelope_fit_bps {
        let (action, entry_mode, reason_code, diagnostic) = if current_abs_position > 0 {
            (
                RiskAction::Flatten,
                EntryMode::ForcedFlatten,
                "STRATEGY_HEALTH_OPERATING_ENVELOPE_FLATTEN",
                "Operating-envelope fit fell below the hard-stop threshold while exposure was open, so the runtime must flatten immediately.",
            )
        } else {
            (
                RiskAction::Restrict,
                EntryMode::NoNewEntries,
                "STRATEGY_HEALTH_OPERATING_ENVELOPE_RESTRICT",
                "Operating-envelope fit fell below the hard-stop threshold, so the runtime suppressed new entries until recalibration.",
            )
        };
        return fail_control(
            "strategy_operating_envelope_fit",
            "Strategy operating-envelope fit monitor",
            action,
            entry_mode,
            reason_code,
            diagnostic,
            context,
        );
    }

    if health.recalibration_required
        || health.operating_envelope_fit_bps < limits.min_operating_envelope_fit_bps
    {
        let (action, entry_mode) = if current_abs_position > 0 {
            (RiskAction::ExitOnly, EntryMode::ExitOnly)
        } else {
            (RiskAction::Restrict, EntryMode::NoNewEntries)
        };
        let reason_code = if health.recalibration_required {
            "STRATEGY_HEALTH_RECALIBRATION_REQUIRED"
        } else {
            "STRATEGY_HEALTH_OPERATING_ENVELOPE_RESTRICT"
        };
        let diagnostic = if health.recalibration_required {
            "The strategy-health lane requested recalibration before new risk can be added."
        } else {
            "Operating-envelope fit fell below the approved threshold, so the runtime restricted new risk pending review."
        };
        return fail_control(
            "strategy_operating_envelope_fit",
            "Strategy operating-envelope fit monitor",
            action,
            entry_mode,
            reason_code,
            diagnostic,
            context,
        );
    }

    pass_control(
        "strategy_operating_envelope_fit",
        "Strategy operating-envelope fit monitor",
        "Operating-envelope fit remained inside the approved runtime threshold and no recalibration was required.",
        context,
    )
}

/// Evaluates runtime trading eligibility and baseline risk controls.
pub fn evaluate_runtime_risk(request: &RuntimeRiskRequest) -> RuntimeRiskReport {
    let mut issues = Vec::new();
    if request.symbol.trim().is_empty() {
        issues.push("symbol");
    }
    if request.session_id.trim().is_empty() {
        issues.push("session_id");
    }
    if request.operating_posture.trim().is_empty() {
        issues.push("operating_posture");
    }
    if request.limits.max_position_contracts <= 0 {
        issues.push("max_position_contracts");
    }
    if request.limits.max_concurrent_order_intents == 0 {
        issues.push("max_concurrent_order_intents");
    }
    if request.limits.max_behavior_drift_bps == 0 {
        issues.push("max_behavior_drift_bps");
    }
    if request.limits.max_fill_slippage_drift_bps == 0 {
        issues.push("max_fill_slippage_drift_bps");
    }
    if request.limits.severe_behavior_drift_bps < request.limits.max_behavior_drift_bps {
        issues.push("severe_behavior_drift_bps");
    }
    if request.limits.severe_fill_slippage_drift_bps
        < request.limits.max_fill_slippage_drift_bps
    {
        issues.push("severe_fill_slippage_drift_bps");
    }
    if request.limits.max_data_quality_drift_bps == 0 {
        issues.push("max_data_quality_drift_bps");
    }
    if request.limits.severe_data_quality_drift_bps
        < request.limits.max_data_quality_drift_bps
    {
        issues.push("severe_data_quality_drift_bps");
    }
    if request.limits.min_operating_envelope_fit_bps == 0
        || request.limits.min_operating_envelope_fit_bps > 10_000
    {
        issues.push("min_operating_envelope_fit_bps");
    }
    if request.limits.hard_stop_operating_envelope_fit_bps
        > request.limits.min_operating_envelope_fit_bps
    {
        issues.push("hard_stop_operating_envelope_fit_bps");
    }
    if request.limits.max_initial_margin_requirement_usd_cents <= 0 {
        issues.push("max_initial_margin_requirement_usd_cents");
    }
    if request.limits.max_maintenance_margin_requirement_usd_cents <= 0 {
        issues.push("max_maintenance_margin_requirement_usd_cents");
    }
    if request.envelope.size_multiplier_bps == 0 || request.envelope.size_multiplier_bps > 10_000 {
        issues.push("size_multiplier_bps");
    }
    if request.envelope.max_trade_count_multiplier_bps == 0
        || request.envelope.max_trade_count_multiplier_bps > 10_000
    {
        issues.push("max_trade_count_multiplier_bps");
    }
    if request
        .envelope
        .required_operating_posture
        .trim()
        .is_empty()
    {
        issues.push("required_operating_posture");
    }
    if request.limits.required_overnight_posture.trim().is_empty() {
        issues.push("required_overnight_posture");
    }
    if request.strategy_health.operating_envelope_fit_bps > 10_000 {
        issues.push("strategy_health.operating_envelope_fit_bps");
    }
    if request.strategy_health.reference_window_id.trim().is_empty() {
        issues.push("strategy_health.reference_window_id");
    }
    if request.strategy_health.reason_code.trim().is_empty() {
        issues.push("strategy_health.reason_code");
    }
    if !issues.is_empty() {
        return invalid_report(request, issues);
    }

    let effective_max_position_contracts = scaled_contract_limit(
        request.limits.max_position_contracts,
        request.envelope.size_multiplier_bps,
    );
    let effective_max_concurrent_order_intents = scaled_count_limit(
        request.limits.max_concurrent_order_intents,
        request.envelope.max_trade_count_multiplier_bps,
    );
    let current_abs_position = request.exposure.current_position_contracts.abs();
    let projected_abs_position = request.exposure.projected_position_contracts.abs();
    let first_trade_pending = current_abs_position == 0
        && projected_abs_position > 0
        && request.proposed_order_increases_risk;
    let market_data_degraded = !request.market_data.market_data_fresh
        || request.market_data.stale_quote_rate_bps > request.limits.degraded_data_stale_quote_bps
        || !request.market_data.parity_healthy;

    let mut decisions = Vec::new();

    decisions.push(if request.session_tradeable {
        pass_control(
            "session_tradeability",
            "Session tradeability gate",
            "The compiled session topology kept the runtime in a tradeable slice.",
            BTreeMap::from([
                ("session_tradeable".to_string(), "true".to_string()),
                ("session_id".to_string(), request.session_id.clone()),
            ]),
        )
    } else {
        let (action, entry_mode) = if current_abs_position > 0 {
            (RiskAction::ExitOnly, EntryMode::ExitOnly)
        } else {
            (RiskAction::Restrict, EntryMode::NoNewEntries)
        };
        fail_control(
            "session_tradeability",
            "Session tradeability gate",
            action,
            entry_mode,
            "RUNTIME_SESSION_NOT_TRADEABLE",
            "The compiled session topology marked this slice as non-tradeable.",
            BTreeMap::from([
                ("session_tradeable".to_string(), "false".to_string()),
                ("session_id".to_string(), request.session_id.clone()),
            ]),
        )
    });

    decisions.push(
        if current_abs_position > effective_max_position_contracts
            || projected_abs_position > effective_max_position_contracts
        {
            let (action, entry_mode) = if current_abs_position > effective_max_position_contracts {
                (RiskAction::ExitOnly, EntryMode::ExitOnly)
            } else {
                (RiskAction::Restrict, EntryMode::NoNewEntries)
            };
            fail_control(
                "max_position_limit",
                "Maximum position limit",
                action,
                entry_mode,
                "BASELINE_RISK_POSITION_LIMIT_EXCEEDED",
                "Projected or active exposure exceeded the effective maximum position limit.",
                BTreeMap::from([
                    (
                        "current_position_contracts".to_string(),
                        request.exposure.current_position_contracts.to_string(),
                    ),
                    (
                        "projected_position_contracts".to_string(),
                        request.exposure.projected_position_contracts.to_string(),
                    ),
                    (
                        "effective_max_position_contracts".to_string(),
                        effective_max_position_contracts.to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "max_position_limit",
                "Maximum position limit",
                "Projected and active exposure stayed within the effective position limit.",
                BTreeMap::from([
                    (
                        "effective_max_position_contracts".to_string(),
                        effective_max_position_contracts.to_string(),
                    ),
                    (
                        "projected_position_contracts".to_string(),
                        request.exposure.projected_position_contracts.to_string(),
                    ),
                ]),
            )
        },
    );

    decisions.push(
        if request.exposure.pending_order_intent_count > effective_max_concurrent_order_intents {
            fail_control(
                "max_concurrent_order_intents",
                "Concurrent order-intent limit",
                RiskAction::Restrict,
                EntryMode::NoNewEntries,
                "BASELINE_RISK_CONCURRENT_ORDER_INTENT_LIMIT_EXCEEDED",
                "Pending order-intent count exceeded the effective concurrency limit.",
                BTreeMap::from([
                    (
                        "pending_order_intent_count".to_string(),
                        request.exposure.pending_order_intent_count.to_string(),
                    ),
                    (
                        "effective_max_concurrent_order_intents".to_string(),
                        effective_max_concurrent_order_intents.to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "max_concurrent_order_intents",
                "Concurrent order-intent limit",
                "Pending order-intent count stayed within the effective concurrency limit.",
                BTreeMap::from([
                    (
                        "pending_order_intent_count".to_string(),
                        request.exposure.pending_order_intent_count.to_string(),
                    ),
                    (
                        "effective_max_concurrent_order_intents".to_string(),
                        effective_max_concurrent_order_intents.to_string(),
                    ),
                ]),
            )
        },
    );

    decisions.push(if market_data_degraded && request.proposed_order_increases_risk {
        fail_control(
            "degraded_data_entry_suppression",
            "Degraded-data entry suppression",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "BASELINE_RISK_DATA_DEGRADED_ENTRY_SUPPRESSION",
            "Market-data freshness or parity degraded while the requested action would increase risk.",
            BTreeMap::from([
                (
                    "market_data_fresh".to_string(),
                    request.market_data.market_data_fresh.to_string(),
                ),
                (
                    "stale_quote_rate_bps".to_string(),
                    request.market_data.stale_quote_rate_bps.to_string(),
                ),
                (
                    "parity_healthy".to_string(),
                    request.market_data.parity_healthy.to_string(),
                ),
                (
                    "degraded_data_stale_quote_bps".to_string(),
                    request.limits.degraded_data_stale_quote_bps.to_string(),
                ),
            ]),
        )
    } else {
        pass_control(
            "degraded_data_entry_suppression",
            "Degraded-data entry suppression",
            "Market-data freshness and parity conditions permitted the requested risk change.",
            BTreeMap::from([
                (
                    "market_data_fresh".to_string(),
                    request.market_data.market_data_fresh.to_string(),
                ),
                (
                    "stale_quote_rate_bps".to_string(),
                    request.market_data.stale_quote_rate_bps.to_string(),
                ),
                (
                    "parity_healthy".to_string(),
                    request.market_data.parity_healthy.to_string(),
                ),
            ]),
        )
    });

    decisions.push(strategy_behavior_drift_control(
        request,
        current_abs_position,
    ));

    decisions.push(strategy_data_quality_control(request));

    decisions.push(operating_envelope_fit_control(
        request,
        current_abs_position,
    ));

    decisions.push(
        if request.exposure.realized_loss_usd_cents >= request.limits.daily_loss_lockout_usd_cents {
            fail_control(
                "daily_loss_lockout",
                "Daily loss lockout",
                RiskAction::ExitOnly,
                EntryMode::ExitOnly,
                "BASELINE_RISK_DAILY_LOSS_LOCKOUT",
                "Daily realized loss breached the hard lockout threshold.",
                BTreeMap::from([
                    (
                        "realized_loss_usd_cents".to_string(),
                        request.exposure.realized_loss_usd_cents.to_string(),
                    ),
                    (
                        "daily_loss_lockout_usd_cents".to_string(),
                        request.limits.daily_loss_lockout_usd_cents.to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "daily_loss_lockout",
                "Daily loss lockout",
                "Daily realized loss remained below the hard lockout threshold.",
                BTreeMap::from([
                    (
                        "realized_loss_usd_cents".to_string(),
                        request.exposure.realized_loss_usd_cents.to_string(),
                    ),
                    (
                        "daily_loss_lockout_usd_cents".to_string(),
                        request.limits.daily_loss_lockout_usd_cents.to_string(),
                    ),
                ]),
            )
        },
    );

    decisions.push(
        if request.exposure.drawdown_usd_cents >= request.limits.max_drawdown_usd_cents {
            fail_control(
                "max_drawdown_flatten",
                "Max drawdown flatten",
                RiskAction::Flatten,
                EntryMode::ForcedFlatten,
                "BASELINE_RISK_MAX_DRAWDOWN",
                "Cumulative drawdown breached the hard flatten threshold.",
                BTreeMap::from([
                    (
                        "drawdown_usd_cents".to_string(),
                        request.exposure.drawdown_usd_cents.to_string(),
                    ),
                    (
                        "max_drawdown_usd_cents".to_string(),
                        request.limits.max_drawdown_usd_cents.to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "max_drawdown_flatten",
                "Max drawdown flatten",
                "Cumulative drawdown remained inside the hard flatten threshold.",
                BTreeMap::from([
                    (
                        "drawdown_usd_cents".to_string(),
                        request.exposure.drawdown_usd_cents.to_string(),
                    ),
                    (
                        "max_drawdown_usd_cents".to_string(),
                        request.limits.max_drawdown_usd_cents.to_string(),
                    ),
                ]),
            )
        },
    );

    decisions.push(
        if request.delivery_window_active && projected_abs_position > 0 {
            let (action, entry_mode) = if current_abs_position > 0 {
                (RiskAction::Flatten, EntryMode::ForcedFlatten)
            } else {
                (RiskAction::Restrict, EntryMode::NoNewEntries)
            };
            fail_control(
                "delivery_fence_forced_flat",
                "Delivery-fence forced flat",
                action,
                entry_mode,
                "BASELINE_RISK_DELIVERY_FENCE_FLATTEN",
                "The delivery fence is active, so the runtime cannot carry or increase exposure.",
                BTreeMap::from([
                    (
                        "delivery_window_active".to_string(),
                        request.delivery_window_active.to_string(),
                    ),
                    (
                        "projected_position_contracts".to_string(),
                        request.exposure.projected_position_contracts.to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "delivery_fence_forced_flat",
                "Delivery-fence forced flat",
                "No active delivery fence blocked or liquidated exposure in this request.",
                BTreeMap::from([(
                    "delivery_window_active".to_string(),
                    request.delivery_window_active.to_string(),
                )]),
            )
        },
    );

    decisions.push(if first_trade_pending
        && (request.warmup.history_bars_observed < request.limits.warmup_min_history_bars
            || request.warmup.history_minutes_observed < request.limits.warmup_min_history_minutes
            || (request.limits.warmup_requires_state_seed && !request.warmup.state_seed_loaded))
    {
        fail_control(
            "warmup_hold",
            "Warm-up hold",
            RiskAction::Restrict,
            EntryMode::NoNewEntries,
            "BASELINE_RISK_WARMUP_HOLD",
            "The first live trade is still gated by the required warm-up history or seed state.",
            BTreeMap::from([
                (
                    "history_bars_observed".to_string(),
                    request.warmup.history_bars_observed.to_string(),
                ),
                (
                    "history_minutes_observed".to_string(),
                    request.warmup.history_minutes_observed.to_string(),
                ),
                (
                    "state_seed_loaded".to_string(),
                    request.warmup.state_seed_loaded.to_string(),
                ),
                (
                    "warmup_min_history_bars".to_string(),
                    request.limits.warmup_min_history_bars.to_string(),
                ),
                (
                    "warmup_min_history_minutes".to_string(),
                    request.limits.warmup_min_history_minutes.to_string(),
                ),
            ]),
        )
    } else {
        pass_control(
            "warmup_hold",
            "Warm-up hold",
            "The request either was not a first trade or already satisfied the warm-up requirements.",
            BTreeMap::from([
                (
                    "history_bars_observed".to_string(),
                    request.warmup.history_bars_observed.to_string(),
                ),
                (
                    "history_minutes_observed".to_string(),
                    request.warmup.history_minutes_observed.to_string(),
                ),
            ]),
        )
    });

    decisions.push(
        if request.exposure.initial_margin_requirement_usd_cents
            > request.limits.max_initial_margin_requirement_usd_cents
            || request.exposure.maintenance_margin_requirement_usd_cents
                > request.limits.max_maintenance_margin_requirement_usd_cents
        {
            fail_control(
                "margin_pretrade_check",
                "Margin-aware pre-trade check",
                RiskAction::Halt,
                EntryMode::NoNewEntries,
                "BASELINE_RISK_MARGIN_LIMIT",
                "Margin requirements exceeded the hard runtime limits.",
                BTreeMap::from([
                    (
                        "initial_margin_requirement_usd_cents".to_string(),
                        request
                            .exposure
                            .initial_margin_requirement_usd_cents
                            .to_string(),
                    ),
                    (
                        "maintenance_margin_requirement_usd_cents".to_string(),
                        request
                            .exposure
                            .maintenance_margin_requirement_usd_cents
                            .to_string(),
                    ),
                    (
                        "max_initial_margin_requirement_usd_cents".to_string(),
                        request
                            .limits
                            .max_initial_margin_requirement_usd_cents
                            .to_string(),
                    ),
                    (
                        "max_maintenance_margin_requirement_usd_cents".to_string(),
                        request
                            .limits
                            .max_maintenance_margin_requirement_usd_cents
                            .to_string(),
                    ),
                ]),
            )
        } else {
            pass_control(
                "margin_pretrade_check",
                "Margin-aware pre-trade check",
                "Margin requirements remained within the hard runtime limits.",
                BTreeMap::from([
                    (
                        "initial_margin_requirement_usd_cents".to_string(),
                        request
                            .exposure
                            .initial_margin_requirement_usd_cents
                            .to_string(),
                    ),
                    (
                        "maintenance_margin_requirement_usd_cents".to_string(),
                        request
                            .exposure
                            .maintenance_margin_requirement_usd_cents
                            .to_string(),
                    ),
                ]),
            )
        },
    );

    decisions.push(if request.overnight_requested
        && (!request.overnight_approval_granted
            || !request.envelope.overnight_carry_allowed
            || (request.limits.overnight_only_with_strict_posture
                && request.operating_posture != request.limits.required_overnight_posture))
    {
        let strict_posture_missing = request.limits.overnight_only_with_strict_posture
            && request.operating_posture != request.limits.required_overnight_posture;
        let (action, entry_mode) = if current_abs_position > 0 {
            (RiskAction::ExitOnly, EntryMode::ExitOnly)
        } else {
            (RiskAction::Restrict, EntryMode::NoNewEntries)
        };
        fail_control(
            "overnight_approval",
            "Overnight approval",
            action,
            entry_mode,
            if strict_posture_missing {
                "BASELINE_RISK_OVERNIGHT_STRICT_POSTURE_REQUIRED"
            } else {
                "BASELINE_RISK_OVERNIGHT_APPROVAL_REQUIRED"
            },
            "Overnight carry requires explicit approval, approved envelope state, and the strict overnight posture where required.",
            BTreeMap::from([
                (
                    "overnight_requested".to_string(),
                    request.overnight_requested.to_string(),
                ),
                (
                    "overnight_approval_granted".to_string(),
                    request.overnight_approval_granted.to_string(),
                ),
                (
                    "operating_posture".to_string(),
                    request.operating_posture.clone(),
                ),
                (
                    "required_overnight_posture".to_string(),
                    request.limits.required_overnight_posture.clone(),
                ),
                (
                    "envelope_overnight_carry_allowed".to_string(),
                    request.envelope.overnight_carry_allowed.to_string(),
                ),
            ]),
        )
    } else {
        pass_control(
            "overnight_approval",
            "Overnight approval",
            "No blocked overnight carry condition was active for this request.",
            BTreeMap::from([
                (
                    "overnight_requested".to_string(),
                    request.overnight_requested.to_string(),
                ),
                (
                    "overnight_approval_granted".to_string(),
                    request.overnight_approval_granted.to_string(),
                ),
            ]),
        )
    });

    decisions.push(envelope_control(
        request,
        effective_max_position_contracts,
        effective_max_concurrent_order_intents,
    ));

    let triggered_control_ids = decisions
        .iter()
        .filter(|decision| !decision.passed)
        .map(|decision| decision.control_id.clone())
        .collect::<Vec<_>>();
    let triggered_reason_codes = decisions
        .iter()
        .filter_map(|decision| (!decision.passed).then(|| decision.reason_code.clone()))
        .flatten()
        .collect::<Vec<_>>();
    let action = dominant_action(&decisions);
    let entry_mode = dominant_entry_mode(&decisions, action);
    let status = match action {
        RiskAction::Allow => EligibilityStatus::Eligible,
        RiskAction::Restrict => EligibilityStatus::Restricted,
        RiskAction::ExitOnly => EligibilityStatus::ExitOnly,
        RiskAction::Flatten => EligibilityStatus::Flatten,
        RiskAction::Halt => EligibilityStatus::Halted,
    };
    let dominant_severity = action_severity(action);
    let reason_code = decisions
        .iter()
        .filter(|decision| {
            !decision.passed && action_severity(decision.action) == dominant_severity
        })
        .find_map(|decision| decision.reason_code.clone())
        .unwrap_or_else(|| "RUNTIME_RISK_ALLOW".to_string());

    let explanation = if triggered_control_ids.is_empty() {
        "All runtime eligibility and baseline risk controls passed.".to_string()
    } else {
        format!(
            "Runtime eligibility changed to {} because these controls triggered: {}.",
            status.as_str(),
            triggered_control_ids.join(", ")
        )
    };

    RuntimeRiskReport {
        request_id: request.request_id.clone(),
        status,
        action,
        entry_mode,
        reason_code,
        retained_artifact_id: format!("runtime_state/risk/{}", request.request_id),
        trading_eligible: matches!(
            status,
            EligibilityStatus::Eligible | EligibilityStatus::Restricted
        ),
        allow_new_risk: matches!(entry_mode, EntryMode::Normal | EntryMode::PassiveOnly),
        require_flatten: status == EligibilityStatus::Flatten,
        effective_max_position_contracts,
        effective_max_concurrent_order_intents,
        effective_size_multiplier_bps: request.envelope.size_multiplier_bps,
        effective_max_trade_count_multiplier_bps: request.envelope.max_trade_count_multiplier_bps,
        triggered_control_ids,
        triggered_reason_codes,
        decisions,
        explanation,
    }
}

fn base_request() -> RuntimeRiskRequest {
    RuntimeRiskRequest {
        request_id: "runtime-risk-green-pass".to_string(),
        symbol: "1OZ".to_string(),
        session_id: "globex_2026_03_18".to_string(),
        session_tradeable: true,
        delivery_window_active: false,
        operating_posture: "intraday".to_string(),
        proposed_order_increases_risk: true,
        overnight_requested: false,
        overnight_approval_granted: false,
        limits: RuntimeRiskLimits {
            max_position_contracts: 3,
            max_concurrent_order_intents: 2,
            degraded_data_stale_quote_bps: 50,
            max_behavior_drift_bps: 180,
            max_fill_slippage_drift_bps: 120,
            severe_behavior_drift_bps: 320,
            severe_fill_slippage_drift_bps: 220,
            max_data_quality_drift_bps: 140,
            severe_data_quality_drift_bps: 260,
            min_operating_envelope_fit_bps: 9_000,
            hard_stop_operating_envelope_fit_bps: 7_000,
            daily_loss_lockout_usd_cents: 50_000,
            max_drawdown_usd_cents: 120_000,
            max_initial_margin_requirement_usd_cents: 150_000,
            max_maintenance_margin_requirement_usd_cents: 110_000,
            warmup_min_history_bars: 60,
            warmup_min_history_minutes: 45,
            warmup_requires_state_seed: true,
            overnight_only_with_strict_posture: true,
            required_overnight_posture: "overnight_strict".to_string(),
        },
        exposure: RuntimeExposureSnapshot {
            current_position_contracts: 0,
            projected_position_contracts: 1,
            pending_order_intent_count: 0,
            realized_loss_usd_cents: 0,
            drawdown_usd_cents: 0,
            initial_margin_requirement_usd_cents: 95_000,
            maintenance_margin_requirement_usd_cents: 75_000,
        },
        market_data: MarketDataHealthSnapshot {
            market_data_fresh: true,
            stale_quote_rate_bps: 10,
            parity_healthy: true,
        },
        warmup: WarmupSnapshot {
            history_bars_observed: 120,
            history_minutes_observed: 90,
            state_seed_loaded: true,
        },
        strategy_health: StrategyHealthSnapshot {
            behavior_drift_bps: 40,
            fill_slippage_drift_bps: 35,
            data_quality_drift_bps: 20,
            operating_envelope_fit_bps: 9_800,
            recalibration_required: false,
            reference_window_id: "strategy-health-window-2026-03-18T13:30Z".to_string(),
            reason_code: "STRATEGY_HEALTH_GREEN".to_string(),
        },
        envelope: OperatingEnvelopeSnapshot {
            session_class: "regular_comex".to_string(),
            reason_code: "OPERATING_ENVELOPE_GREEN".to_string(),
            actions: vec![OperatingEnvelopeAction::Maintain],
            size_multiplier_bps: 10_000,
            max_trade_count_multiplier_bps: 10_000,
            required_operating_posture: "intraday".to_string(),
            overnight_carry_allowed: false,
        },
    }
}

/// Built-in runtime-risk scenarios used by the isolated smoke path and tests.
pub fn sample_runtime_risk_request(name: &str) -> Option<RuntimeRiskRequest> {
    let mut request = base_request();
    match name {
        "green-tradeable-pass" => Some(request),
        "degraded-data-restrict" => {
            request.request_id = "runtime-risk-degraded-data".to_string();
            request.market_data.market_data_fresh = false;
            request.market_data.stale_quote_rate_bps = 240;
            request.market_data.parity_healthy = false;
            request.envelope.session_class = "degraded_data".to_string();
            request.envelope.reason_code = "OPERATING_ENVELOPE_DEGRADED_DATA".to_string();
            request.envelope.actions = vec![OperatingEnvelopeAction::EntrySuppression];
            Some(request)
        }
        "daily-loss-exit-only" => {
            request.request_id = "runtime-risk-daily-loss".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.exposure.realized_loss_usd_cents = 60_000;
            Some(request)
        }
        "drawdown-flatten" => {
            request.request_id = "runtime-risk-drawdown".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.exposure.drawdown_usd_cents = 150_000;
            Some(request)
        }
        "delivery-fence-flatten" => {
            request.request_id = "runtime-risk-delivery-fence".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.delivery_window_active = true;
            request.envelope.session_class = "maintenance_adjacent".to_string();
            request.envelope.reason_code = "OPERATING_ENVELOPE_DELIVERY_FENCE".to_string();
            Some(request)
        }
        "warmup-hold" => {
            request.request_id = "runtime-risk-warmup".to_string();
            request.warmup.history_bars_observed = 10;
            request.warmup.history_minutes_observed = 8;
            request.warmup.state_seed_loaded = false;
            Some(request)
        }
        "margin-halt" => {
            request.request_id = "runtime-risk-margin".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 2;
            request.exposure.initial_margin_requirement_usd_cents = 200_000;
            request.exposure.maintenance_margin_requirement_usd_cents = 140_000;
            Some(request)
        }
        "overnight-approval-block" => {
            request.request_id = "runtime-risk-overnight".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.overnight_requested = true;
            request.overnight_approval_granted = false;
            request.operating_posture = "intraday".to_string();
            request.envelope.session_class = "overnight".to_string();
            request.envelope.reason_code = "OPERATING_ENVELOPE_OVERNIGHT".to_string();
            request.envelope.actions = vec![OperatingEnvelopeAction::NoNewOvernightCarry];
            request.envelope.required_operating_posture = "overnight_strict".to_string();
            request.envelope.overnight_carry_allowed = false;
            Some(request)
        }
        "size-reduction-restrict" => {
            request.request_id = "runtime-risk-size-reduction".to_string();
            request.exposure.projected_position_contracts = 2;
            request.exposure.pending_order_intent_count = 1;
            request.envelope.session_class = "macro_event".to_string();
            request.envelope.reason_code = "OPERATING_ENVELOPE_YELLOW".to_string();
            request.envelope.actions = vec![
                OperatingEnvelopeAction::SizeReduction,
                OperatingEnvelopeAction::LowerMaxTrades,
            ];
            request.envelope.size_multiplier_bps = 5_000;
            request.envelope.max_trade_count_multiplier_bps = 5_000;
            Some(request)
        }
        "behavior-drift-restrict" => {
            request.request_id = "runtime-risk-behavior-drift".to_string();
            request.strategy_health.behavior_drift_bps = 240;
            request.strategy_health.fill_slippage_drift_bps = 150;
            request.strategy_health.reason_code = "STRATEGY_HEALTH_BEHAVIOR_DRIFT".to_string();
            Some(request)
        }
        "behavior-drift-exit-only" => {
            request.request_id = "runtime-risk-behavior-drift-severe".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.strategy_health.behavior_drift_bps = 360;
            request.strategy_health.fill_slippage_drift_bps = 260;
            request.strategy_health.reason_code = "STRATEGY_HEALTH_BEHAVIOR_DRIFT".to_string();
            Some(request)
        }
        "data-quality-halt" => {
            request.request_id = "runtime-risk-data-quality-drift".to_string();
            request.strategy_health.data_quality_drift_bps = 320;
            request.strategy_health.reason_code =
                "STRATEGY_HEALTH_DATA_QUALITY_DRIFT".to_string();
            Some(request)
        }
        "operating-envelope-fit-restrict" => {
            request.request_id = "runtime-risk-envelope-fit".to_string();
            request.strategy_health.operating_envelope_fit_bps = 8_300;
            request.strategy_health.reason_code =
                "STRATEGY_HEALTH_OPERATING_ENVELOPE_DRIFT".to_string();
            Some(request)
        }
        "operating-envelope-fit-flatten" => {
            request.request_id = "runtime-risk-envelope-fit-hard-stop".to_string();
            request.exposure.current_position_contracts = 1;
            request.exposure.projected_position_contracts = 1;
            request.strategy_health.operating_envelope_fit_bps = 6_400;
            request.strategy_health.recalibration_required = true;
            request.strategy_health.reason_code =
                "STRATEGY_HEALTH_OPERATING_ENVELOPE_DRIFT".to_string();
            Some(request)
        }
        "recalibration-required-restrict" => {
            request.request_id = "runtime-risk-recalibration".to_string();
            request.strategy_health.recalibration_required = true;
            request.strategy_health.reason_code =
                "STRATEGY_HEALTH_RECALIBRATION_REVIEW".to_string();
            Some(request)
        }
        _ => None,
    }
}

/// Writes the runtime risk request and report to the provided artifact directory.
pub fn write_runtime_risk_artifacts(
    root: &Path,
    request: &RuntimeRiskRequest,
    report: &RuntimeRiskReport,
) -> std::io::Result<()> {
    write_report_artifacts(root, request, report)
}

#[cfg(test)]
mod tests {
    use super::{
        EligibilityStatus, EntryMode, RiskAction, evaluate_runtime_risk,
        sample_runtime_risk_request,
    };

    #[test]
    fn green_scenario_remains_eligible() {
        let request =
            sample_runtime_risk_request("green-tradeable-pass").expect("green scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Eligible, report.status);
        assert_eq!(RiskAction::Allow, report.action);
        assert_eq!(EntryMode::Normal, report.entry_mode);
        assert_eq!("RUNTIME_RISK_ALLOW", report.reason_code);
        assert!(report.trading_eligible);
        assert!(report.allow_new_risk);
    }

    #[test]
    fn degraded_data_blocks_new_entries() {
        let request = sample_runtime_risk_request("degraded-data-restrict")
            .expect("degraded-data scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Restricted, report.status);
        assert_eq!(RiskAction::Restrict, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!(
            "BASELINE_RISK_DATA_DEGRADED_ENTRY_SUPPRESSION",
            report.reason_code
        );
        assert!(
            report
                .triggered_control_ids
                .contains(&"degraded_data_entry_suppression".to_string())
        );
    }

    #[test]
    fn daily_loss_switches_to_exit_only() {
        let request = sample_runtime_risk_request("daily-loss-exit-only")
            .expect("daily loss scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::ExitOnly, report.status);
        assert_eq!(RiskAction::ExitOnly, report.action);
        assert_eq!(EntryMode::ExitOnly, report.entry_mode);
        assert_eq!("BASELINE_RISK_DAILY_LOSS_LOCKOUT", report.reason_code);
    }

    #[test]
    fn drawdown_requires_immediate_flatten() {
        let request =
            sample_runtime_risk_request("drawdown-flatten").expect("drawdown scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Flatten, report.status);
        assert_eq!(RiskAction::Flatten, report.action);
        assert_eq!(EntryMode::ForcedFlatten, report.entry_mode);
        assert_eq!("BASELINE_RISK_MAX_DRAWDOWN", report.reason_code);
        assert!(report.require_flatten);
    }

    #[test]
    fn margin_breach_halts_trading() {
        let request = sample_runtime_risk_request("margin-halt").expect("margin scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Halted, report.status);
        assert_eq!(RiskAction::Halt, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!("BASELINE_RISK_MARGIN_LIMIT", report.reason_code);
        assert!(!report.trading_eligible);
    }

    #[test]
    fn overnight_block_requires_approval_and_strict_posture() {
        let request = sample_runtime_risk_request("overnight-approval-block")
            .expect("overnight scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::ExitOnly, report.status);
        assert_eq!(RiskAction::ExitOnly, report.action);
        assert_eq!(EntryMode::ExitOnly, report.entry_mode);
        assert_eq!(
            "BASELINE_RISK_OVERNIGHT_STRICT_POSTURE_REQUIRED",
            report.reason_code
        );
    }

    #[test]
    fn size_reduction_scales_effective_limits() {
        let request = sample_runtime_risk_request("size-reduction-restrict")
            .expect("size reduction scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Restricted, report.status);
        assert_eq!(RiskAction::Restrict, report.action);
        assert_eq!(EntryMode::Normal, report.entry_mode);
        assert_eq!("OPERATING_ENVELOPE_RESTRICTED", report.reason_code);
        assert_eq!(2, report.effective_max_position_contracts);
        assert_eq!(1, report.effective_max_concurrent_order_intents);
    }

    #[test]
    fn moderate_behavior_drift_restricts_new_entries() {
        let request = sample_runtime_risk_request("behavior-drift-restrict")
            .expect("behavior drift scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Restricted, report.status);
        assert_eq!(RiskAction::Restrict, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!("STRATEGY_HEALTH_BEHAVIOR_DRIFT_RESTRICT", report.reason_code);
        assert!(
            report
                .triggered_control_ids
                .contains(&"strategy_behavior_drift".to_string())
        );
    }

    #[test]
    fn severe_behavior_drift_switches_open_exposure_to_exit_only() {
        let request = sample_runtime_risk_request("behavior-drift-exit-only")
            .expect("severe behavior drift scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::ExitOnly, report.status);
        assert_eq!(RiskAction::ExitOnly, report.action);
        assert_eq!(EntryMode::ExitOnly, report.entry_mode);
        assert_eq!(
            "STRATEGY_HEALTH_BEHAVIOR_DRIFT_EXIT_ONLY",
            report.reason_code
        );
    }

    #[test]
    fn severe_data_quality_drift_halts_runtime() {
        let request = sample_runtime_risk_request("data-quality-halt")
            .expect("data-quality drift scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Halted, report.status);
        assert_eq!(RiskAction::Halt, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!("STRATEGY_HEALTH_DATA_QUALITY_HALT", report.reason_code);
        assert!(!report.trading_eligible);
    }

    #[test]
    fn low_operating_envelope_fit_restricts_new_risk() {
        let request = sample_runtime_risk_request("operating-envelope-fit-restrict")
            .expect("operating-envelope fit scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Restricted, report.status);
        assert_eq!(RiskAction::Restrict, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!(
            "STRATEGY_HEALTH_OPERATING_ENVELOPE_RESTRICT",
            report.reason_code
        );
    }

    #[test]
    fn hard_stop_operating_envelope_fit_flattens_open_exposure() {
        let request = sample_runtime_risk_request("operating-envelope-fit-flatten")
            .expect("hard-stop operating-envelope fit scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Flatten, report.status);
        assert_eq!(RiskAction::Flatten, report.action);
        assert_eq!(EntryMode::ForcedFlatten, report.entry_mode);
        assert_eq!(
            "STRATEGY_HEALTH_OPERATING_ENVELOPE_FLATTEN",
            report.reason_code
        );
        assert!(report.require_flatten);
    }

    #[test]
    fn recalibration_requirement_blocks_new_risk_even_without_low_fit() {
        let request = sample_runtime_risk_request("recalibration-required-restrict")
            .expect("recalibration scenario exists");
        let report = evaluate_runtime_risk(&request);

        assert_eq!(EligibilityStatus::Restricted, report.status);
        assert_eq!(RiskAction::Restrict, report.action);
        assert_eq!(EntryMode::NoNewEntries, report.entry_mode);
        assert_eq!("STRATEGY_HEALTH_RECALIBRATION_REQUIRED", report.reason_code);
    }
}
