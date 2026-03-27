#[path = "../bar_builder.rs"]
mod bar_builder;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use bar_builder::{build_live_bar, sample_live_bar_request, write_live_bar_artifacts};

fn usage() -> &'static str {
    "usage: live_bar_smoke --scenario <tradeable-pass|reset-boundary-reject|delayed-entitlement-reject|quote-fallback-zero-volume|parity-degraded> --artifact-dir <dir>"
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

fn parse_scenario(args: &[String]) -> Result<&str, String> {
    let Some(flag_index) = args.iter().position(|arg| arg == "--scenario") else {
        return Err("missing --scenario".to_string());
    };
    let Some(scenario) = args.get(flag_index + 1) else {
        return Err("missing scenario value".to_string());
    };
    Ok(scenario.as_str())
}

fn run(args: &[String]) -> Result<(), String> {
    let scenario = parse_scenario(args)?;
    let artifact_dir = parse_artifact_dir(args)?;
    let request = sample_live_bar_request(scenario)
        .ok_or_else(|| format!("unknown live-bar scenario: {scenario}"))?;
    let report = build_live_bar(&request);
    write_live_bar_artifacts(&artifact_dir, &request, &report)
        .map_err(|err| format!("failed to write live-bar artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("status={}", report.status.as_str());
    println!("reason_code={}", report.reason_code);
    println!("market_data_fresh={}", report.market_data_fresh);
    println!("stale_quote_rate_bps={}", report.stale_quote_rate_bps);
    println!("parity_healthy={}", report.parity_healthy);
    println!("normalized_update_count={}", report.normalized_update_count);
    println!("rejected_update_count={}", report.rejected_update_ids.len());
    println!(
        "degraded_reason_count={}",
        report.degraded_reason_codes.len()
    );
    if let Some(bar) = report.bar.as_ref() {
        println!("bar_source={}", bar.source.as_str());
        println!("bar_close={}", bar.close);
        println!("bar_volume={}", bar.volume);
        println!("bar_zero_volume_flag={}", bar.zero_volume_flag);
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
