#[path = "../risk.rs"]
mod risk;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use risk::{evaluate_runtime_risk, sample_runtime_risk_request, write_runtime_risk_artifacts};

fn usage() -> &'static str {
    "usage: strategy_health_smoke --scenario <behavior-drift-restrict|behavior-drift-exit-only|data-quality-halt|operating-envelope-fit-restrict|operating-envelope-fit-flatten|recalibration-required-restrict> --artifact-dir <dir>"
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

fn emit_report(scenario: &str, artifact_dir: &PathBuf) -> Result<(), String> {
    let request = sample_runtime_risk_request(scenario)
        .ok_or_else(|| format!("unknown strategy health scenario: {scenario}"))?;
    let report = evaluate_runtime_risk(&request);
    write_runtime_risk_artifacts(artifact_dir, &request, &report)
        .map_err(|err| format!("failed to write strategy health artifacts: {err}"))?;

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
        "triggered_control_ids={}",
        report.triggered_control_ids.join(",")
    );
    println!("explanation={}", report.explanation);
    Ok(())
}

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_flag(args, "--scenario")?;
    let artifact_dir = PathBuf::from(parse_flag(args, "--artifact-dir")?);
    emit_report(scenario, &artifact_dir)
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

    use super::emit_report;

    #[test]
    fn scenario_sweep_emits_strategy_health_states() {
        let artifact_root = PathBuf::from(
            env::var("STRATEGY_HEALTH_SMOKE_ARTIFACT_ROOT").unwrap_or_else(|_| {
                env::temp_dir()
                    .join("backtesting_engine_opsd_strategy_health_smoke_tests")
                    .display()
                    .to_string()
            }),
        );

        for scenario in [
            "behavior-drift-restrict",
            "behavior-drift-exit-only",
            "data-quality-halt",
            "operating-envelope-fit-restrict",
            "operating-envelope-fit-flatten",
            "recalibration-required-restrict",
        ] {
            let artifact_dir = artifact_root.join(scenario);
            emit_report(scenario, &artifact_dir)
                .expect("strategy-health smoke artifacts must write");
        }
    }
}
