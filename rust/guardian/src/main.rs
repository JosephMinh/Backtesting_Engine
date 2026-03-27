use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use backtesting_engine_guardian::{
    EmergencyController, sample_emergency_action_request, sample_guardian_connectivity_report,
    write_emergency_artifacts,
};

fn usage() -> &'static str {
    "usage: cargo run -p backtesting-engine-guardian -- emergency-drill <authorized-flatten|duplicate-cancel|missing-auth|impaired-connectivity> --artifact-dir <dir>"
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

fn connectivity_scenario_for_drill(scenario: &str) -> &'static str {
    match scenario {
        "impaired-connectivity" => "impaired-connectivity",
        _ => "healthy",
    }
}

fn request_scenario_for_drill(scenario: &str) -> &'static str {
    match scenario {
        "duplicate-cancel" => "duplicate-cancel",
        "missing-auth" => "missing-auth",
        _ => "authorized-flatten",
    }
}

fn run(args: &[String]) -> Result<(), String> {
    if args.len() < 4 || args[0] != "emergency-drill" {
        return Err(usage().to_string());
    }

    let scenario = args[1].as_str();
    let artifact_dir = parse_artifact_dir(args)?;
    let request = sample_emergency_action_request(request_scenario_for_drill(scenario))
        .ok_or_else(|| format!("unknown guardian drill scenario: {scenario}"))?;
    let connectivity =
        sample_guardian_connectivity_report(connectivity_scenario_for_drill(scenario))
            .ok_or_else(|| format!("unknown guardian connectivity scenario: {scenario}"))?;

    let mut controller = EmergencyController::new();
    let evidence = controller.execute(&request, &connectivity);
    write_emergency_artifacts(&artifact_dir, &request, &connectivity, &evidence)
        .map_err(|err| format!("failed to write guardian artifacts: {err}"))?;

    println!("command=emergency-drill");
    println!("scenario={scenario}");
    println!("artifact_dir={}", artifact_dir.display());
    println!("action={}", request.action.as_str());
    println!("disposition={}", evidence.disposition.as_str());
    println!("reason_code={}", evidence.reason_code);
    println!("duplicate_invocation={}", evidence.duplicate_invocation);
    println!("operator_summary={}", evidence.operator_summary);
    Ok(())
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
