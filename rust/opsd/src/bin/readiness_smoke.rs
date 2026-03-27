#![allow(unused_crate_dependencies)]

#[path = "../readiness.rs"]
mod readiness;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use readiness::{
    assemble_session_readiness_packet, sample_session_readiness_request,
    write_session_readiness_artifacts,
};

fn usage() -> &'static str {
    "usage: readiness_smoke --scenario <green-readiness-pass|clock-stale-blocked|broker-state-blocked|reconciliation-review-required|missing-secret-provider-invalid> --artifact-dir <dir>"
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
    let request = sample_session_readiness_request(scenario)
        .ok_or_else(|| format!("unknown readiness scenario: {scenario}"))?;
    let packet = assemble_session_readiness_packet(&request);
    write_session_readiness_artifacts(&artifact_dir, &request, &packet)
        .map_err(|err| format!("failed to write readiness artifacts: {err}"))?;

    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("status={}", packet.status.as_str());
    println!("reason_code={}", packet.reason_code);
    println!("packet_digest={}", packet.packet_digest);
    println!(
        "blocked_provider_count={}",
        packet.blocked_provider_ids.len()
    );
    println!(
        "suspect_provider_count={}",
        packet.suspect_provider_ids.len()
    );
    println!(
        "missing_required_provider_count={}",
        packet.missing_required_provider_kinds.len()
    );
    if !packet.blocked_provider_ids.is_empty() {
        println!(
            "blocked_provider_ids={}",
            packet.blocked_provider_ids.join(",")
        );
    }
    if !packet.suspect_provider_ids.is_empty() {
        println!(
            "suspect_provider_ids={}",
            packet.suspect_provider_ids.join(",")
        );
    }
    if !packet.missing_required_provider_kinds.is_empty() {
        println!(
            "missing_required_provider_kinds={}",
            packet.missing_required_provider_kinds.join(",")
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
    use std::path::{Path, PathBuf};

    use super::readiness::{
        assemble_session_readiness_packet, sample_session_readiness_request,
        write_session_readiness_artifacts,
    };

    fn safe_tmp_root() -> PathBuf {
        let shm_root = Path::new("/dev/shm");
        if shm_root.exists() {
            shm_root.join("backtesting_engine_opsd_readiness_smoke_tests")
        } else {
            env::temp_dir().join("backtesting_engine_opsd_readiness_smoke_tests")
        }
    }

    #[test]
    fn scenario_sweep_emits_readiness_states() {
        let artifact_root = PathBuf::from(
            env::var("READINESS_SMOKE_ARTIFACT_ROOT")
                .unwrap_or_else(|_| safe_tmp_root().display().to_string()),
        );

        for scenario in [
            "green-readiness-pass",
            "clock-stale-blocked",
            "broker-state-blocked",
            "reconciliation-review-required",
            "missing-secret-provider-invalid",
        ] {
            let request = sample_session_readiness_request(scenario)
                .expect("scenario must exist for readiness smoke");
            let packet = assemble_session_readiness_packet(&request);
            let artifact_dir = artifact_root.join(scenario);
            write_session_readiness_artifacts(&artifact_dir, &request, &packet)
                .expect("readiness smoke artifacts must write");

            println!("scenario={scenario}");
            println!("artifact_dir={}", artifact_dir.display());
            println!("status={}", packet.status.as_str());
            println!("reason_code={}", packet.reason_code);
            println!("packet_digest={}", packet.packet_digest);
            println!(
                "blocked_provider_count={}",
                packet.blocked_provider_ids.len()
            );
            println!(
                "suspect_provider_count={}",
                packet.suspect_provider_ids.len()
            );
            println!(
                "missing_required_provider_count={}",
                packet.missing_required_provider_kinds.len()
            );
        }
    }
}
