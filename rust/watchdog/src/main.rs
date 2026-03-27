use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use backtesting_engine_watchdog::{
    evaluate_clock_health, evaluate_supervision_bundle, execute_migration,
    sample_activation_preflight_inputs, sample_clock_health_observation, sample_migration_request,
    sample_restore_request, sample_secret_health_observation, sample_supervision_bundle,
    verify_restore_execution, write_activation_preflight_artifacts, write_clock_health_artifacts,
    write_migration_artifacts, write_restore_artifacts, write_secret_health_artifacts,
    write_supervision_artifacts,
};

fn usage() -> &'static str {
    "usage: cargo run -p backtesting-engine-watchdog -- <restore-drill|execute-migration|clock-health|secret-health|activation-preflight|supervision-drill> <scenario> --artifact-dir <dir>"
}

fn parse_artifact_dir(args: &[String]) -> Result<PathBuf, String> {
    let Some(flag_index) = args.iter().position(|arg| arg == "--artifact-dir") else {
        return Err("missing --artifact-dir".to_string());
    };
    let Some(dir) = args.get(flag_index + 1) else {
        return Err("missing artifact directory value".to_string());
    };
    Ok(PathBuf::from(dir))
}

fn run(args: &[String]) -> Result<(), String> {
    if args.len() < 4 {
        return Err(usage().to_string());
    }

    let artifact_dir = parse_artifact_dir(args)?;
    match (args[0].as_str(), args[1].as_str()) {
        ("restore-drill", scenario) => {
            let request = sample_restore_request(scenario)
                .ok_or_else(|| format!("unknown restore scenario: {scenario}"))?;
            let report = verify_restore_execution(&request);
            write_restore_artifacts(&artifact_dir, &request, &report)
                .map_err(|err| format!("failed to write restore artifacts: {err}"))?;
            println!("command=restore-drill");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("disposition={}", report.disposition.as_str());
            println!("reason_code={}", report.reason_code);
            println!(
                "verified_frontier_digest={}",
                report.verified_frontier_digest
            );
            println!("backup_age_minutes={}", report.backup_age_minutes);
            println!("explanation={}", report.explanation);
            Ok(())
        }
        ("execute-migration", scenario) => {
            let request = sample_migration_request(scenario)
                .ok_or_else(|| format!("unknown migration scenario: {scenario}"))?;
            let report = execute_migration(&request);
            write_migration_artifacts(&artifact_dir, &request, &report)
                .map_err(|err| format!("failed to write migration artifacts: {err}"))?;
            println!("command=execute-migration");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("status={}", report.status.as_str());
            println!("reason_code={}", report.reason_code);
            println!("safe_halt_required={}", report.safe_halt_required);
            println!("applied_steps={}", report.applied_steps.len());
            println!("explanation={}", report.explanation);
            Ok(())
        }
        ("clock-health", scenario) => {
            let observation = sample_clock_health_observation(scenario)
                .ok_or_else(|| format!("unknown clock-health scenario: {scenario}"))?;
            let report = evaluate_clock_health(&observation);
            write_clock_health_artifacts(&artifact_dir, &observation, &report)
                .map_err(|err| format!("failed to write clock-health artifacts: {err}"))?;
            println!("command=clock-health");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("state={}", report.state.as_str());
            println!("reason_code={}", report.reason_code);
            println!("measured_skew_ms={}", report.measured_skew_ms);
            println!("operator_summary={}", report.operator_summary);
            Ok(())
        }
        ("secret-health", scenario) => {
            let observation = sample_secret_health_observation(scenario)
                .ok_or_else(|| format!("unknown secret-health scenario: {scenario}"))?;
            let report = backtesting_engine_watchdog::evaluate_secret_health(&observation);
            write_secret_health_artifacts(&artifact_dir, &observation, &report)
                .map_err(|err| format!("failed to write secret-health artifacts: {err}"))?;
            println!("command=secret-health");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("state={}", report.state.as_str());
            println!("reason_code={}", report.reason_code);
            println!("delivery_surface={}", report.delivery_surface.as_str());
            println!("operator_summary={}", report.operator_summary);
            Ok(())
        }
        ("activation-preflight", scenario) => {
            let (clock_report, secret_report, backup_report, restore_report, summary) =
                sample_activation_preflight_inputs(scenario)
                    .ok_or_else(|| format!("unknown activation-preflight scenario: {scenario}"))?;
            write_activation_preflight_artifacts(
                &artifact_dir,
                &clock_report,
                &secret_report,
                &backup_report,
                &restore_report,
                &summary,
            )
            .map_err(|err| format!("failed to write activation-preflight artifacts: {err}"))?;
            println!("command=activation-preflight");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("state={}", summary.state.as_str());
            println!("reason_code={}", summary.reason_code);
            println!("failed_check_count={}", summary.failed_check_ids.len());
            println!("warning_check_count={}", summary.warning_check_ids.len());
            println!("operator_summary={}", summary.operator_summary);
            Ok(())
        }
        ("supervision-drill", scenario) => {
            let bundle = sample_supervision_bundle(scenario)
                .ok_or_else(|| format!("unknown supervision-drill scenario: {scenario}"))?;
            let report = evaluate_supervision_bundle(&bundle);
            write_supervision_artifacts(&artifact_dir, &bundle, &report)
                .map_err(|err| format!("failed to write supervision artifacts: {err}"))?;
            println!("command=supervision-drill");
            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("state={}", report.state.as_str());
            println!("reason_code={}", report.reason_code);
            println!("restarted_target_count={}", report.restarted_targets.len());
            println!(
                "quarantined_target_count={}",
                report.quarantined_targets.len()
            );
            println!("operator_summary={}", report.operator_summary);
            Ok(())
        }
        _ => Err(usage().to_string()),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            ExitCode::from(2)
        }
    }
}
