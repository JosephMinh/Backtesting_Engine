#[path = "../recovery.rs"]
mod recovery;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use recovery::{
    evaluate_recovery, plan_graceful_shutdown, sample_recovery_scenario, write_recovery_artifacts,
};

fn usage() -> &'static str {
    "usage: recovery_smoke --scenario <green-verified-restart|warmup-journal-hold|restart-while-holding-exit-only|daily-reset-readiness-blocked|ambiguous-journal-halt> --artifact-dir <dir>"
}

fn parse_flag<'a>(args: &'a [String], flag: &str) -> Result<&'a str, String> {
    let Some(index) = args.iter().position(|arg| arg == flag) else {
        return Err(format!("missing {flag}"));
    };
    let Some(value) = args.get(index + 1) else {
        return Err(format!("missing value for {flag}"));
    };
    Ok(value.as_str())
}

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_flag(args, "--scenario")?;
    let artifact_dir = PathBuf::from(parse_flag(args, "--artifact-dir")?);
    let (shutdown_request, recovery_request) = sample_recovery_scenario(scenario)
        .ok_or_else(|| format!("unknown recovery scenario: {scenario}"))?;
    let shutdown_artifact = plan_graceful_shutdown(&shutdown_request);
    let recovery_report = evaluate_recovery(&recovery_request);

    write_recovery_artifacts(
        &artifact_dir,
        &shutdown_request,
        &shutdown_artifact,
        &recovery_request,
        &recovery_report,
    )
    .map_err(|err| format!("failed to write recovery artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("shutdown_status={}", shutdown_artifact.status.as_str());
    println!("shutdown_reason_code={}", shutdown_artifact.reason_code);
    println!(
        "safe_restart_ready={}",
        shutdown_artifact.safe_restart_ready
    );
    println!("recovery_status={}", recovery_report.status.as_str());
    println!("recovery_reason_code={}", recovery_report.reason_code);
    println!("allow_new_entries={}", recovery_report.allow_new_entries);
    println!("exit_only={}", recovery_report.exit_only);
    println!("require_flatten={}", recovery_report.require_flatten);
    println!(
        "warmup_source={}",
        recovery_report
            .selected_warmup_source
            .map(|source| source.as_str())
            .unwrap_or("")
    );
    println!(
        "blocking_reasons={}",
        recovery_report.blocking_reasons.join(",")
    );
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
