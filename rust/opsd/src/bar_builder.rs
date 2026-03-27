//! Entitlement-aware live bar builder for the execution lane.
//!
//! This module is intentionally self-contained so the live-bar semantics can be
//! implemented and exercised without coupling to unrelated in-flight runtime
//! work. It uses the current `opsd` schedule/runtime vocabulary but does not
//! require ownership of the broader daemon surfaces.

use std::fs;
use std::path::Path;

/// Session states that matter to bar construction.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionState {
    Tradeable,
    ResetBoundary,
    Maintenance,
    DeliveryFence,
    PolicyRestricted,
    Closed,
}

impl SessionState {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Tradeable => "tradeable",
            Self::ResetBoundary => "reset_boundary",
            Self::Maintenance => "maintenance",
            Self::DeliveryFence => "delivery_fence",
            Self::PolicyRestricted => "policy_restricted",
            Self::Closed => "closed",
        }
    }
}

/// Entitlement surfaces relevant to the first live bar lane.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MarketDataEntitlement {
    LiveTopOfBook,
    DelayedTopOfBook,
    Missing,
}

impl MarketDataEntitlement {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::LiveTopOfBook => "live_top_of_book",
            Self::DelayedTopOfBook => "delayed_top_of_book",
            Self::Missing => "missing",
        }
    }
}

/// Raw event kinds admitted by the bar builder.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MarketDataEventKind {
    Trade,
    Quote,
}

impl MarketDataEventKind {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Trade => "trade",
            Self::Quote => "quote",
        }
    }
}

/// Source that actually determined the emitted bar.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BarSource {
    Trades,
    QuoteFallback,
}

impl BarSource {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Trades => "trades",
            Self::QuoteFallback => "quote_fallback",
        }
    }
}

/// Operator-visible bar build status.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BarBuildStatus {
    Accepted,
    Degraded,
    Rejected,
}

impl BarBuildStatus {
    /// Stable identifier for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::Degraded => "degraded",
            Self::Rejected => "rejected",
        }
    }
}

/// Read-only session slice view produced by the compiled session topology.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionTopologyView {
    pub session_id: String,
    pub trade_date: String,
    pub state: SessionState,
    pub tradeable: bool,
    pub matched_slice_id: String,
    pub reason_code: String,
    pub event_window_label: String,
}

/// One raw market-data event admitted for normalization.
#[derive(Clone, Debug, PartialEq)]
pub struct MarketDataEvent {
    pub event_id: String,
    pub symbol: String,
    pub kind: MarketDataEventKind,
    pub event_time_utc: String,
    pub price: Option<f64>,
    pub size: Option<u64>,
    pub bid: Option<f64>,
    pub ask: Option<f64>,
    pub quote_age_ms: u64,
    pub corrected: bool,
    pub late_print: bool,
}

/// Reference bar used for parity/degradation instrumentation.
#[derive(Clone, Debug, PartialEq)]
pub struct BarParityReference {
    pub reference_id: String,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: u64,
    pub availability_delay_ms: u64,
    pub event_window_label: String,
    pub price_tolerance: f64,
    pub volume_tolerance: u64,
    pub availability_tolerance_ms: u64,
}

/// Full request consumed by the live bar builder.
#[derive(Clone, Debug, PartialEq)]
pub struct LiveBarBuildRequest {
    pub request_id: String,
    pub symbol: String,
    pub data_profile_release_id: String,
    pub approved_bar_construction_semantics_id: String,
    pub entitlement_check_id: String,
    pub entitlement: MarketDataEntitlement,
    pub session: SessionTopologyView,
    pub bar_start_utc: String,
    pub bar_end_utc: String,
    pub zero_volume_bar_policy: String,
    pub trade_quote_precedence_rule: String,
    pub gap_policy: String,
    pub bar_close_to_publish_ms: u64,
    pub max_bar_close_to_publish_ms: u64,
    pub max_quote_staleness_ms: u64,
    pub stale_quote_restrict_bps: u32,
    pub parity_reference: Option<BarParityReference>,
    pub updates: Vec<MarketDataEvent>,
}

/// Built bar retained for diagnostics and downstream runtime use.
#[derive(Clone, Debug, PartialEq)]
pub struct LiveBar {
    pub bar_id: String,
    pub symbol: String,
    pub session_id: String,
    pub bar_start_utc: String,
    pub bar_end_utc: String,
    pub source: BarSource,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: u64,
    pub zero_volume_flag: bool,
    pub event_window_label: String,
}

/// Operator-facing result from one bar build attempt.
#[derive(Clone, Debug, PartialEq)]
pub struct LiveBarBuildReport {
    pub request_id: String,
    pub status: BarBuildStatus,
    pub reason_code: String,
    pub retained_artifact_id: String,
    pub market_data_fresh: bool,
    pub stale_quote_rate_bps: u32,
    pub parity_healthy: bool,
    pub normalized_update_count: usize,
    pub rejected_update_ids: Vec<String>,
    pub degraded_reason_codes: Vec<String>,
    pub bar: Option<LiveBar>,
    pub explanation: String,
}

#[derive(Clone, Debug, PartialEq)]
struct NormalizedTrade {
    price: f64,
    size: u64,
}

#[derive(Clone, Debug, PartialEq)]
struct NormalizedQuote {
    midpoint: f64,
    stale: bool,
}

fn render_request(request: &LiveBarBuildRequest) -> String {
    let mut lines = vec![
        format!("request_id={}", request.request_id),
        format!("symbol={}", request.symbol),
        format!(
            "data_profile_release_id={}",
            request.data_profile_release_id
        ),
        format!(
            "approved_bar_construction_semantics_id={}",
            request.approved_bar_construction_semantics_id
        ),
        format!("entitlement_check_id={}", request.entitlement_check_id),
        format!("entitlement={}", request.entitlement.as_str()),
        format!("session_id={}", request.session.session_id),
        format!("session_state={}", request.session.state.as_str()),
        format!("session_tradeable={}", request.session.tradeable),
        format!("session_reason_code={}", request.session.reason_code),
        format!("event_window_label={}", request.session.event_window_label),
        format!("bar_start_utc={}", request.bar_start_utc),
        format!("bar_end_utc={}", request.bar_end_utc),
        format!("zero_volume_bar_policy={}", request.zero_volume_bar_policy),
        format!(
            "trade_quote_precedence_rule={}",
            request.trade_quote_precedence_rule
        ),
        format!("gap_policy={}", request.gap_policy),
        format!(
            "bar_close_to_publish_ms={}",
            request.bar_close_to_publish_ms
        ),
        format!(
            "max_bar_close_to_publish_ms={}",
            request.max_bar_close_to_publish_ms
        ),
        format!("max_quote_staleness_ms={}", request.max_quote_staleness_ms),
        format!(
            "stale_quote_restrict_bps={}",
            request.stale_quote_restrict_bps
        ),
    ];
    if let Some(reference) = request.parity_reference.as_ref() {
        lines.push(format!("parity_reference_id={}", reference.reference_id));
        lines.push(format!(
            "parity_event_window_label={}",
            reference.event_window_label
        ));
    }
    for (index, update) in request.updates.iter().enumerate() {
        lines.push(format!("update[{index}].event_id={}", update.event_id));
        lines.push(format!("update[{index}].kind={}", update.kind.as_str()));
        lines.push(format!("update[{index}].symbol={}", update.symbol));
        lines.push(format!(
            "update[{index}].quote_age_ms={}",
            update.quote_age_ms
        ));
        lines.push(format!("update[{index}].corrected={}", update.corrected));
        lines.push(format!("update[{index}].late_print={}", update.late_print));
    }
    lines.join("\n")
}

fn render_bar(bar: &LiveBar) -> String {
    [
        format!("bar_id={}", bar.bar_id),
        format!("symbol={}", bar.symbol),
        format!("session_id={}", bar.session_id),
        format!("bar_start_utc={}", bar.bar_start_utc),
        format!("bar_end_utc={}", bar.bar_end_utc),
        format!("source={}", bar.source.as_str()),
        format!("open={}", bar.open),
        format!("high={}", bar.high),
        format!("low={}", bar.low),
        format!("close={}", bar.close),
        format!("volume={}", bar.volume),
        format!("zero_volume_flag={}", bar.zero_volume_flag),
        format!("event_window_label={}", bar.event_window_label),
    ]
    .join("\n")
}

fn render_report(report: &LiveBarBuildReport) -> String {
    let mut lines = vec![
        format!("request_id={}", report.request_id),
        format!("status={}", report.status.as_str()),
        format!("reason_code={}", report.reason_code),
        format!("retained_artifact_id={}", report.retained_artifact_id),
        format!("market_data_fresh={}", report.market_data_fresh),
        format!("stale_quote_rate_bps={}", report.stale_quote_rate_bps),
        format!("parity_healthy={}", report.parity_healthy),
        format!("normalized_update_count={}", report.normalized_update_count),
        format!(
            "rejected_update_ids={}",
            report.rejected_update_ids.join(",")
        ),
        format!(
            "degraded_reason_codes={}",
            report.degraded_reason_codes.join(",")
        ),
        format!("explanation={}", report.explanation),
    ];
    if let Some(bar) = report.bar.as_ref() {
        lines.push(render_bar(bar));
    }
    lines.join("\n")
}

fn reject_report(
    request: &LiveBarBuildRequest,
    reason_code: &str,
    rejected_update_ids: Vec<String>,
    explanation: &str,
) -> LiveBarBuildReport {
    LiveBarBuildReport {
        request_id: request.request_id.clone(),
        status: BarBuildStatus::Rejected,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!("runtime_state/live_bars/{}", request.request_id),
        market_data_fresh: false,
        stale_quote_rate_bps: 0,
        parity_healthy: false,
        normalized_update_count: 0,
        rejected_update_ids,
        degraded_reason_codes: Vec::new(),
        bar: None,
        explanation: explanation.to_string(),
    }
}

fn normalize_updates(
    request: &LiveBarBuildRequest,
) -> Result<(Vec<NormalizedTrade>, Vec<NormalizedQuote>, Vec<String>), LiveBarBuildReport> {
    let mut trades = Vec::new();
    let mut quotes = Vec::new();
    let mut rejected_update_ids = Vec::new();

    for update in &request.updates {
        if update.symbol != request.symbol {
            rejected_update_ids.push(update.event_id.clone());
            continue;
        }
        if update.corrected || update.late_print {
            rejected_update_ids.push(update.event_id.clone());
            continue;
        }
        match update.kind {
            MarketDataEventKind::Trade => {
                let Some(price) = update.price else {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                };
                let Some(size) = update.size else {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                };
                if price <= 0.0 || size == 0 {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                }
                trades.push(NormalizedTrade { price, size });
            }
            MarketDataEventKind::Quote => {
                let Some(bid) = update.bid else {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                };
                let Some(ask) = update.ask else {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                };
                if bid <= 0.0 || ask <= 0.0 || bid > ask {
                    rejected_update_ids.push(update.event_id.clone());
                    continue;
                }
                quotes.push(NormalizedQuote {
                    midpoint: (bid + ask) / 2.0,
                    stale: update.quote_age_ms > request.max_quote_staleness_ms,
                });
            }
        }
    }

    if trades.is_empty() && quotes.is_empty() {
        return Err(reject_report(
            request,
            "BAR_BUILDER_NO_USABLE_UPDATES",
            rejected_update_ids,
            "The bar builder rejected every update under the approved normalization and correction policy.",
        ));
    }

    Ok((trades, quotes, rejected_update_ids))
}

fn build_bar_from_trades(request: &LiveBarBuildRequest, trades: &[NormalizedTrade]) -> LiveBar {
    let open = trades
        .first()
        .expect("trade-based bar requires at least one trade")
        .price;
    let close = trades
        .last()
        .expect("trade-based bar requires at least one trade")
        .price;
    let high = trades.iter().map(|trade| trade.price).fold(open, f64::max);
    let low = trades.iter().map(|trade| trade.price).fold(open, f64::min);
    let volume = trades.iter().map(|trade| trade.size).sum();

    LiveBar {
        bar_id: format!("{}:bar", request.request_id),
        symbol: request.symbol.clone(),
        session_id: request.session.session_id.clone(),
        bar_start_utc: request.bar_start_utc.clone(),
        bar_end_utc: request.bar_end_utc.clone(),
        source: BarSource::Trades,
        open,
        high,
        low,
        close,
        volume,
        zero_volume_flag: false,
        event_window_label: request.session.event_window_label.clone(),
    }
}

fn build_bar_from_quotes(request: &LiveBarBuildRequest, quotes: &[NormalizedQuote]) -> LiveBar {
    let open = quotes
        .first()
        .expect("quote-based bar requires at least one quote")
        .midpoint;
    let close = quotes
        .last()
        .expect("quote-based bar requires at least one quote")
        .midpoint;
    let high = quotes
        .iter()
        .map(|quote| quote.midpoint)
        .fold(open, f64::max);
    let low = quotes
        .iter()
        .map(|quote| quote.midpoint)
        .fold(open, f64::min);

    LiveBar {
        bar_id: format!("{}:bar", request.request_id),
        symbol: request.symbol.clone(),
        session_id: request.session.session_id.clone(),
        bar_start_utc: request.bar_start_utc.clone(),
        bar_end_utc: request.bar_end_utc.clone(),
        source: BarSource::QuoteFallback,
        open,
        high,
        low,
        close,
        volume: 0,
        zero_volume_flag: true,
        event_window_label: request.session.event_window_label.clone(),
    }
}

fn parity_reason_codes(bar: &LiveBar, request: &LiveBarBuildRequest) -> Vec<String> {
    let Some(reference) = request.parity_reference.as_ref() else {
        return Vec::new();
    };

    let mut reasons = Vec::new();
    if (bar.open - reference.open).abs() > reference.price_tolerance
        || (bar.high - reference.high).abs() > reference.price_tolerance
        || (bar.low - reference.low).abs() > reference.price_tolerance
        || (bar.close - reference.close).abs() > reference.price_tolerance
    {
        reasons.push("BAR_BUILDER_PARITY_OHLC_DRIFT".to_string());
    }
    if bar.volume.abs_diff(reference.volume) > reference.volume_tolerance {
        reasons.push("BAR_BUILDER_PARITY_VOLUME_DRIFT".to_string());
    }
    if request
        .bar_close_to_publish_ms
        .abs_diff(reference.availability_delay_ms)
        > reference.availability_tolerance_ms
    {
        reasons.push("BAR_BUILDER_PARITY_AVAILABILITY_DRIFT".to_string());
    }
    if bar.event_window_label != reference.event_window_label {
        reasons.push("BAR_BUILDER_PARITY_EVENT_WINDOW_LABEL_DRIFT".to_string());
    }
    reasons
}

/// Builds one live bar from approved market-data inputs and runtime context.
pub fn build_live_bar(request: &LiveBarBuildRequest) -> LiveBarBuildReport {
    if request.entitlement != MarketDataEntitlement::LiveTopOfBook {
        return reject_report(
            request,
            "BAR_BUILDER_ENTITLEMENT_REQUIRED",
            Vec::new(),
            "The approved live bar lane requires live top-of-book entitlement before runtime bars may be emitted.",
        );
    }
    if !request.session.tradeable || request.session.state != SessionState::Tradeable {
        return reject_report(
            request,
            "BAR_BUILDER_SESSION_NOT_TRADEABLE",
            Vec::new(),
            "The compiled session topology marked this slice as non-tradeable, so the bar builder refused to emit a live decision bar.",
        );
    }

    let (trades, quotes, rejected_update_ids) = match normalize_updates(request) {
        Ok(result) => result,
        Err(report) => return report,
    };

    let bar = if !trades.is_empty() {
        build_bar_from_trades(request, &trades)
    } else if request.trade_quote_precedence_rule == "trade_first_then_quote_fallback"
        && request.zero_volume_bar_policy == "emit_with_explicit_zero_volume_flag"
    {
        build_bar_from_quotes(request, &quotes)
    } else {
        return reject_report(
            request,
            "BAR_BUILDER_QUOTE_FALLBACK_NOT_APPROVED",
            rejected_update_ids,
            "The request needed quote fallback, but the approved bar-construction semantics did not allow it.",
        );
    };

    let quote_count = quotes.len() as u32;
    let stale_quote_count = quotes.iter().filter(|quote| quote.stale).count() as u32;
    let stale_quote_rate_bps = if quote_count == 0 {
        0
    } else {
        stale_quote_count.saturating_mul(10_000) / quote_count
    };
    let market_data_fresh = request.bar_close_to_publish_ms <= request.max_bar_close_to_publish_ms;

    let mut degraded_reason_codes = Vec::new();
    if !market_data_fresh {
        degraded_reason_codes.push("BAR_BUILDER_FRESHNESS_LAGGING".to_string());
    }
    if stale_quote_rate_bps > request.stale_quote_restrict_bps {
        degraded_reason_codes.push("BAR_BUILDER_STALE_QUOTE_RATE_RESTRICTED".to_string());
    }

    let parity_reasons = parity_reason_codes(&bar, request);
    let parity_healthy = parity_reasons.is_empty();
    degraded_reason_codes.extend(parity_reasons);

    let status = if degraded_reason_codes.is_empty() {
        BarBuildStatus::Accepted
    } else {
        BarBuildStatus::Degraded
    };
    let reason_code = match status {
        BarBuildStatus::Accepted => "BAR_BUILDER_ACCEPTED",
        BarBuildStatus::Degraded => "BAR_BUILDER_DEGRADED",
        BarBuildStatus::Rejected => "BAR_BUILDER_REJECTED",
    };
    let explanation = match status {
        BarBuildStatus::Accepted => {
            "The live bar builder emitted a tradeable bar under approved entitlement, normalization, freshness, and parity conditions."
                .to_string()
        }
        BarBuildStatus::Degraded => format!(
            "The live bar builder emitted a degraded bar because {}.",
            degraded_reason_codes.join(", ")
        ),
        BarBuildStatus::Rejected => "The live bar builder rejected the request.".to_string(),
    };

    LiveBarBuildReport {
        request_id: request.request_id.clone(),
        status,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!("runtime_state/live_bars/{}", request.request_id),
        market_data_fresh,
        stale_quote_rate_bps,
        parity_healthy,
        normalized_update_count: trades.len() + quotes.len(),
        rejected_update_ids,
        degraded_reason_codes,
        bar: Some(bar),
        explanation,
    }
}

/// Writes the request, report, and emitted bar artifacts to the provided directory.
pub fn write_live_bar_artifacts(
    root: &Path,
    request: &LiveBarBuildRequest,
    report: &LiveBarBuildReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(root.join("live_bar_request.txt"), render_request(request))?;
    fs::write(root.join("live_bar_report.txt"), render_report(report))?;
    if let Some(bar) = report.bar.as_ref() {
        fs::write(root.join("live_bar.txt"), render_bar(bar))?;
    }
    Ok(())
}

fn base_request() -> LiveBarBuildRequest {
    LiveBarBuildRequest {
        request_id: "live-bar-request-001".to_string(),
        symbol: "1OZ".to_string(),
        data_profile_release_id: "ibkr_1oz_comex_bars_1m_v1".to_string(),
        approved_bar_construction_semantics_id: "gc_1m_bar_rules_v1".to_string(),
        entitlement_check_id: "entitlement_check_live_20260327".to_string(),
        entitlement: MarketDataEntitlement::LiveTopOfBook,
        session: SessionTopologyView {
            session_id: "globex_2026_03_18".to_string(),
            trade_date: "2026-03-18".to_string(),
            state: SessionState::Tradeable,
            tradeable: true,
            matched_slice_id: "compiled_schedule_gc:slice:001".to_string(),
            reason_code: "SESSION_OPEN_TRADEABLE".to_string(),
            event_window_label: "tradeable".to_string(),
        },
        bar_start_utc: "2026-03-18T14:30:00Z".to_string(),
        bar_end_utc: "2026-03-18T14:31:00Z".to_string(),
        zero_volume_bar_policy: "emit_with_explicit_zero_volume_flag".to_string(),
        trade_quote_precedence_rule: "trade_first_then_quote_fallback".to_string(),
        gap_policy: "no_forward_fill_inside_tradeable_slice".to_string(),
        bar_close_to_publish_ms: 420,
        max_bar_close_to_publish_ms: 1_000,
        max_quote_staleness_ms: 500,
        stale_quote_restrict_bps: 50,
        parity_reference: Some(BarParityReference {
            reference_id: "parity_reference_gc_20260318_1430".to_string(),
            open: 2360.75,
            high: 2361.50,
            low: 2360.75,
            close: 2361.25,
            volume: 12,
            availability_delay_ms: 400,
            event_window_label: "tradeable".to_string(),
            price_tolerance: 0.25,
            volume_tolerance: 1,
            availability_tolerance_ms: 150,
        }),
        updates: vec![
            MarketDataEvent {
                event_id: "trade-001".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Trade,
                event_time_utc: "2026-03-18T14:30:12Z".to_string(),
                price: Some(2360.75),
                size: Some(3),
                bid: None,
                ask: None,
                quote_age_ms: 0,
                corrected: false,
                late_print: false,
            },
            MarketDataEvent {
                event_id: "quote-001".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Quote,
                event_time_utc: "2026-03-18T14:30:20Z".to_string(),
                price: None,
                size: None,
                bid: Some(2360.50),
                ask: Some(2361.00),
                quote_age_ms: 120,
                corrected: false,
                late_print: false,
            },
            MarketDataEvent {
                event_id: "trade-002".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Trade,
                event_time_utc: "2026-03-18T14:30:41Z".to_string(),
                price: Some(2361.50),
                size: Some(4),
                bid: None,
                ask: None,
                quote_age_ms: 0,
                corrected: false,
                late_print: false,
            },
            MarketDataEvent {
                event_id: "trade-003".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Trade,
                event_time_utc: "2026-03-18T14:30:57Z".to_string(),
                price: Some(2361.25),
                size: Some(5),
                bid: None,
                ask: None,
                quote_age_ms: 0,
                corrected: false,
                late_print: false,
            },
            MarketDataEvent {
                event_id: "trade-corrected-004".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Trade,
                event_time_utc: "2026-03-18T14:30:58Z".to_string(),
                price: Some(2361.10),
                size: Some(1),
                bid: None,
                ask: None,
                quote_age_ms: 0,
                corrected: true,
                late_print: false,
            },
        ],
    }
}

/// Built-in live-bar scenarios used by tests and smoke drills.
pub fn sample_live_bar_request(name: &str) -> Option<LiveBarBuildRequest> {
    let mut request = base_request();
    match name {
        "tradeable-pass" => Some(request),
        "reset-boundary-reject" => {
            request.request_id = "live-bar-request-reset-boundary".to_string();
            request.session.state = SessionState::ResetBoundary;
            request.session.tradeable = false;
            request.session.reason_code = "SESSION_RESET_RECONNECT_WINDOW".to_string();
            request.session.event_window_label = "reset_boundary".to_string();
            if let Some(reference) = request.parity_reference.as_mut() {
                reference.event_window_label = "reset_boundary".to_string();
            }
            Some(request)
        }
        "delayed-entitlement-reject" => {
            request.request_id = "live-bar-request-delayed-entitlement".to_string();
            request.entitlement = MarketDataEntitlement::DelayedTopOfBook;
            Some(request)
        }
        "quote-fallback-zero-volume" => {
            request.request_id = "live-bar-request-quote-fallback".to_string();
            request.updates = vec![
                MarketDataEvent {
                    event_id: "quote-only-001".to_string(),
                    symbol: "1OZ".to_string(),
                    kind: MarketDataEventKind::Quote,
                    event_time_utc: "2026-03-18T14:30:15Z".to_string(),
                    price: None,
                    size: None,
                    bid: Some(2360.25),
                    ask: Some(2360.75),
                    quote_age_ms: 140,
                    corrected: false,
                    late_print: false,
                },
                MarketDataEvent {
                    event_id: "quote-only-002".to_string(),
                    symbol: "1OZ".to_string(),
                    kind: MarketDataEventKind::Quote,
                    event_time_utc: "2026-03-18T14:30:48Z".to_string(),
                    price: None,
                    size: None,
                    bid: Some(2360.50),
                    ask: Some(2361.00),
                    quote_age_ms: 160,
                    corrected: false,
                    late_print: false,
                },
            ];
            if let Some(reference) = request.parity_reference.as_mut() {
                reference.open = 2360.50;
                reference.high = 2360.75;
                reference.low = 2360.50;
                reference.close = 2360.75;
                reference.volume = 0;
            }
            Some(request)
        }
        "parity-degraded" => {
            request.request_id = "live-bar-request-parity-degraded".to_string();
            request.bar_close_to_publish_ms = 1_550;
            request.updates.push(MarketDataEvent {
                event_id: "quote-stale-002".to_string(),
                symbol: "1OZ".to_string(),
                kind: MarketDataEventKind::Quote,
                event_time_utc: "2026-03-18T14:30:59Z".to_string(),
                price: None,
                size: None,
                bid: Some(2361.00),
                ask: Some(2362.00),
                quote_age_ms: 900,
                corrected: false,
                late_print: false,
            });
            if let Some(reference) = request.parity_reference.as_mut() {
                reference.close = 2359.00;
                reference.high = 2360.00;
                reference.availability_delay_ms = 250;
            }
            Some(request)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{BarBuildStatus, BarSource, SessionState, build_live_bar, sample_live_bar_request};

    #[test]
    fn tradeable_bar_build_passes_with_trade_precedence() {
        let request = sample_live_bar_request("tradeable-pass").expect("pass scenario exists");
        let report = build_live_bar(&request);
        let bar = report.bar.as_ref().expect("accepted bar exists");

        assert_eq!(BarBuildStatus::Accepted, report.status);
        assert_eq!("BAR_BUILDER_ACCEPTED", report.reason_code);
        assert_eq!(BarSource::Trades, bar.source);
        assert_eq!(2360.75, bar.open);
        assert_eq!(2361.50, bar.high);
        assert_eq!(2360.75, bar.low);
        assert_eq!(2361.25, bar.close);
        assert_eq!(12, bar.volume);
        assert_eq!(
            vec!["trade-corrected-004".to_string()],
            report.rejected_update_ids
        );
    }

    #[test]
    fn session_boundary_rejects_non_tradeable_bar() {
        let request =
            sample_live_bar_request("reset-boundary-reject").expect("reset scenario exists");
        let report = build_live_bar(&request);

        assert_eq!(SessionState::ResetBoundary, request.session.state);
        assert_eq!(BarBuildStatus::Rejected, report.status);
        assert_eq!("BAR_BUILDER_SESSION_NOT_TRADEABLE", report.reason_code);
        assert!(report.bar.is_none());
    }

    #[test]
    fn delayed_entitlement_rejects_live_bar_build() {
        let request = sample_live_bar_request("delayed-entitlement-reject")
            .expect("delayed entitlement scenario exists");
        let report = build_live_bar(&request);

        assert_eq!(BarBuildStatus::Rejected, report.status);
        assert_eq!("BAR_BUILDER_ENTITLEMENT_REQUIRED", report.reason_code);
        assert!(report.bar.is_none());
    }

    #[test]
    fn quote_fallback_emits_zero_volume_bar_when_policy_allows() {
        let request = sample_live_bar_request("quote-fallback-zero-volume")
            .expect("quote fallback scenario exists");
        let report = build_live_bar(&request);
        let bar = report.bar.as_ref().expect("quote fallback bar exists");

        assert_eq!(BarBuildStatus::Accepted, report.status);
        assert_eq!(BarSource::QuoteFallback, bar.source);
        assert_eq!(0, bar.volume);
        assert!(bar.zero_volume_flag);
    }

    #[test]
    fn parity_drift_and_stale_quotes_degrade_bar() {
        let request = sample_live_bar_request("parity-degraded").expect("degraded scenario exists");
        let report = build_live_bar(&request);

        assert_eq!(BarBuildStatus::Degraded, report.status);
        assert_eq!("BAR_BUILDER_DEGRADED", report.reason_code);
        assert!(!report.market_data_fresh);
        assert!(!report.parity_healthy);
        assert!(
            report
                .degraded_reason_codes
                .contains(&"BAR_BUILDER_FRESHNESS_LAGGING".to_string())
        );
        assert!(
            report
                .degraded_reason_codes
                .contains(&"BAR_BUILDER_PARITY_OHLC_DRIFT".to_string())
        );
    }
}
