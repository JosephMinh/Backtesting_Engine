use backtesting_engine_kernels as _;
use backtesting_engine_opsd::{
    AuthoritativeStatementSet, BrokerCallback, BrokerCallbackKind, BrokerContractDescriptor,
    BrokerControlRequest, BrokerOrderIntentRequest, BrokerOrderType, BrokerTimeInForce,
    CompiledSessionState, DailyLedgerCloseRequest, DeliveryFenceWindowDefinition,
    IntradayReconciliationRequest, LedgerEventClass, LedgerEventRequest,
    MaintenanceWindowDefinition, OperatorRequest, OpsdModule, OpsdRuntime, OrderIntentIdentity,
    PolicyOverlayWindowDefinition, RuntimeControlAction, ScheduleCompileRequest,
    SessionCalendarEntry, SessionCloseRequest, SessionDayKind, module_boundary,
    sample_session_readiness_request,
};

fn usage() -> i32 {
    eprintln!(
        "usage: cargo run -p backtesting-engine-opsd -- --scenario <startup-handoff|mailbox-backpressure|broker-mutation-control|schedule-reset-boundary|ledger-session-close|authoritative-reconciliation|session-readiness>"
    );
    2
}

fn join_modules(modules: &[OpsdModule]) -> String {
    modules
        .iter()
        .map(|module| module.as_str())
        .collect::<Vec<_>>()
        .join(",")
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

fn scenario_startup_handoff() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let startup = runtime.startup_report().clone();

    let control = runtime
        .handle_operator_request(OperatorRequest::new(
            "startup-control",
            OpsdModule::Risk,
            RuntimeControlAction::HaltNewOrders,
            "ops-http-smoke",
        ))
        .expect("startup control action should fit");
    let reconciliation = runtime
        .publish_reconciliation_tick(
            "startup-reconcile",
            OpsdModule::StateStore,
            "state-store handoff after startup barrier",
        )
        .expect("startup reconciliation tick should fit");
    let broker_probe = runtime
        .enqueue_health_probe(OpsdModule::Broker, "startup-probe")
        .expect("broker health probe should fit");
    let broker_cancel = runtime
        .handle_broker_control_request(BrokerControlRequest::new(
            "startup-cancel",
            "ops-http-smoke",
            "decision-trace-startup-cancel",
            "expected-timeline-startup-cancel",
            "actual-timeline-startup-cancel",
            "artifact-manifest-startup-cancel",
            "reason-bundle-startup-cancel",
            OrderIntentIdentity::new("startup-gold-1", 91, "broker", "flat", "cancel_open_orders"),
            RuntimeControlAction::CancelOpenOrders,
            "WITHDRAW_LIVE_OPERATOR_REQUEST",
        ))
        .expect("broker cancel should fit");

    let first_broker = runtime
        .drain_next(OpsdModule::Broker)
        .expect("broker should drain high-priority cancel");
    let second_broker = runtime
        .drain_next(OpsdModule::Broker)
        .expect("broker should then drain the health probe");
    let health = runtime.health_report();

    println!("scenario=startup_handoff");
    println!("booted_modules={}", join_modules(&startup.booted_modules));
    println!("startup_steps={}", startup.startup_steps.len());
    println!("state_owner_count={}", health.state_owners.len());
    println!(
        "risk_control={}:{}:{}",
        control.target.as_str(),
        control.message_kind.as_str(),
        control.priority.as_str()
    );
    println!(
        "reconciliation_tick={}:{}:{}",
        reconciliation.target.as_str(),
        reconciliation.message_kind.as_str(),
        reconciliation.priority.as_str()
    );
    println!(
        "broker_probe={}:{}:{}",
        broker_probe.target.as_str(),
        broker_probe.message_kind.as_str(),
        broker_probe.priority.as_str()
    );
    println!(
        "broker_cancel={}:{}:{}",
        broker_cancel.dispatch.target.as_str(),
        broker_cancel.dispatch.message_kind.as_str(),
        broker_cancel.dispatch.priority.as_str()
    );
    println!(
        "broker_drain_order={},{}",
        first_broker.kind.as_str(),
        second_broker.kind.as_str()
    );
    println!("dispatch_count={}", health.dispatch_count);
    0
}

fn scenario_mailbox_backpressure() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    runtime
        .submit_order_intent(BrokerOrderIntentRequest::new(
            "overflow-seed",
            "decision-trace-overflow-seed",
            "expected-timeline-overflow-seed",
            "actual-timeline-overflow-seed",
            "artifact-manifest-overflow-seed",
            "reason-bundle-overflow-seed",
            OrderIntentIdentity::new("paper-gold-1", 42, "leg-a", "buy", "entry"),
            BrokerOrderType::Limit,
            BrokerTimeInForce::Day,
            BrokerContractDescriptor::one_oz_comex(),
        ))
        .expect("seed submit should fit");
    for index in 0..module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity {
        runtime
            .handle_broker_control_request(BrokerControlRequest::new(
                format!("overflow-fill-{index}"),
                "ops-http-smoke",
                format!("decision-trace-overflow-{index}"),
                format!("expected-timeline-overflow-{index}"),
                format!("actual-timeline-overflow-{index}"),
                format!("artifact-manifest-overflow-{index}"),
                format!("reason-bundle-overflow-{index}"),
                OrderIntentIdentity::new(
                    "paper-gold-1",
                    100 + index as u64,
                    "broker",
                    "flat",
                    "cancel_open_orders",
                ),
                RuntimeControlAction::CancelOpenOrders,
                "WITHDRAW_LIVE_OPERATOR_REQUEST",
            ))
            .expect("broker high-priority slot should fit");
    }

    let diagnostic = match runtime.handle_broker_control_request(BrokerControlRequest::new(
        "overflow-trigger",
        "ops-http-smoke",
        "decision-trace-overflow-trigger",
        "expected-timeline-overflow-trigger",
        "actual-timeline-overflow-trigger",
        "artifact-manifest-overflow-trigger",
        "reason-bundle-overflow-trigger",
        OrderIntentIdentity::new("paper-gold-1", 999, "broker", "flat", "flatten_positions"),
        RuntimeControlAction::FlattenPositions,
        "KILL_SWITCH_FLATTEN_REQUEST",
    )) {
        Err(backtesting_engine_opsd::DispatchError::Backpressure(diagnostic)) => diagnostic,
        Ok(_) => {
            eprintln!("expected mailbox backpressure diagnostic");
            return 1;
        }
        Err(other) => {
            eprintln!("unexpected dispatch error: {other:?}");
            return 1;
        }
    };

    println!("scenario=mailbox_backpressure");
    println!("mailbox_owner={}", diagnostic.mailbox_owner.as_str());
    println!("priority={}", diagnostic.priority.as_str());
    println!("capacity={}", diagnostic.capacity);
    println!("depth={}", diagnostic.depth);
    println!("message_kind={}", diagnostic.message_kind.as_str());
    println!("correlation_id={}", diagnostic.correlation_id);
    0
}

fn scenario_broker_mutation_control() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let submit_request = BrokerOrderIntentRequest::new(
        "submit-intent-1",
        "decision-trace-broker-1",
        "expected-timeline-broker-1",
        "actual-timeline-broker-1",
        "artifact-manifest-broker-1",
        "reason-bundle-broker-1",
        OrderIntentIdentity::new("paper-gold-1", 77, "leg-a", "buy", "entry"),
        BrokerOrderType::Limit,
        BrokerTimeInForce::Day,
        BrokerContractDescriptor::one_oz_comex(),
    );
    let first_submit = runtime
        .submit_order_intent(submit_request.clone())
        .expect("initial broker submit should fit");
    let retry_submit = runtime
        .submit_order_intent(submit_request)
        .expect("retry submit should reuse broker mapping");
    let control = runtime
        .handle_broker_control_request(BrokerControlRequest::new(
            "control-intent-1",
            "ops-http-smoke",
            "decision-trace-control-1",
            "expected-timeline-control-1",
            "actual-timeline-control-1",
            "artifact-manifest-control-1",
            "reason-bundle-control-1",
            OrderIntentIdentity::new("paper-gold-1", 120, "broker", "flat", "cancel_open_orders"),
            RuntimeControlAction::CancelOpenOrders,
            "WITHDRAW_LIVE_OPERATOR_REQUEST",
        ))
        .expect("governed broker control should fit");
    let broker_order_id = first_submit
        .broker_order_ids
        .first()
        .expect("initial submit should emit a broker order id")
        .clone();
    runtime
        .record_broker_callback(BrokerCallback::new(
            "fill-1",
            broker_order_id.clone(),
            BrokerCallbackKind::Fill,
        ))
        .expect("first fill should apply");
    let duplicate_fill = runtime
        .record_broker_callback(BrokerCallback::new(
            "fill-1",
            broker_order_id,
            BrokerCallbackKind::Fill,
        ))
        .expect("duplicate fill should deduplicate");
    let artifact_ids = runtime
        .broker_artifacts()
        .iter()
        .map(|artifact| artifact.artifact_id.clone())
        .collect::<Vec<_>>()
        .join(",");

    println!("scenario=broker_mutation_control");
    println!("submit_intent_id={}", first_submit.order_intent_id);
    println!(
        "submit_broker_order_id={}",
        first_submit.broker_order_ids[0]
    );
    println!("retry_idempotent={}", retry_submit.idempotent_replay);
    println!(
        "retry_broker_order_id={}",
        retry_submit
            .broker_order_ids
            .first()
            .expect("retry should reuse broker order id")
    );
    println!(
        "duplicate_callback_deduplicated={}",
        duplicate_fill.deduplicated
    );
    println!("callback_reason_code={}", duplicate_fill.reason_code);
    println!("control_action={}", control.mutation_kind.as_str());
    println!("control_reason_code={}", control.reason_code);
    println!("control_intent_id={}", control.order_intent_id);
    println!(
        "control_broker_order_ids={}",
        control.broker_order_ids.join(",")
    );
    println!("artifact_count={}", runtime.broker_artifacts().len());
    println!("artifact_ids={artifact_ids}");
    println!("dispatch_count={}", runtime.health_report().dispatch_count);
    0
}

fn scenario_schedule_reset_boundary() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let activation = runtime
        .compile_and_install_schedule(sample_schedule_request())
        .expect("compiled schedule should install");
    let winter_tradeable = runtime
        .evaluate_session_topology("2026-02-18T00:00:00Z")
        .expect("winter session should evaluate");
    let maintenance = runtime
        .evaluate_session_topology("2026-03-17T21:15:00Z")
        .expect("maintenance window should evaluate");
    let reset = runtime
        .evaluate_session_topology("2026-03-17T22:02:00Z")
        .expect("reset boundary should evaluate");
    let post_reset = runtime
        .evaluate_session_topology("2026-03-17T22:10:00Z")
        .expect("post-reset tradeability should evaluate");
    let delivery = runtime
        .evaluate_session_topology("2026-03-18T13:30:00Z")
        .expect("delivery fence should evaluate");
    let health = runtime.health_report();

    println!("scenario=schedule_reset_boundary");
    println!("artifact_id={}", activation.artifact_id);
    println!("retained_artifact_id={}", activation.retained_artifact_id);
    println!(
        "compiled_range={},{}",
        activation.compiled_from_utc, activation.compiled_to_utc
    );
    println!("slice_count={}", activation.slice_count);
    println!("tradeable_slice_count={}", activation.tradeable_slice_count);
    println!(
        "winter_offset_minutes={}",
        winter_tradeable.exchange_offset_minutes
    );
    println!("maintenance_state={}", maintenance.state.as_str());
    println!("maintenance_reason={}", maintenance.reason_code);
    println!("reset_state={}", reset.state.as_str());
    println!("reset_reason={}", reset.reason_code);
    println!("post_reset_tradeable={}", post_reset.tradeable);
    println!("post_reset_reason={}", post_reset.reason_code);
    println!("delivery_state={}", delivery.state.as_str());
    println!("delivery_reason={}", delivery.reason_code);
    println!(
        "health_schedule_artifact_id={}",
        health
            .compiled_schedule_artifact_id
            .expect("schedule artifact should be visible in health")
    );
    println!(
        "health_schedule_slice_count={}",
        health.compiled_schedule_slice_count
    );
    0
}

fn scenario_ledger_session_close() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let schedule = runtime
        .compile_and_install_schedule(sample_schedule_request())
        .expect("compiled schedule should install");
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
                schedule.retained_artifact_id.clone(),
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
                schedule.retained_artifact_id.clone(),
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
        .expect("booked commission should append");
    runtime
        .append_ledger_event(LedgerEventRequest {
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
            compiled_schedule_artifact_id: schedule.retained_artifact_id.clone(),
            close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
        })
        .expect("session close should build");
    let health = runtime.health_report();

    println!("scenario=ledger_session_close");
    println!("ledger_event_count={}", runtime.ledger_events().len());
    println!("duplicate_fill_idempotent={}", duplicate.idempotent_replay);
    println!("close_status={}", close.status.as_str());
    println!("close_reason={}", close.reason_code);
    println!(
        "as_booked_position_contracts={}",
        close.as_booked_totals.position_contracts
    );
    println!(
        "as_booked_commission_usd_cents={}",
        close.as_booked_totals.commission_total_usd_cents
    );
    println!(
        "as_reconciled_commission_usd_cents={}",
        close.as_reconciled_totals.commission_total_usd_cents
    );
    println!(
        "broker_initial_margin_usd_cents={}",
        close
            .broker_authoritative_snapshot
            .initial_margin_requirement_usd_cents
            .expect("margin snapshot should be present")
    );
    println!("manifest_id={}", close.manifest.manifest_id);
    println!("artifact_id={}", close.artifact_id);
    println!("retained_artifact_id={}", close.retained_artifact_id);
    println!(
        "health_latest_close_artifact_id={}",
        health
            .latest_session_close_artifact_id
            .expect("health should expose latest session close")
    );
    println!("health_ledger_event_count={}", health.ledger_event_count);
    0
}

fn scenario_authoritative_reconciliation() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let schedule = runtime
        .compile_and_install_schedule(sample_schedule_request())
        .expect("compiled schedule should install");
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
            source_artifact_ids: vec![
                "artifact-1001".to_string(),
                schedule.retained_artifact_id.clone(),
            ],
        })
        .expect("booked fill should append");
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
            source_artifact_ids: vec!["artifact-1002".to_string()],
        })
        .expect("booked commission should append");
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
            source_artifact_ids: vec!["artifact-1003".to_string()],
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
            source_artifact_ids: vec!["artifact-1004".to_string()],
        })
        .expect("broker EOD margin should append");
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
    let session_close = runtime
        .build_session_close_artifact(SessionCloseRequest {
            close_id: "close-2".to_string(),
            account_id: "acct-1".to_string(),
            symbol: "1OZ".to_string(),
            session_id: "globex_2026_03_18".to_string(),
            compiled_schedule_artifact_id: schedule.retained_artifact_id.clone(),
            close_completed_at_utc: "2026-03-18T22:15:00Z".to_string(),
        })
        .expect("session close should build");
    let daily_close = runtime
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
                    "evidence/broker/statement-set-2026-03-18.sha256".to_string(),
                ],
            },
            runtime_unrealized_pnl_usd_cents: Some(8_750),
            reviewed_or_waived: false,
            review_or_waiver_id: None,
            correlation_id: "daily-corr-1".to_string(),
            evaluated_at_utc: "2026-03-18T22:25:00Z".to_string(),
        })
        .expect("authoritative daily close should build");
    let health = runtime.health_report();
    let intraday_categories = intraday
        .discrepancy_summaries
        .iter()
        .map(|summary| summary.category.as_str())
        .collect::<Vec<_>>()
        .join(",");
    let close_categories = daily_close
        .discrepancy_summaries
        .iter()
        .map(|summary| summary.category.as_str())
        .collect::<Vec<_>>()
        .join(",");

    println!("scenario=authoritative_reconciliation");
    println!("intraday_artifact_id={}", intraday.artifact_id);
    println!("intraday_status={}", intraday.status.as_str());
    println!("intraday_reason={}", intraday.reason_code);
    println!("intraday_action={}", intraday.required_action.as_str());
    println!(
        "intraday_blocking_new_entries={}",
        intraday.blocking_new_entries
    );
    println!("intraday_categories={intraday_categories}");
    println!("daily_close_artifact_id={}", daily_close.artifact_id);
    println!("daily_close_status={}", daily_close.status.as_str());
    println!("daily_close_reason={}", daily_close.reason_code);
    println!(
        "next_session_eligibility={}",
        daily_close.next_session_eligibility.as_str()
    );
    println!(
        "daily_close_discrepancy_ids={}",
        daily_close.discrepancy_summary_ids.join(",")
    );
    println!("daily_close_categories={close_categories}");
    println!(
        "daily_close_statement_set_id={}",
        daily_close.authoritative_statement_set_id
    );
    println!(
        "health_latest_authoritative_close_artifact_id={}",
        health
            .latest_authoritative_close_artifact_id
            .expect("health should expose the latest authoritative close")
    );
    println!(
        "health_next_session_eligibility={}",
        health
            .next_session_eligibility
            .expect("health should expose next-session eligibility")
    );
    0
}

fn scenario_session_readiness() -> i32 {
    let mut runtime = OpsdRuntime::boot();
    let green_packet = runtime.publish_session_readiness_packet(
        sample_session_readiness_request("green-readiness-pass")
            .expect("green readiness scenario should exist"),
    );
    let blocked_packet = runtime.publish_session_readiness_packet(
        sample_session_readiness_request("clock-stale-blocked")
            .expect("blocked readiness scenario should exist"),
    );
    let latest = runtime
        .latest_session_readiness_packet()
        .expect("latest readiness packet should be retained");
    let health = runtime.health_report();

    println!("scenario=session_readiness");
    println!("green_packet_id={}", green_packet.packet_id);
    println!("green_status={}", green_packet.status.as_str());
    println!("green_reason_code={}", green_packet.reason_code);
    println!("green_history_len={}", green_packet.history.len());
    println!("blocked_packet_id={}", blocked_packet.packet_id);
    println!("blocked_packet_digest={}", blocked_packet.packet_digest);
    println!("blocked_status={}", blocked_packet.status.as_str());
    println!("blocked_reason_code={}", blocked_packet.reason_code);
    println!(
        "blocked_provider_ids={}",
        blocked_packet.blocked_provider_ids.join(",")
    );
    println!("blocked_history_len={}", blocked_packet.history.len());
    println!(
        "blocked_retained_artifact_id={}",
        blocked_packet.retained_artifact_id
    );
    println!("latest_packet_id={}", latest.packet_id);
    println!("latest_packet_digest={}", latest.packet_digest);
    println!("latest_summary={}", latest.summary);
    println!(
        "health_latest_readiness_packet_id={}",
        health
            .latest_session_readiness_packet_id
            .expect("health should expose latest readiness packet id")
    );
    println!(
        "health_latest_readiness_packet_digest={}",
        health
            .latest_session_readiness_packet_digest
            .expect("health should expose latest readiness packet digest")
    );
    println!(
        "health_latest_readiness_status={}",
        health
            .latest_session_readiness_status
            .expect("health should expose latest readiness status")
    );
    println!(
        "health_latest_readiness_reason_code={}",
        health
            .latest_session_readiness_reason_code
            .expect("health should expose latest readiness reason")
    );
    println!(
        "health_readiness_history_len={}",
        health.readiness_history_len
    );
    0
}

fn run() -> i32 {
    let mut args = std::env::args().skip(1);
    let Some(flag) = args.next() else {
        return usage();
    };
    if flag != "--scenario" {
        return usage();
    }
    let Some(scenario) = args.next() else {
        return usage();
    };
    if args.next().is_some() {
        return usage();
    }
    match scenario.as_str() {
        "startup-handoff" => scenario_startup_handoff(),
        "mailbox-backpressure" => scenario_mailbox_backpressure(),
        "broker-mutation-control" => scenario_broker_mutation_control(),
        "schedule-reset-boundary" => scenario_schedule_reset_boundary(),
        "ledger-session-close" => scenario_ledger_session_close(),
        "authoritative-reconciliation" => scenario_authoritative_reconciliation(),
        "session-readiness" => scenario_session_readiness(),
        _ => usage(),
    }
}

fn main() {
    std::process::exit(run());
}
