use backtesting_engine_kernels as _;
use backtesting_engine_opsd::{
    OperatorRequest, OpsdModule, OpsdRuntime, RuntimeControlAction, module_boundary,
};

fn usage() -> i32 {
    eprintln!(
        "usage: cargo run -p backtesting-engine-opsd -- --scenario <startup-handoff|mailbox-backpressure>"
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
        .handle_operator_request(OperatorRequest::new(
            "startup-cancel",
            OpsdModule::Broker,
            RuntimeControlAction::CancelOpenOrders,
            "ops-http-smoke",
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
        broker_cancel.target.as_str(),
        broker_cancel.message_kind.as_str(),
        broker_cancel.priority.as_str()
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
    for index in 0..module_boundary(OpsdModule::Broker).high_priority_mailbox_capacity {
        runtime
            .handle_operator_request(OperatorRequest::new(
                format!("overflow-fill-{index}"),
                OpsdModule::Broker,
                RuntimeControlAction::CancelOpenOrders,
                "ops-http-smoke",
            ))
            .expect("broker high-priority slot should fit");
    }

    let diagnostic = match runtime.handle_operator_request(OperatorRequest::new(
        "overflow-trigger",
        OpsdModule::Broker,
        RuntimeControlAction::FlattenPositions,
        "ops-http-smoke",
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
        _ => usage(),
    }
}

fn main() {
    std::process::exit(run());
}
