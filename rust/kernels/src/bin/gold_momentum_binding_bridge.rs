use std::process::ExitCode;

use backtesting_engine_kernels::{
    BarInput, GOLD_MOMENTUM_BINDING_MODULE, GOLD_MOMENTUM_IDENTITY, GoldMomentumKernel,
};

fn main() -> ExitCode {
    let Some((lookback_bars, threshold_ticks, inputs)) = parse_args() else {
        return ExitCode::FAILURE;
    };
    let decisions = GoldMomentumKernel::evaluate_series(lookback_bars, threshold_ticks, &inputs);
    print!(
        "{}",
        render_json(
            GOLD_MOMENTUM_BINDING_MODULE,
            lookback_bars,
            threshold_ticks,
            &decisions,
        )
    );
    ExitCode::SUCCESS
}

fn parse_args() -> Option<(usize, i64, Vec<BarInput>)> {
    let mut lookback_bars = None;
    let mut threshold_ticks = None;
    let mut closes = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--lookback-bars" => lookback_bars = args.next(),
            "--threshold-ticks" => threshold_ticks = args.next(),
            "--closes" => closes = args.next(),
            "--json" => {}
            other => {
                eprintln!("unexpected argument: {other}");
                return None;
            }
        }
    }
    let lookback_bars = lookback_bars?.parse::<usize>().ok()?;
    let threshold_ticks = threshold_ticks?.parse::<i64>().ok()?;
    let closes = closes?;
    let mut inputs = Vec::new();
    for (index, value) in closes.split(',').enumerate() {
        let close_ticks = value.trim().parse::<i64>().ok()?;
        inputs.push(BarInput {
            sequence_number: (index + 1) as u64,
            close_ticks,
        });
    }
    Some((lookback_bars, threshold_ticks, inputs))
}

fn render_json(
    entry_path: &str,
    lookback_bars: usize,
    threshold_ticks: i64,
    decisions: &[backtesting_engine_kernels::SignalDecision],
) -> String {
    let identity = GOLD_MOMENTUM_IDENTITY;
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str(&format!("  \"entry_path\": \"{}\",\n", entry_path));
    output.push_str("  \"identity\": {\n");
    output.push_str(&format!(
        "    \"strategy_family_id\": \"{}\",\n",
        identity.strategy_family_id
    ));
    output.push_str(&format!(
        "    \"rust_crate\": \"{}\",\n",
        identity.rust_crate
    ));
    output.push_str(&format!(
        "    \"python_binding_module\": \"{}\",\n",
        identity.python_binding_module
    ));
    output.push_str(&format!(
        "    \"kernel_abi_version\": \"{}\",\n",
        identity.kernel_abi_version
    ));
    output.push_str(&format!(
        "    \"state_serialization_version\": \"{}\",\n",
        identity.state_serialization_version
    ));
    output.push_str(&format!(
        "    \"semantic_version\": \"{}\",\n",
        identity.semantic_version
    ));
    output.push_str(&format!(
        "    \"canonical_digest\": \"{}\"\n",
        identity.canonical_digest()
    ));
    output.push_str("  },\n");
    output.push_str(&format!("  \"lookback_bars\": {},\n", lookback_bars));
    output.push_str(&format!("  \"threshold_ticks\": {},\n", threshold_ticks));
    output.push_str("  \"decisions\": [\n");
    for (index, decision) in decisions.iter().enumerate() {
        output.push_str("    {");
        output.push_str(&format!(
            "\"sequence_number\": {}, \"disposition\": \"{}\", \"score_ticks\": {}",
            decision.sequence_number,
            decision.disposition.as_str(),
            decision.score_ticks,
        ));
        output.push('}');
        if index + 1 != decisions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n");
    output.push_str("}\n");
    output
}
