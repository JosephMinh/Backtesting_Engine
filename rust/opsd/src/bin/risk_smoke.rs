#[path = "../risk.rs"]
mod risk;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use risk::{evaluate_runtime_risk, sample_runtime_risk_request, write_runtime_risk_artifacts};

fn usage() -> &'static str {
    "usage: risk_smoke --scenario <green-tradeable-pass|degraded-data-restrict|daily-loss-exit-only|drawdown-flatten|delivery-fence-flatten|warmup-hold|margin-halt|overnight-approval-block|size-reduction-restrict> --artifact-dir <dir>"
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

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_flag(args, "--scenario")?;
    let artifact_dir = PathBuf::from(parse_flag(args, "--artifact-dir")?);
    let request = sample_runtime_risk_request(scenario)
        .ok_or_else(|| format!("unknown risk scenario: {scenario}"))?;
    let report = evaluate_runtime_risk(&request);
    write_runtime_risk_artifacts(&artifact_dir, &request, &report)
        .map_err(|err| format!("failed to write risk artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("status={}", report.status.as_str());
    println!("action={}", report.action.as_str());
    println!("entry_mode={}", report.entry_mode.as_str());
    println!("reason_code={}", report.reason_code);
    println!("trading_eligible={}", report.trading_eligible);
    println!("allow_new_risk={}", report.allow_new_risk);
    println!("require_flatten={}", report.require_flatten);
    println!(
        "effective_max_position_contracts={}",
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
    if !report.triggered_control_ids.is_empty() {
        println!(
            "triggered_control_ids={}",
            report.triggered_control_ids.join(",")
        );
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
    use std::path::PathBuf;

    use super::risk::{
        evaluate_runtime_risk, sample_runtime_risk_request, write_runtime_risk_artifacts,
    };

    #[test]
    fn scenario_sweep_emits_runtime_states() {
        let artifact_root =
            PathBuf::from(env::var("RISK_SMOKE_ARTIFACT_ROOT").unwrap_or_else(|_| {
                env::temp_dir()
                    .join("backtesting_engine_opsd_risk_smoke_tests")
                    .display()
                    .to_string()
            }));

        for scenario in [
            "green-tradeable-pass",
            "degraded-data-restrict",
            "daily-loss-exit-only",
            "drawdown-flatten",
            "margin-halt",
        ] {
            let request =
                sample_runtime_risk_request(scenario).expect("scenario must exist for smoke");
            let report = evaluate_runtime_risk(&request);
            let artifact_dir = artifact_root.join(scenario);
            write_runtime_risk_artifacts(&artifact_dir, &request, &report)
                .expect("smoke artifacts must write");

            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("status={}", report.status.as_str());
            println!("action={}", report.action.as_str());
            println!("entry_mode={}", report.entry_mode.as_str());
            println!("reason_code={}", report.reason_code);
            println!("trading_eligible={}", report.trading_eligible);
            println!("allow_new_risk={}", report.allow_new_risk);
            println!("require_flatten={}", report.require_flatten);
            println!(
                "effective_max_position_contracts={}",
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
            if !report.triggered_control_ids.is_empty() {
                println!(
                    "triggered_control_ids={}",
                    report.triggered_control_ids.join(",")
                );
            }
        }
    }
}
