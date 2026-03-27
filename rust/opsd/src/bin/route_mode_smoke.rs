#![allow(unused_crate_dependencies)]

#[path = "../route_mode.rs"]
mod route_mode;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use route_mode::{evaluate_route_mode, sample_route_mode_request, write_route_mode_artifacts};

fn usage() -> &'static str {
    "usage: route_mode_smoke --scenario <paper-route-reroutes-submit|shadow-live-suppresses-submit|paper-route-falls-back-to-suppression|shadow-live-duplicate-dedupes|live-adjacent-readiness-blocked> --artifact-dir <dir>"
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
    let request = sample_route_mode_request(scenario)
        .ok_or_else(|| format!("unknown route-mode scenario: {scenario}"))?;
    let report = evaluate_route_mode(&request);
    write_route_mode_artifacts(&artifact_dir, &request, &report)
        .map_err(|err| format!("failed to write route-mode artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("route_mode={}", report.route_mode.as_str());
    println!("outcome={}", report.outcome.as_str());
    println!("reason_code={}", report.reason_code);
    println!("route_target={}", report.route_target);
    println!(
        "economic_mutation_permitted={}",
        report.economic_mutation_permitted
    );
    println!("duplicate_prevented={}", report.duplicate_prevented);
    println!("retained_artifact_id={}", report.retained_artifact_id);
    println!("artifact_count={}", report.retained_artifact_ids.len());
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

    use super::route_mode::{
        evaluate_route_mode, sample_route_mode_request, write_route_mode_artifacts,
    };

    fn safe_tmp_root() -> PathBuf {
        let shm_root = Path::new("/dev/shm");
        if shm_root.exists() {
            shm_root.join("backtesting_engine_route_mode_smoke_tests")
        } else {
            env::temp_dir().join("backtesting_engine_route_mode_smoke_tests")
        }
    }

    #[test]
    fn scenario_sweep_emits_route_decisions() {
        let artifact_root = PathBuf::from(
            env::var("ROUTE_MODE_SMOKE_ARTIFACT_ROOT")
                .unwrap_or_else(|_| safe_tmp_root().display().to_string()),
        );

        for scenario in [
            "paper-route-reroutes-submit",
            "shadow-live-suppresses-submit",
            "paper-route-falls-back-to-suppression",
            "shadow-live-duplicate-dedupes",
            "live-adjacent-readiness-blocked",
        ] {
            let request =
                sample_route_mode_request(scenario).expect("scenario must exist for smoke");
            let report = evaluate_route_mode(&request);
            let artifact_dir = artifact_root.join(scenario);
            write_route_mode_artifacts(&artifact_dir, &request, &report)
                .expect("route-mode smoke artifacts must write");

            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("route_mode={}", report.route_mode.as_str());
            println!("outcome={}", report.outcome.as_str());
            println!("reason_code={}", report.reason_code);
            println!("route_target={}", report.route_target);
            println!(
                "economic_mutation_permitted={}",
                report.economic_mutation_permitted
            );
            println!("duplicate_prevented={}", report.duplicate_prevented);
        }
    }
}
