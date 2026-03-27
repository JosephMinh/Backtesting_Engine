#![allow(unused_crate_dependencies)]
#![allow(dead_code)]
#![allow(clippy::filter_map_bool_then)]
#![allow(clippy::manual_checked_ops)]
#![allow(clippy::manual_div_ceil)]
#![allow(clippy::result_large_err)]
#![allow(clippy::type_complexity)]

#[path = "../bar_builder.rs"]
mod bar_builder;
#[path = "../risk.rs"]
mod risk;
#[path = "../route_mode.rs"]
mod route_mode;

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use backtesting_engine_kernels::{
    BarInput, GoldMomentumKernel, KernelArtifactBinding, SignalDecision, SignalDisposition,
};
use backtesting_engine_opsd::{
    AuthoritativeStatementSet, BrokerCallback, BrokerCallbackKind, BrokerContractDescriptor,
    BrokerOrderIntentRequest, BrokerOrderType, BrokerTimeInForce, CompiledSessionState,
    DailyLedgerCloseRequest, DeliveryFenceWindowDefinition, IntradayReconciliationRequest,
    LedgerEventClass, LedgerEventRequest, MaintenanceWindowDefinition,
    OperationalEvidenceArtifactClass, OperationalEvidenceArtifactInput, OperationalEvidenceQuery,
    OperationalEvidenceSealRequest, OpsdRuntime, OrderIntentIdentity,
    PolicyOverlayWindowDefinition, ReadinessProviderKind, ScheduleCompileRequest,
    SessionCalendarEntry, SessionCloseRequest, SessionDayKind, SessionReadinessPacketRequest,
    SessionReadinessStatus,
};
use bar_builder::{build_live_bar, sample_live_bar_request, write_live_bar_artifacts};
use risk::{evaluate_runtime_risk, sample_runtime_risk_request, write_runtime_risk_artifacts};
use route_mode::{evaluate_route_mode, sample_route_mode_request, write_route_mode_artifacts};

const PASS_SCENARIO: &str = "paper-shadow-e2e-pass";
const BLOCKED_SCENARIO: &str = "broker-state-blocked-before-routing";

struct DummyStrategySmokeReport {
    scenario: String,
    artifact_dir: PathBuf,
    final_status: String,
    final_reason_code: String,
    kernel_disposition: String,
    kernel_score_ticks: i64,
    kernel_identity_digest: String,
    tradeable_state: String,
    tradeable_reason_code: String,
    reset_state: String,
    reset_reason_code: String,
    session_reset_observed: bool,
    broker_reconnect_observed: bool,
    readiness_status: String,
    readiness_reason_code: String,
    readiness_packet_id: String,
    risk_status: String,
    risk_reason_code: String,
    paper_route_outcome: String,
    paper_route_reason_code: String,
    paper_broker_artifact_count: usize,
    paper_callback_count: usize,
    paper_order_intent_id: String,
    intraday_status: String,
    intraday_reason_code: String,
    session_close_status: String,
    session_close_reason_code: String,
    daily_close_status: String,
    daily_close_reason_code: String,
    next_session_eligibility: String,
    shadow_route_outcome: String,
    shadow_route_reason_code: String,
    shadow_broker_artifact_delta: usize,
    operational_evidence_manifest_id: String,
    operational_evidence_record_count: usize,
    correlation_id: String,
    reason_bundle_id: String,
    correlated_log: Vec<String>,
    reason_bundle: Vec<String>,
    kernel_binding_summary: String,
    broker_reconnect_summary: String,
    reconciliation_summary: String,
}

impl DummyStrategySmokeReport {
    fn render_lines(&self) -> Vec<String> {
        vec![
            format!("scenario={}", self.scenario),
            format!("artifact_dir={}", self.artifact_dir.display()),
            format!("final_status={}", self.final_status),
            format!("final_reason_code={}", self.final_reason_code),
            format!("kernel_disposition={}", self.kernel_disposition),
            format!("kernel_score_ticks={}", self.kernel_score_ticks),
            format!("kernel_identity_digest={}", self.kernel_identity_digest),
            format!("tradeable_state={}", self.tradeable_state),
            format!("tradeable_reason_code={}", self.tradeable_reason_code),
            format!("reset_state={}", self.reset_state),
            format!("reset_reason_code={}", self.reset_reason_code),
            format!("session_reset_observed={}", self.session_reset_observed),
            format!(
                "broker_reconnect_observed={}",
                self.broker_reconnect_observed
            ),
            format!("readiness_status={}", self.readiness_status),
            format!("readiness_reason_code={}", self.readiness_reason_code),
            format!("readiness_packet_id={}", self.readiness_packet_id),
            format!("risk_status={}", self.risk_status),
            format!("risk_reason_code={}", self.risk_reason_code),
            format!("paper_route_outcome={}", self.paper_route_outcome),
            format!("paper_route_reason_code={}", self.paper_route_reason_code),
            format!(
                "paper_broker_artifact_count={}",
                self.paper_broker_artifact_count
            ),
            format!("paper_callback_count={}", self.paper_callback_count),
            format!("paper_order_intent_id={}", self.paper_order_intent_id),
            format!("intraday_status={}", self.intraday_status),
            format!("intraday_reason_code={}", self.intraday_reason_code),
            format!("session_close_status={}", self.session_close_status),
            format!(
                "session_close_reason_code={}",
                self.session_close_reason_code
            ),
            format!("daily_close_status={}", self.daily_close_status),
            format!("daily_close_reason_code={}", self.daily_close_reason_code),
            format!("next_session_eligibility={}", self.next_session_eligibility),
            format!("shadow_route_outcome={}", self.shadow_route_outcome),
            format!("shadow_route_reason_code={}", self.shadow_route_reason_code),
            format!(
                "shadow_broker_artifact_delta={}",
                self.shadow_broker_artifact_delta
            ),
            format!(
                "operational_evidence_manifest_id={}",
                self.operational_evidence_manifest_id
            ),
            format!(
                "operational_evidence_record_count={}",
                self.operational_evidence_record_count
            ),
            format!("correlation_id={}", self.correlation_id),
            format!("reason_bundle_id={}", self.reason_bundle_id),
        ]
    }
}

fn usage() -> &'static str {
    "usage: dummy_strategy_smoke --scenario <paper-shadow-e2e-pass|broker-state-blocked-before-routing> --artifact-dir <dir>"
}

fn parse_flag<'a>(args: &'a [String], flag: &str) -> Result<&'a str, String> {
    let Some(flag_index) = args.iter().position(|arg| arg == flag) else {
        return Err(format!("missing {flag}"));
    };
    let Some(value) = args.get(flag_index + 1) else {
        return Err(format!("missing value for {flag}"));
    };
    Ok(value.as_str())
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
                "winter-2026-02-18",
                "globex_2026_02_18",
                "2026-02-18",
                "comex_metals_globex_v1",
                "2026-02-17T23:00:00Z",
                "2026-02-18T22:00:00Z",
                SessionDayKind::Regular,
                -360,
                "17:00 CT",
                "16:00 CT",
            ),
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

fn sync_readiness_provider(
    request: &mut SessionReadinessPacketRequest,
    provider_kind: ReadinessProviderKind,
    reason_code: &str,
    summary: &str,
    source_artifact_id: &str,
) -> Result<(), String> {
    let Some(provider) = request
        .providers
        .iter_mut()
        .find(|provider| provider.provider_kind == provider_kind)
    else {
        return Err(format!(
            "missing readiness provider for {}",
            provider_kind.as_str()
        ));
    };
    provider.reason_code = reason_code.to_string();
    provider.summary = summary.to_string();
    provider.source_artifact_id = source_artifact_id.to_string();
    provider.component_digest = format!("{}::{source_artifact_id}", provider.provider_id);
    Ok(())
}

fn route_readiness_state(status: SessionReadinessStatus) -> route_mode::ReadinessState {
    match status {
        SessionReadinessStatus::Green => route_mode::ReadinessState::Green,
        SessionReadinessStatus::Suspect => route_mode::ReadinessState::Suspect,
        SessionReadinessStatus::Blocked | SessionReadinessStatus::Invalid => {
            route_mode::ReadinessState::Blocked
        }
    }
}

fn evaluate_dummy_kernel(
    current_close: f64,
) -> Result<(KernelArtifactBinding, SignalDecision), String> {
    let current_ticks = (current_close * 10.0).round() as i64;
    let binding = GoldMomentumKernel::binding(
        "candidate_bundles/dummy_strategy_bundle_v1.json",
        "resolved_context_bundles/dummy_strategy_context_v1.json",
        "signal_kernels/gold_momentum_kernel_v1.json",
    )
    .map_err(|error| format!("kernel binding failed: {error:?}"))?;
    let decisions = GoldMomentumKernel::evaluate_series(
        3,
        8,
        &[
            BarInput {
                sequence_number: 1,
                close_ticks: current_ticks - 12,
            },
            BarInput {
                sequence_number: 2,
                close_ticks: current_ticks - 8,
            },
            BarInput {
                sequence_number: 3,
                close_ticks: current_ticks - 4,
            },
            BarInput {
                sequence_number: 4,
                close_ticks: current_ticks,
            },
        ],
    );
    let Some(decision) = decisions.into_iter().last() else {
        return Err("kernel warmup did not emit a decision".to_string());
    };
    Ok((binding, decision))
}

fn write_dummy_strategy_artifacts(
    root: &Path,
    report: &DummyStrategySmokeReport,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("dummy_strategy_summary.txt"),
        report.render_lines().join("\n"),
    )?;
    fs::write(
        root.join("correlated_log.txt"),
        report.correlated_log.join("\n"),
    )?;
    fs::write(
        root.join("reason_bundle.txt"),
        report.reason_bundle.join("\n"),
    )?;
    fs::write(
        root.join("kernel_binding.txt"),
        &report.kernel_binding_summary,
    )?;
    fs::write(
        root.join("broker_reconnect_observation.txt"),
        &report.broker_reconnect_summary,
    )?;
    fs::write(
        root.join("reconciliation_summary.txt"),
        &report.reconciliation_summary,
    )?;
    Ok(())
}

fn run_paper_shadow_e2e_pass(artifact_dir: &Path) -> Result<DummyStrategySmokeReport, String> {
    let correlation_id = "corr-dummy-strategy-pass-001".to_string();
    let reason_bundle_id = "reason-bundle-dummy-strategy-pass-001".to_string();
    let deployment_instance_id = "deployment-dummy-strategy-001".to_string();
    let candidate_id = "candidate-gold-dummy-001".to_string();
    let mut correlated_log = Vec::new();
    let mut reason_bundle = Vec::new();
    let mut runtime = OpsdRuntime::boot();

    let schedule = runtime
        .compile_and_install_schedule(sample_schedule_request())
        .map_err(|error| format!("schedule compile/install failed: {error:?}"))?;
    correlated_log.push(format!(
        "step=schedule_install correlation_id={correlation_id} artifact_id={} retained_artifact_id={}",
        schedule.artifact_id, schedule.retained_artifact_id
    ));

    let tradeable = runtime
        .evaluate_session_topology("2026-03-18T15:00:00Z")
        .map_err(|error| format!("tradeable topology evaluation failed: {error:?}"))?;
    let reset = runtime
        .evaluate_session_topology("2026-03-17T22:02:00Z")
        .map_err(|error| format!("reset topology evaluation failed: {error:?}"))?;
    if tradeable.state != CompiledSessionState::Tradeable {
        return Err("expected tradeable session state for pass scenario".to_string());
    }
    if reset.state != CompiledSessionState::ResetBoundary {
        return Err("expected reset-boundary state for pass scenario".to_string());
    }

    let live_bar_request = sample_live_bar_request("tradeable-pass")
        .ok_or_else(|| "missing live-bar pass scenario".to_string())?;
    let live_bar_report = build_live_bar(&live_bar_request);
    write_live_bar_artifacts(
        &artifact_dir.join("live_bar"),
        &live_bar_request,
        &live_bar_report,
    )
    .map_err(|error| format!("failed to write live-bar artifacts: {error}"))?;
    let Some(bar) = live_bar_report.bar.as_ref() else {
        return Err("live-bar pass scenario did not emit a bar".to_string());
    };
    correlated_log.push(format!(
        "step=live_bar correlation_id={correlation_id} status={} reason_code={} retained_artifact_id={}",
        live_bar_report.status.as_str(),
        live_bar_report.reason_code,
        live_bar_report.retained_artifact_id
    ));

    let (kernel_binding, kernel_decision) = evaluate_dummy_kernel(bar.close)?;
    if kernel_decision.disposition != SignalDisposition::Long {
        return Err("dummy strategy kernel did not emit the expected long signal".to_string());
    }
    correlated_log.push(format!(
        "step=kernel_decision correlation_id={correlation_id} disposition={} score_ticks={} candidate_bundle={}",
        kernel_decision.disposition.as_str(),
        kernel_decision.score_ticks,
        kernel_binding.candidate_bundle.relative_path()
    ));

    let mut risk_request = sample_runtime_risk_request("green-tradeable-pass")
        .ok_or_else(|| "missing runtime-risk pass scenario".to_string())?;
    risk_request.request_id = "runtime-risk-dummy-strategy-pass".to_string();
    risk_request.session_id = tradeable
        .session_id
        .clone()
        .unwrap_or_else(|| "globex_2026_03_18".to_string());
    risk_request.proposed_order_increases_risk = true;
    let risk_report = evaluate_runtime_risk(&risk_request);
    write_runtime_risk_artifacts(
        &artifact_dir.join("runtime_risk"),
        &risk_request,
        &risk_report,
    )
    .map_err(|error| format!("failed to write runtime-risk artifacts: {error}"))?;
    correlated_log.push(format!(
        "step=runtime_risk correlation_id={correlation_id} status={} reason_code={} retained_artifact_id={}",
        risk_report.status.as_str(),
        risk_report.reason_code,
        risk_report.retained_artifact_id
    ));

    let mut readiness_request =
        backtesting_engine_opsd::sample_session_readiness_request("green-readiness-pass")
            .ok_or_else(|| "missing readiness pass scenario".to_string())?;
    readiness_request.packet_id = "session-readiness-dummy-pass".to_string();
    readiness_request.deployment_instance_id = deployment_instance_id.clone();
    readiness_request.session_id = tradeable
        .session_id
        .clone()
        .unwrap_or_else(|| "globex_2026_03_18".to_string());
    readiness_request.correlation_id = correlation_id.clone();
    readiness_request.operator_summary =
        "Issue the readiness packet for the dummy-strategy paper/shadow rehearsal.".to_string();
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::SessionEligibility,
        &tradeable.reason_code,
        "Compiled session topology is tradeable after the reset/reconnect window.",
        &schedule.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::RuntimeRisk,
        &risk_report.reason_code,
        "Runtime risk stays green for the dummy-strategy paper/shadow rehearsal.",
        &risk_report.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::Entitlement,
        &live_bar_report.reason_code,
        "Approved entitlement-aware live bar construction succeeded for the tradeable slice.",
        &live_bar_report.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::BrokerState,
        "BROKER_SESSION_RECONNECTED_CLEANLY",
        "Broker session reset and reconnect observation completed cleanly before paper submission.",
        "broker-session/ibkr-paper-reconnect-001",
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::ContractConformance,
        "KERNEL_BINDING_CANONICAL",
        "Dummy strategy is bound to the canonical kernel artifacts for this rehearsal lane.",
        kernel_binding.signal_kernel.relative_path(),
    )?;
    let readiness_packet = runtime.publish_session_readiness_packet(readiness_request.clone());
    backtesting_engine_opsd::write_session_readiness_artifacts(
        &artifact_dir.join("readiness"),
        &readiness_request,
        &readiness_packet,
    )
    .map_err(|error| format!("failed to write readiness artifacts: {error}"))?;
    correlated_log.push(format!(
        "step=readiness_packet correlation_id={correlation_id} packet_id={} status={} reason_code={} retained_artifact_id={}",
        readiness_packet.packet_id,
        readiness_packet.status.as_str(),
        readiness_packet.reason_code,
        readiness_packet.retained_artifact_id
    ));

    let order_intent_identity = OrderIntentIdentity::new(
        deployment_instance_id.clone(),
        kernel_decision.sequence_number,
        "leg-primary",
        "buy",
        "entry",
    );
    let order_intent_id = order_intent_identity.deterministic_id();

    let mut paper_route_request = sample_route_mode_request("paper-route-reroutes-submit")
        .ok_or_else(|| "missing paper-route scenario".to_string())?;
    paper_route_request.request_id = "route-mode-dummy-paper-pass".to_string();
    paper_route_request.correlation_id = correlation_id.clone();
    paper_route_request.deployment_instance_id = deployment_instance_id.clone();
    paper_route_request.session_id = tradeable
        .session_id
        .clone()
        .unwrap_or_else(|| "globex_2026_03_18".to_string());
    paper_route_request.order_intent_id = order_intent_id.clone();
    paper_route_request.readiness_state = route_readiness_state(readiness_packet.status);
    paper_route_request.risk_allows_new_risk = risk_report.allow_new_risk;
    paper_route_request.policy_input_ids = vec![
        kernel_binding.identity.canonical_digest(),
        schedule.retained_artifact_id.clone(),
    ];
    paper_route_request.source_artifact_ids = vec![
        live_bar_report.retained_artifact_id.clone(),
        risk_report.retained_artifact_id.clone(),
        readiness_packet.retained_artifact_id.clone(),
    ];
    let paper_route_report = evaluate_route_mode(&paper_route_request);
    write_route_mode_artifacts(
        &artifact_dir.join("paper_route"),
        &paper_route_request,
        &paper_route_report,
    )
    .map_err(|error| format!("failed to write paper-route artifacts: {error}"))?;
    correlated_log.push(format!(
        "step=paper_route correlation_id={correlation_id} outcome={} reason_code={} retained_artifact_id={}",
        paper_route_report.outcome.as_str(),
        paper_route_report.reason_code,
        paper_route_report.retained_artifact_id
    ));

    let paper_submit = runtime
        .submit_order_intent(BrokerOrderIntentRequest::new(
            correlation_id.clone(),
            "decision-trace-dummy-strategy-paper-pass",
            "expected-timeline-dummy-strategy-paper-pass",
            "actual-timeline-dummy-strategy-paper-pass",
            "artifact-manifest-dummy-strategy-paper-pass",
            reason_bundle_id.clone(),
            order_intent_identity,
            BrokerOrderType::Limit,
            BrokerTimeInForce::Day,
            BrokerContractDescriptor::one_oz_comex(),
        ))
        .map_err(|error| format!("paper submit failed: {error:?}"))?;
    let Some(broker_order_id) = paper_submit.broker_order_ids.first().cloned() else {
        return Err("paper submit did not emit a broker order id".to_string());
    };
    let ack_receipt = runtime
        .record_broker_callback(BrokerCallback::new(
            "ack-1",
            broker_order_id.clone(),
            BrokerCallbackKind::Acknowledged,
        ))
        .map_err(|error| format!("broker ack callback failed: {error:?}"))?;
    let fill_receipt = runtime
        .record_broker_callback(BrokerCallback::new(
            "fill-1",
            broker_order_id.clone(),
            BrokerCallbackKind::Fill,
        ))
        .map_err(|error| format!("broker fill callback failed: {error:?}"))?;
    correlated_log.push(format!(
        "step=paper_submit correlation_id={correlation_id} order_intent_id={} broker_order_id={} reason_code={}",
        paper_submit.order_intent_id, broker_order_id, paper_submit.reason_code
    ));
    correlated_log.push(format!(
        "step=broker_ack correlation_id={correlation_id} callback_id={} reason_code={}",
        ack_receipt.callback_id, ack_receipt.reason_code
    ));
    correlated_log.push(format!(
        "step=broker_fill correlation_id={correlation_id} callback_id={} reason_code={}",
        fill_receipt.callback_id, fill_receipt.reason_code
    ));

    runtime
        .append_ledger_event(LedgerEventRequest {
            event_class: LedgerEventClass::BookedFill,
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            occurred_at_utc: "2026-03-18T15:01:00Z".to_string(),
            description: "Booked one-contract dummy-strategy fill".to_string(),
            correlation_id: correlation_id.clone(),
            order_intent_id: Some(paper_submit.order_intent_id.clone()),
            broker_order_id: Some(broker_order_id.clone()),
            source_callback_id: Some(fill_receipt.callback_id.clone()),
            reference_event_id: None,
            discrepancy_id: None,
            position_delta_contracts: 1,
            cash_delta_usd_cents: -25_360,
            realized_pnl_delta_usd_cents: 0,
            fee_delta_usd_cents: 0,
            commission_delta_usd_cents: 0,
            authoritative_position_contracts: None,
            authoritative_initial_margin_requirement_usd_cents: None,
            authoritative_maintenance_margin_requirement_usd_cents: None,
            source_artifact_ids: vec![
                paper_submit.retained_artifact_id.clone(),
                live_bar_report.retained_artifact_id.clone(),
            ],
        })
        .map_err(|error| format!("failed to append booked fill: {error:?}"))?;
    runtime
        .append_ledger_event(LedgerEventRequest {
            event_class: LedgerEventClass::BookedCommission,
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            occurred_at_utc: "2026-03-18T15:01:01Z".to_string(),
            description: "Booked dummy-strategy commission".to_string(),
            correlation_id: correlation_id.clone(),
            order_intent_id: Some(paper_submit.order_intent_id.clone()),
            broker_order_id: Some(broker_order_id.clone()),
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
            source_artifact_ids: vec![paper_submit.retained_artifact_id.clone()],
        })
        .map_err(|error| format!("failed to append booked commission: {error:?}"))?;
    runtime
        .append_ledger_event(LedgerEventRequest {
            event_class: LedgerEventClass::BrokerEodPosition,
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            occurred_at_utc: "2026-03-18T22:10:00Z".to_string(),
            description: "Broker EOD position".to_string(),
            correlation_id: correlation_id.clone(),
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
            source_artifact_ids: vec!["broker-state/position-end-of-day.json".to_string()],
        })
        .map_err(|error| format!("failed to append broker EOD position: {error:?}"))?;
    runtime
        .append_ledger_event(LedgerEventRequest {
            event_class: LedgerEventClass::BrokerEodMarginSnapshot,
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            occurred_at_utc: "2026-03-18T22:10:01Z".to_string(),
            description: "Broker EOD margin".to_string(),
            correlation_id: correlation_id.clone(),
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
            authoritative_initial_margin_requirement_usd_cents: Some(95_000),
            authoritative_maintenance_margin_requirement_usd_cents: Some(70_000),
            source_artifact_ids: vec!["broker-state/margin-end-of-day.json".to_string()],
        })
        .map_err(|error| format!("failed to append broker EOD margin: {error:?}"))?;

    let intraday = runtime
        .evaluate_intraday_reconciliation(IntradayReconciliationRequest {
            reconciliation_id: "intraday-dummy-pass".to_string(),
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            evaluated_at_utc: "2026-03-18T18:00:00Z".to_string(),
            correlation_id: correlation_id.clone(),
            position_tolerance_contracts: 0,
            local_position_contracts: 1,
            broker_position_contracts: 1,
            local_working_order_ids: Vec::new(),
            broker_working_order_ids: Vec::new(),
            local_fill_ids: vec![fill_receipt.callback_id.clone()],
            broker_fill_ids: vec![fill_receipt.callback_id.clone()],
            local_trading_permission_state: "tradeable".to_string(),
            broker_trading_permission_state: "tradeable".to_string(),
            source_artifact_ids: vec![
                paper_submit.retained_artifact_id.clone(),
                readiness_packet.retained_artifact_id.clone(),
            ],
        })
        .map_err(|error| format!("intraday reconciliation failed: {error:?}"))?;
    let session_close = runtime
        .build_session_close_artifact(SessionCloseRequest {
            close_id: "close-dummy-pass".to_string(),
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            compiled_schedule_artifact_id: schedule.retained_artifact_id.clone(),
            close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
        })
        .map_err(|error| format!("session close failed: {error:?}"))?;
    let daily_close = runtime
        .build_authoritative_ledger_close(DailyLedgerCloseRequest {
            ledger_close_id: "daily-close-dummy-pass".to_string(),
            session_close_artifact_id: session_close.artifact_id.clone(),
            statement_set: AuthoritativeStatementSet {
                statement_set_id: "statement-set-dummy-pass".to_string(),
                account_id: "acct-1".to_string(),
                symbol: "1OZ".to_string(),
                session_id: "globex_2026_03_18".to_string(),
                ledger_close_date: "2026-03-18".to_string(),
                ingested_at_utc: "2026-03-18T22:20:00Z".to_string(),
                fill_execution_ids: vec![fill_receipt.callback_id.clone()],
                position_contracts: 1,
                cash_movement_total_usd_cents: -25_360,
                commission_total_usd_cents: 45,
                fee_total_usd_cents: 0,
                realized_pnl_usd_cents: 0,
                unrealized_pnl_usd_cents: 8_750,
                initial_margin_requirement_usd_cents: 95_000,
                maintenance_margin_requirement_usd_cents: 70_000,
                source_artifact_ids: vec![
                    "evidence/broker/dummy-pass-statement.csv".to_string(),
                    "evidence/broker/dummy-pass-statement.sha256".to_string(),
                ],
            },
            runtime_unrealized_pnl_usd_cents: Some(8_750),
            reviewed_or_waived: false,
            review_or_waiver_id: None,
            correlation_id: correlation_id.clone(),
            evaluated_at_utc: "2026-03-18T22:25:00Z".to_string(),
        })
        .map_err(|error| format!("daily close failed: {error:?}"))?;
    correlated_log.push(format!(
        "step=daily_close correlation_id={correlation_id} artifact_id={} status={} next_session_eligibility={}",
        daily_close.artifact_id,
        daily_close.status.as_str(),
        daily_close.next_session_eligibility.as_str()
    ));

    let shadow_artifacts_before = runtime.broker_artifacts().len();
    let mut shadow_route_request = sample_route_mode_request("shadow-live-suppresses-submit")
        .ok_or_else(|| "missing shadow-route scenario".to_string())?;
    shadow_route_request.request_id = "route-mode-dummy-shadow-pass".to_string();
    shadow_route_request.correlation_id = correlation_id.clone();
    shadow_route_request.deployment_instance_id = deployment_instance_id.clone();
    shadow_route_request.session_id = "globex_2026_03_18".to_string();
    shadow_route_request.order_intent_id = order_intent_id.clone();
    shadow_route_request.readiness_state = route_readiness_state(readiness_packet.status);
    shadow_route_request.risk_allows_new_risk = risk_report.allow_new_risk;
    shadow_route_request.policy_input_ids = vec![
        kernel_binding.identity.canonical_digest(),
        schedule.retained_artifact_id.clone(),
    ];
    shadow_route_request.source_artifact_ids = vec![
        daily_close.retained_artifact_id.clone(),
        readiness_packet.retained_artifact_id.clone(),
        risk_report.retained_artifact_id.clone(),
    ];
    let shadow_route_report = evaluate_route_mode(&shadow_route_request);
    write_route_mode_artifacts(
        &artifact_dir.join("shadow_route"),
        &shadow_route_request,
        &shadow_route_report,
    )
    .map_err(|error| format!("failed to write shadow-route artifacts: {error}"))?;
    let shadow_broker_artifact_delta = runtime
        .broker_artifacts()
        .len()
        .saturating_sub(shadow_artifacts_before);
    correlated_log.push(format!(
        "step=shadow_route correlation_id={correlation_id} outcome={} reason_code={} broker_artifact_delta={shadow_broker_artifact_delta}",
        shadow_route_report.outcome.as_str(),
        shadow_route_report.reason_code
    ));

    let seal_receipt = runtime
        .seal_operational_evidence(OperationalEvidenceSealRequest {
            archive_run_id: "archive-run-dummy-pass-001".to_string(),
            sealed_at_utc: "2026-03-18T22:30:00Z".to_string(),
            correlation_id: correlation_id.clone(),
            retention_class: "operational_evidence_archive".to_string(),
            operator_summary:
                "Seal the dummy-strategy paper/shadow rehearsal evidence bundle for review."
                    .to_string(),
            artifacts: vec![
                OperationalEvidenceArtifactInput {
                    source_artifact_id: paper_route_report.retained_artifact_id.clone(),
                    artifact_class: OperationalEvidenceArtifactClass::PaperPassEvidence,
                    candidate_id: Some(candidate_id.clone()),
                    deployment_id: Some(deployment_instance_id.clone()),
                    session_id: Some("globex_2026_03_18".to_string()),
                    drill_id: None,
                    summary: "Paper routing rehearsal completed with a retained non-economic broker mutation trail.".to_string(),
                    generated_at_utc: "2026-03-18T15:01:00Z".to_string(),
                },
                OperationalEvidenceArtifactInput {
                    source_artifact_id: shadow_route_report.retained_artifact_id.clone(),
                    artifact_class: OperationalEvidenceArtifactClass::ShadowLiveTrace,
                    candidate_id: Some(candidate_id.clone()),
                    deployment_id: Some(deployment_instance_id.clone()),
                    session_id: Some("globex_2026_03_18".to_string()),
                    drill_id: None,
                    summary:
                        "Shadow-live suppression trace proves the rehearsal emitted no economic mutation."
                            .to_string(),
                    generated_at_utc: "2026-03-18T22:26:00Z".to_string(),
                },
                OperationalEvidenceArtifactInput {
                    source_artifact_id: paper_submit.retained_artifact_id.clone(),
                    artifact_class: OperationalEvidenceArtifactClass::BrokerSessionRecording,
                    candidate_id: Some(candidate_id.clone()),
                    deployment_id: Some(deployment_instance_id.clone()),
                    session_id: Some("globex_2026_03_18".to_string()),
                    drill_id: None,
                    summary:
                        "Broker callback trail retained the reconnect-clean submission, acknowledgment, and fill mapping."
                            .to_string(),
                    generated_at_utc: "2026-03-18T15:01:02Z".to_string(),
                },
                OperationalEvidenceArtifactInput {
                    source_artifact_id: live_bar_report.retained_artifact_id.clone(),
                    artifact_class: OperationalEvidenceArtifactClass::ParityReport,
                    candidate_id: Some(candidate_id.clone()),
                    deployment_id: Some(deployment_instance_id.clone()),
                    session_id: Some("globex_2026_03_18".to_string()),
                    drill_id: None,
                    summary:
                        "Approved live-bar construction retained the parity and freshness instrumentation for this slice."
                            .to_string(),
                    generated_at_utc: "2026-03-18T15:00:00Z".to_string(),
                },
                OperationalEvidenceArtifactInput {
                    source_artifact_id: daily_close.retained_artifact_id.clone(),
                    artifact_class: OperationalEvidenceArtifactClass::PostSessionReview,
                    candidate_id: Some(candidate_id.clone()),
                    deployment_id: Some(deployment_instance_id.clone()),
                    session_id: Some("globex_2026_03_18".to_string()),
                    drill_id: None,
                    summary:
                        "Authoritative statement ingestion reconciled the dummy-strategy session and left the next session eligible."
                            .to_string(),
                    generated_at_utc: "2026-03-18T22:25:00Z".to_string(),
                },
            ],
        })
        .map_err(|error| format!("operational evidence seal failed: {error:?}"))?;
    let query_results = runtime.query_operational_evidence(&OperationalEvidenceQuery {
        candidate_id: Some(candidate_id.clone()),
        deployment_id: Some(deployment_instance_id.clone()),
        session_id: Some("globex_2026_03_18".to_string()),
        drill_id: None,
        artifact_class: None,
    });
    backtesting_engine_opsd::write_operational_evidence_archive_artifacts(
        &artifact_dir.join("archive"),
        &seal_receipt,
        &query_results,
    )
    .map_err(|error| format!("failed to write operational-evidence artifacts: {error}"))?;
    let health = runtime.health_report();
    reason_bundle.extend([
        format!(
            "Kernel {} emitted a {} decision with score {}.",
            kernel_binding.identity.strategy_family_id,
            kernel_decision.disposition.as_str(),
            kernel_decision.score_ticks
        ),
        format!(
            "Readiness packet {} stayed {} with {}.",
            readiness_packet.packet_id,
            readiness_packet.status.as_str(),
            readiness_packet.reason_code
        ),
        format!(
            "Paper route emitted {} and retained {}.",
            paper_route_report.reason_code, paper_submit.retained_artifact_id
        ),
        format!(
            "Shadow route emitted {} without increasing broker artifacts.",
            shadow_route_report.reason_code
        ),
        format!(
            "Authoritative statement ingestion ended {} with next-session eligibility {}.",
            daily_close.reason_code,
            daily_close.next_session_eligibility.as_str()
        ),
    ]);

    let report = DummyStrategySmokeReport {
        scenario: PASS_SCENARIO.to_string(),
        artifact_dir: artifact_dir.to_path_buf(),
        final_status: "pass".to_string(),
        final_reason_code: "DUMMY_STRATEGY_E2E_RECONCILED".to_string(),
        kernel_disposition: kernel_decision.disposition.as_str().to_string(),
        kernel_score_ticks: kernel_decision.score_ticks,
        kernel_identity_digest: kernel_binding.identity.canonical_digest(),
        tradeable_state: tradeable.state.as_str().to_string(),
        tradeable_reason_code: tradeable.reason_code,
        reset_state: reset.state.as_str().to_string(),
        reset_reason_code: reset.reason_code.clone(),
        session_reset_observed: true,
        broker_reconnect_observed: true,
        readiness_status: readiness_packet.status.as_str().to_string(),
        readiness_reason_code: readiness_packet.reason_code.clone(),
        readiness_packet_id: readiness_packet.packet_id.clone(),
        risk_status: risk_report.status.as_str().to_string(),
        risk_reason_code: risk_report.reason_code.clone(),
        paper_route_outcome: paper_route_report.outcome.as_str().to_string(),
        paper_route_reason_code: paper_route_report.reason_code.clone(),
        paper_broker_artifact_count: runtime.broker_artifacts().len(),
        paper_callback_count: runtime.broker_callback_log().len(),
        paper_order_intent_id: order_intent_id,
        intraday_status: intraday.status.as_str().to_string(),
        intraday_reason_code: intraday.reason_code.clone(),
        session_close_status: session_close.status.as_str().to_string(),
        session_close_reason_code: session_close.reason_code.clone(),
        daily_close_status: daily_close.status.as_str().to_string(),
        daily_close_reason_code: daily_close.reason_code.clone(),
        next_session_eligibility: daily_close.next_session_eligibility.as_str().to_string(),
        shadow_route_outcome: shadow_route_report.outcome.as_str().to_string(),
        shadow_route_reason_code: shadow_route_report.reason_code.clone(),
        shadow_broker_artifact_delta,
        operational_evidence_manifest_id: seal_receipt.manifest.manifest_id.clone(),
        operational_evidence_record_count: query_results.len(),
        correlation_id,
        reason_bundle_id,
        correlated_log,
        reason_bundle,
        kernel_binding_summary: [
            format!(
                "candidate_bundle={}",
                kernel_binding.candidate_bundle.relative_path()
            ),
            format!(
                "resolved_context_bundle={}",
                kernel_binding.resolved_context_bundle.relative_path()
            ),
            format!(
                "signal_kernel={}",
                kernel_binding.signal_kernel.relative_path()
            ),
            format!(
                "kernel_identity_digest={}",
                kernel_binding.identity.canonical_digest()
            ),
        ]
        .join("\n"),
        broker_reconnect_summary: [
            "session_reset_observed=true".to_string(),
            "broker_reconnect_observed=true".to_string(),
            "reset_observation_time_utc=2026-03-17T22:02:00Z".to_string(),
            format!("reset_reason_code={}", reset.reason_code),
            "reconnect_observation_reference=broker-session/ibkr-paper-reconnect-001".to_string(),
            format!("ack_callback_id={}", ack_receipt.callback_id),
            format!("fill_callback_id={}", fill_receipt.callback_id),
        ]
        .join("\n"),
        reconciliation_summary: [
            format!("intraday_status={}", intraday.status.as_str()),
            format!("intraday_reason_code={}", intraday.reason_code),
            format!("session_close_status={}", session_close.status.as_str()),
            format!("session_close_reason_code={}", session_close.reason_code),
            format!("daily_close_status={}", daily_close.status.as_str()),
            format!("daily_close_reason_code={}", daily_close.reason_code),
            format!(
                "next_session_eligibility={}",
                daily_close.next_session_eligibility.as_str()
            ),
            format!(
                "health_latest_readiness_packet_id={}",
                health
                    .latest_session_readiness_packet_id
                    .unwrap_or_else(|| "none".to_string())
            ),
            format!(
                "health_latest_authoritative_close_artifact_id={}",
                health
                    .latest_authoritative_close_artifact_id
                    .unwrap_or_else(|| "none".to_string())
            ),
            format!(
                "health_latest_operational_evidence_manifest_id={}",
                health
                    .latest_operational_evidence_manifest_id
                    .unwrap_or_else(|| "none".to_string())
            ),
        ]
        .join("\n"),
    };
    write_dummy_strategy_artifacts(artifact_dir, &report)
        .map_err(|error| format!("failed to write dummy-strategy artifacts: {error}"))?;
    Ok(report)
}

fn run_blocked_before_routing(artifact_dir: &Path) -> Result<DummyStrategySmokeReport, String> {
    let correlation_id = "corr-dummy-strategy-blocked-001".to_string();
    let reason_bundle_id = "reason-bundle-dummy-strategy-blocked-001".to_string();
    let deployment_instance_id = "deployment-dummy-strategy-001".to_string();
    let mut correlated_log = Vec::new();
    let mut reason_bundle = Vec::new();
    let mut runtime = OpsdRuntime::boot();

    let schedule = runtime
        .compile_and_install_schedule(sample_schedule_request())
        .map_err(|error| format!("schedule compile/install failed: {error:?}"))?;
    let tradeable = runtime
        .evaluate_session_topology("2026-03-18T15:00:00Z")
        .map_err(|error| format!("tradeable topology evaluation failed: {error:?}"))?;
    let reset = runtime
        .evaluate_session_topology("2026-03-17T22:02:00Z")
        .map_err(|error| format!("reset topology evaluation failed: {error:?}"))?;
    correlated_log.push(format!(
        "step=schedule_install correlation_id={correlation_id} artifact_id={} retained_artifact_id={}",
        schedule.artifact_id, schedule.retained_artifact_id
    ));

    let live_bar_request = sample_live_bar_request("tradeable-pass")
        .ok_or_else(|| "missing live-bar pass scenario".to_string())?;
    let live_bar_report = build_live_bar(&live_bar_request);
    write_live_bar_artifacts(
        &artifact_dir.join("live_bar"),
        &live_bar_request,
        &live_bar_report,
    )
    .map_err(|error| format!("failed to write live-bar artifacts: {error}"))?;
    let Some(bar) = live_bar_report.bar.as_ref() else {
        return Err("blocked scenario did not emit a live bar".to_string());
    };

    let (kernel_binding, kernel_decision) = evaluate_dummy_kernel(bar.close)?;
    let mut risk_request = sample_runtime_risk_request("green-tradeable-pass")
        .ok_or_else(|| "missing runtime-risk pass scenario".to_string())?;
    risk_request.request_id = "runtime-risk-dummy-strategy-blocked".to_string();
    let risk_report = evaluate_runtime_risk(&risk_request);
    write_runtime_risk_artifacts(
        &artifact_dir.join("runtime_risk"),
        &risk_request,
        &risk_report,
    )
    .map_err(|error| format!("failed to write runtime-risk artifacts: {error}"))?;

    let mut readiness_request =
        backtesting_engine_opsd::sample_session_readiness_request("broker-state-blocked")
            .ok_or_else(|| "missing readiness blocked scenario".to_string())?;
    readiness_request.packet_id = "session-readiness-dummy-blocked".to_string();
    readiness_request.deployment_instance_id = deployment_instance_id.clone();
    readiness_request.session_id = tradeable
        .session_id
        .clone()
        .unwrap_or_else(|| "globex_2026_03_18".to_string());
    readiness_request.correlation_id = correlation_id.clone();
    readiness_request.operator_summary =
        "Prove the dummy strategy halts before routing when broker state is blocked.".to_string();
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::SessionEligibility,
        &tradeable.reason_code,
        "Compiled session topology stayed tradeable, so broker state is the real blocker.",
        &schedule.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::RuntimeRisk,
        &risk_report.reason_code,
        "Runtime risk stayed green, so the blocked path is isolated to broker state readiness.",
        &risk_report.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::Entitlement,
        &live_bar_report.reason_code,
        "Approved live-bar construction still passed before the readiness block stopped routing.",
        &live_bar_report.retained_artifact_id,
    )?;
    sync_readiness_provider(
        &mut readiness_request,
        ReadinessProviderKind::BrokerState,
        "BROKER_STATE_BLOCKED",
        "Broker session state is blocked, so the dummy strategy must stop before any route or submit step.",
        "broker-session/ibkr-paper-blocked-001",
    )?;
    let readiness_packet = runtime.publish_session_readiness_packet(readiness_request.clone());
    backtesting_engine_opsd::write_session_readiness_artifacts(
        &artifact_dir.join("readiness"),
        &readiness_request,
        &readiness_packet,
    )
    .map_err(|error| format!("failed to write readiness artifacts: {error}"))?;

    let order_intent_identity = OrderIntentIdentity::new(
        deployment_instance_id,
        kernel_decision.sequence_number,
        "leg-primary",
        "buy",
        "entry",
    );
    let order_intent_id = order_intent_identity.deterministic_id();
    let mut paper_route_request =
        sample_route_mode_request("paper-route-blocked-readiness-blocked")
            .ok_or_else(|| "missing blocked paper-route scenario".to_string())?;
    paper_route_request.request_id = "route-mode-dummy-paper-blocked".to_string();
    paper_route_request.correlation_id = correlation_id.clone();
    paper_route_request.order_intent_id = order_intent_id.clone();
    paper_route_request.readiness_state = route_readiness_state(readiness_packet.status);
    paper_route_request.risk_allows_new_risk = risk_report.allow_new_risk;
    paper_route_request.policy_input_ids = vec![
        kernel_binding.identity.canonical_digest(),
        schedule.retained_artifact_id.clone(),
    ];
    paper_route_request.source_artifact_ids = vec![
        live_bar_report.retained_artifact_id.clone(),
        risk_report.retained_artifact_id.clone(),
        readiness_packet.retained_artifact_id.clone(),
    ];
    let paper_route_report = evaluate_route_mode(&paper_route_request);
    write_route_mode_artifacts(
        &artifact_dir.join("paper_route"),
        &paper_route_request,
        &paper_route_report,
    )
    .map_err(|error| format!("failed to write blocked paper-route artifacts: {error}"))?;

    correlated_log.extend([
        format!(
            "step=readiness_packet correlation_id={correlation_id} packet_id={} status={} reason_code={}",
            readiness_packet.packet_id,
            readiness_packet.status.as_str(),
            readiness_packet.reason_code
        ),
        format!(
            "step=paper_route correlation_id={correlation_id} outcome={} reason_code={}",
            paper_route_report.outcome.as_str(),
            paper_route_report.reason_code
        ),
    ]);
    reason_bundle.extend([
        format!(
            "Readiness packet {} stayed {} with {}.",
            readiness_packet.packet_id,
            readiness_packet.status.as_str(),
            readiness_packet.reason_code
        ),
        format!(
            "Route mode refused the dummy strategy with {} before any broker mutation was attempted.",
            paper_route_report.reason_code
        ),
        "No broker callback, ledger booking, reconciliation, or archive seal occurred after the blocked readiness step.".to_string(),
    ]);

    let report = DummyStrategySmokeReport {
        scenario: BLOCKED_SCENARIO.to_string(),
        artifact_dir: artifact_dir.to_path_buf(),
        final_status: "blocked".to_string(),
        final_reason_code: paper_route_report.reason_code.clone(),
        kernel_disposition: kernel_decision.disposition.as_str().to_string(),
        kernel_score_ticks: kernel_decision.score_ticks,
        kernel_identity_digest: kernel_binding.identity.canonical_digest(),
        tradeable_state: tradeable.state.as_str().to_string(),
        tradeable_reason_code: tradeable.reason_code,
        reset_state: reset.state.as_str().to_string(),
        reset_reason_code: reset.reason_code.clone(),
        session_reset_observed: true,
        broker_reconnect_observed: false,
        readiness_status: readiness_packet.status.as_str().to_string(),
        readiness_reason_code: readiness_packet.reason_code.clone(),
        readiness_packet_id: readiness_packet.packet_id.clone(),
        risk_status: risk_report.status.as_str().to_string(),
        risk_reason_code: risk_report.reason_code.clone(),
        paper_route_outcome: paper_route_report.outcome.as_str().to_string(),
        paper_route_reason_code: paper_route_report.reason_code.clone(),
        paper_broker_artifact_count: runtime.broker_artifacts().len(),
        paper_callback_count: runtime.broker_callback_log().len(),
        paper_order_intent_id: order_intent_id,
        intraday_status: "not_executed".to_string(),
        intraday_reason_code: "NOT_EXECUTED_AFTER_READINESS_BLOCK".to_string(),
        session_close_status: "not_executed".to_string(),
        session_close_reason_code: "NOT_EXECUTED_AFTER_READINESS_BLOCK".to_string(),
        daily_close_status: "not_executed".to_string(),
        daily_close_reason_code: "NOT_EXECUTED_AFTER_READINESS_BLOCK".to_string(),
        next_session_eligibility: "not_executed".to_string(),
        shadow_route_outcome: "not_executed".to_string(),
        shadow_route_reason_code: "NOT_EXECUTED_AFTER_READINESS_BLOCK".to_string(),
        shadow_broker_artifact_delta: 0,
        operational_evidence_manifest_id: "not_sealed".to_string(),
        operational_evidence_record_count: 0,
        correlation_id,
        reason_bundle_id,
        correlated_log,
        reason_bundle,
        kernel_binding_summary: [
            format!("candidate_bundle={}", kernel_binding.candidate_bundle.relative_path()),
            format!(
                "resolved_context_bundle={}",
                kernel_binding.resolved_context_bundle.relative_path()
            ),
            format!("signal_kernel={}", kernel_binding.signal_kernel.relative_path()),
            format!("kernel_identity_digest={}", kernel_binding.identity.canonical_digest()),
        ]
        .join("\n"),
        broker_reconnect_summary: [
            "session_reset_observed=true".to_string(),
            "broker_reconnect_observed=false".to_string(),
            "reset_observation_time_utc=2026-03-17T22:02:00Z".to_string(),
            format!("reset_reason_code={}", reset.reason_code),
            "reconnect_observation_reference=broker-session/ibkr-paper-blocked-001".to_string(),
            "note=readiness blocked the lane before any broker reconnect-safe mutation could be observed".to_string(),
        ]
        .join("\n"),
        reconciliation_summary: [
            "intraday_status=not_executed".to_string(),
            "session_close_status=not_executed".to_string(),
            "daily_close_status=not_executed".to_string(),
            "next_session_eligibility=not_executed".to_string(),
        ]
        .join("\n"),
    };
    write_dummy_strategy_artifacts(artifact_dir, &report)
        .map_err(|error| format!("failed to write dummy-strategy artifacts: {error}"))?;
    Ok(report)
}

fn run_named_scenario(
    scenario: &str,
    artifact_dir: &Path,
) -> Result<DummyStrategySmokeReport, String> {
    match scenario {
        PASS_SCENARIO => run_paper_shadow_e2e_pass(artifact_dir),
        BLOCKED_SCENARIO => run_blocked_before_routing(artifact_dir),
        _ => Err(format!("unknown dummy-strategy scenario: {scenario}")),
    }
}

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_flag(args, "--scenario")?;
    let artifact_dir = PathBuf::from(parse_flag(args, "--artifact-dir")?);
    let report = run_named_scenario(scenario, &artifact_dir)?;
    for line in report.render_lines() {
        println!("{line}");
    }
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            eprintln!("{}", usage());
            ExitCode::from(2)
        }
    }
}

#[cfg(test)]
mod smoke_tests {
    use std::env;
    use std::path::{Path, PathBuf};

    use super::{run_named_scenario, BLOCKED_SCENARIO, PASS_SCENARIO};

    fn safe_tmp_root() -> PathBuf {
        let shm_root = Path::new("/dev/shm");
        if shm_root.exists() {
            shm_root.join("backtesting_engine_dummy_strategy_smoke_tests")
        } else {
            env::temp_dir().join("backtesting_engine_dummy_strategy_smoke_tests")
        }
    }

    #[test]
    fn scenario_sweep_emits_dummy_strategy_reports() {
        let artifact_root = PathBuf::from(
            env::var("DUMMY_STRATEGY_SMOKE_ARTIFACT_ROOT")
                .unwrap_or_else(|_| safe_tmp_root().display().to_string()),
        );
        for scenario in [PASS_SCENARIO, BLOCKED_SCENARIO] {
            let report = run_named_scenario(scenario, &artifact_root.join(scenario))
                .expect("dummy strategy scenario must succeed");
            for line in report.render_lines() {
                println!("{line}");
            }
        }
    }

    #[test]
    fn pass_scenario_preserves_shadow_suppression_without_extra_broker_mutation() {
        let artifact_root = safe_tmp_root().join("pass_assertions");
        let report =
            run_named_scenario(PASS_SCENARIO, &artifact_root).expect("pass scenario must succeed");
        assert_eq!("pass", report.final_status);
        assert_eq!("suppressed", report.shadow_route_outcome);
        assert_eq!(0, report.shadow_broker_artifact_delta);
        assert_eq!("eligible", report.next_session_eligibility);
        assert!(report.broker_reconnect_observed);
        assert!(report.operational_evidence_record_count >= 4);
    }

    #[test]
    fn blocked_scenario_halts_before_broker_mutation() {
        let artifact_root = safe_tmp_root().join("blocked_assertions");
        let report = run_named_scenario(BLOCKED_SCENARIO, &artifact_root)
            .expect("blocked scenario must still render artifacts");
        assert_eq!("blocked", report.final_status);
        assert_eq!(0, report.paper_broker_artifact_count);
        assert_eq!("not_executed", report.shadow_route_outcome);
        assert_eq!(0, report.operational_evidence_record_count);
    }
}
