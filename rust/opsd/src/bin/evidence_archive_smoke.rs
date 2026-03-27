#[path = "../evidence_archive.rs"]
mod evidence_archive;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use evidence_archive::{
    EvidenceArchiveQuery, EvidenceSealRequest, OperationalArtifactClass, query_archive,
    seal_evidence_bundle,
};

fn usage() -> &'static str {
    "usage:
  evidence_archive_smoke seal --source-root <dir> --archive-root <dir> --evidence-id <id> --artifact-class <paper|shadow_live|replay|broker_session|recovery|parity|drift|post_session_review> --candidate-id <id> --deployment-instance-id <id> --session-id <id> [--drill-id <id>] --retention-class <id> --operator-summary <text>
  evidence_archive_smoke query --archive-root <dir> [--artifact-class <class>] [--candidate-id <id>] [--deployment-instance-id <id>] [--session-id <id>] [--drill-id <id>]"
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

fn optional_flag(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|arg| arg == flag)
        .and_then(|index| args.get(index + 1))
        .cloned()
}

fn run_seal(args: &[String]) -> Result<(), String> {
    let artifact_class = OperationalArtifactClass::parse(parse_flag(args, "--artifact-class")?)
        .ok_or_else(|| "invalid --artifact-class".to_string())?;
    let request = EvidenceSealRequest {
        evidence_id: parse_flag(args, "--evidence-id")?.to_string(),
        artifact_class,
        candidate_id: parse_flag(args, "--candidate-id")?.to_string(),
        deployment_instance_id: parse_flag(args, "--deployment-instance-id")?.to_string(),
        session_id: parse_flag(args, "--session-id")?.to_string(),
        drill_id: optional_flag(args, "--drill-id"),
        retention_class: parse_flag(args, "--retention-class")?.to_string(),
        operator_summary: parse_flag(args, "--operator-summary")?.to_string(),
        source_root: PathBuf::from(parse_flag(args, "--source-root")?),
    };
    let archive_root = PathBuf::from(parse_flag(args, "--archive-root")?);
    let manifest = seal_evidence_bundle(&request, &archive_root)?;

    println!("command=seal");
    println!("status=pass");
    println!("entry_id={}", manifest.entry_id);
    println!("manifest_id={}", manifest.manifest_id);
    println!("retained_artifact_id={}", manifest.retained_artifact_id);
    println!("evidence_id={}", manifest.evidence_id);
    println!("artifact_class={}", manifest.artifact_class);
    println!("candidate_id={}", manifest.candidate_id);
    println!("deployment_instance_id={}", manifest.deployment_instance_id);
    println!("session_id={}", manifest.session_id);
    println!("drill_id={}", manifest.drill_id.unwrap_or_default());
    println!("artifact_count={}", manifest.artifacts.len());
    Ok(())
}

fn run_query(args: &[String]) -> Result<(), String> {
    let archive_root = PathBuf::from(parse_flag(args, "--archive-root")?);
    let results = query_archive(
        &archive_root,
        &EvidenceArchiveQuery {
            artifact_class: optional_flag(args, "--artifact-class"),
            candidate_id: optional_flag(args, "--candidate-id"),
            deployment_instance_id: optional_flag(args, "--deployment-instance-id"),
            session_id: optional_flag(args, "--session-id"),
            drill_id: optional_flag(args, "--drill-id"),
        },
    )?;

    println!("command=query");
    println!("status=pass");
    println!("match_count={}", results.len());
    println!(
        "matched_evidence_ids={}",
        results
            .iter()
            .map(|manifest| manifest.evidence_id.clone())
            .collect::<Vec<_>>()
            .join(",")
    );
    println!(
        "matched_manifest_ids={}",
        results
            .iter()
            .map(|manifest| manifest.manifest_id.clone())
            .collect::<Vec<_>>()
            .join(",")
    );
    println!(
        "matched_entry_ids={}",
        results
            .iter()
            .map(|manifest| manifest.entry_id.clone())
            .collect::<Vec<_>>()
            .join(",")
    );
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let Some((command, rest)) = args.split_first() else {
        eprintln!("{}", usage());
        return ExitCode::from(2);
    };
    let result = match command.as_str() {
        "seal" => run_seal(rest),
        "query" => run_query(rest),
        _ => Err(format!("unknown command: {command}")),
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            eprintln!("{}", usage());
            ExitCode::from(2)
        }
    }
}
