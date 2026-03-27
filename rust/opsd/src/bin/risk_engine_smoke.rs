#[path = "../risk.rs"]
mod risk;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use risk::{evaluate_runtime_risk, sample_runtime_risk_request, write_runtime_risk_artifacts};

fn usage() -> &'static str {
    "usage: risk_engine_smoke --scenario <green-tradeable-pass|degraded-data-restrict|daily-loss-exit-only|drawdown-flatten|delivery-fence-flatten|warmup-hold|margin-halt|overnight-approval-block|size-reduction-restrict> --artifact-dir <dir>"
}

fn parse_flag(args: &[String], flag: &str) -> Result<String, String> {
    let Some(index) = args.iter().position(|arg| arg == flag) else {
        return Err(format!("missing {flag}"));
    };
    let Some(value) = args.get(index + 1) else {
        return Err(format!("missing value for {flag}"));
    };
    Ok(value.clone())
}

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_flag(args, "--scenario")?;
    let artifact_dir = PathBuf::from(parse_flag(args, "--artifact-dir")?);
    let request = sample_runtime_risk_request(&scenario)
        .ok_or_else(|| format!("unknown risk scenario: {scenario}"))?;
    let report = evaluate_runtime_risk(&request);
    write_runtime_risk_artifacts(&artifact_dir, &request, &report)
        .map_err(|err| format!("failed to write risk artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("eligibility_state={}", report.status.as_str());
    println!("action={}", report.action.as_str());
    println!("reason_code={}", report.reason_code);
    println!("entry_mode={}", report.entry_mode.as_str());
    println!(
        "effective_max_position_size={}",
        report.effective_max_position_contracts
    );
    println!(
        "effective_max_concurrent_order_intents={}",
        report.effective_max_concurrent_order_intents
    );
    println!(
        "triggered_control_count={}",
        report.triggered_control_ids.len()
    );
    println!("retained_artifact_id={}", report.retained_artifact_id);
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
