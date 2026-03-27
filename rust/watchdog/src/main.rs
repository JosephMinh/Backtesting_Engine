use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use backtesting_engine_watchdog::{
    execute_migration, sample_migration_request, sample_restore_request, verify_restore_execution,
    write_migration_artifacts, write_restore_artifacts,
};

fn usage() -> &'static str {
    "usage: cargo run -p backtesting-engine-watchdog -- <restore-drill|execute-migration> <scenario> --artifact-dir <dir>"
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
