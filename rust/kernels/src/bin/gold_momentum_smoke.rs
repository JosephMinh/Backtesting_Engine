use std::path::PathBuf;
use std::process::ExitCode;

use backtesting_engine_kernels::{default_fixture_path, load_fixture_cases, run_fixture_case};

fn main() -> ExitCode {
    let mut case_id = String::from("gold_momentum_promotable");
    let mut fixture_path = default_fixture_path();
    let mut output_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/kernel-smoke");

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--case-id" => {
                let Some(value) = args.next() else {
                    eprintln!("--case-id requires a value");
                    return ExitCode::FAILURE;
                };
                case_id = value;
            }
            "--fixture-path" => {
                let Some(value) = args.next() else {
                    eprintln!("--fixture-path requires a value");
                    return ExitCode::FAILURE;
                };
                fixture_path = PathBuf::from(value);
            }
            "--output-dir" => {
                let Some(value) = args.next() else {
                    eprintln!("--output-dir requires a value");
                    return ExitCode::FAILURE;
                };
                output_dir = PathBuf::from(value);
            }
            other => {
                eprintln!("unexpected argument: {other}");
                return ExitCode::FAILURE;
            }
        }
    }

    let cases = match load_fixture_cases(&fixture_path) {
        Ok(cases) => cases,
        Err(err) => {
            eprintln!("failed to load fixture cases: {err:?}");
            return ExitCode::FAILURE;
        }
    };
    let Some(case) = cases.iter().find(|item| item.case_id == case_id) else {
        eprintln!("fixture case not found: {case_id}");
        return ExitCode::FAILURE;
    };

    let report = match run_fixture_case(case, &output_dir) {
        Ok(report) => report,
        Err(err) => {
            eprintln!("fixture run failed: {err:?}");
            return ExitCode::FAILURE;
        }
    };

    println!("Gold momentum kernel smoke summary");
    println!("case_id: {}", report.case_id);
    println!("identity_digest: {}", report.identity_digest);
    println!(
        "candidate_bundle: {}",
        report.artifact_binding.candidate_bundle.relative_path()
    );
    println!(
        "resolved_context_bundle: {}",
        report
            .artifact_binding
            .resolved_context_bundle
            .relative_path()
    );
    println!(
        "signal_kernel: {}",
        report.artifact_binding.signal_kernel.relative_path()
    );
    println!("decision_count: {}", report.actual.len());
    for record in &report.log_records {
        println!("[{}] {} {}", record.level, record.event, record.message);
    }
    if let Some(path) = &report.mismatch_artifact_path {
        println!("mismatch_artifact: {}", path.display());
    }

    if report.succeeded() {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}
