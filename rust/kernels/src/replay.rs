use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};

use crate::{
    BarInput, GoldMomentumKernel, KernelArtifactBinding, SignalDecision, SignalDisposition,
};

/// Expected decision from a replay fixture case.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FixtureDecision {
    pub sequence_number: u64,
    pub disposition: SignalDisposition,
    pub score_ticks: i64,
}

/// One executable replay fixture for the canonical gold-momentum kernel.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReplayFixtureCase {
    pub case_id: String,
    pub lookback_bars: usize,
    pub threshold_ticks: i64,
    pub candidate_bundle: String,
    pub resolved_context_bundle: String,
    pub signal_kernel: String,
    pub closes: Vec<i64>,
    pub expected: Vec<FixtureDecision>,
}

/// Parse or execution failures for fixture-backed replay harnesses.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum FixtureLoadError {
    Io(String),
    MissingField(&'static str),
    InvalidNumber { field: &'static str, value: String },
    InvalidDisposition(String),
    InvalidExpectedEntry(String),
    InvalidCaseSeparator,
    EmptyFixtureSet,
}

/// One retained expected-vs-actual mismatch.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SmokeDiff {
    pub sequence_number: u64,
    pub expected_disposition: SignalDisposition,
    pub actual_disposition: Option<SignalDisposition>,
    pub expected_score_ticks: i64,
    pub actual_score_ticks: Option<i64>,
}

/// Human-readable but structured smoke log output.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SmokeLogRecord {
    pub level: &'static str,
    pub event: &'static str,
    pub message: String,
}

/// Result of running a replay fixture through the real artifact-loading path.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SmokeReport {
    pub case_id: String,
    pub identity_digest: String,
    pub artifact_binding: KernelArtifactBinding,
    pub actual: Vec<SignalDecision>,
    pub diffs: Vec<SmokeDiff>,
    pub log_records: Vec<SmokeLogRecord>,
    pub mismatch_artifact_path: Option<PathBuf>,
}

impl SmokeReport {
    pub fn succeeded(&self) -> bool {
        self.diffs.is_empty()
    }
}

pub fn default_fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fixtures/gold_momentum_replay_cases.txt")
}

pub fn load_fixture_cases(path: &Path) -> Result<Vec<ReplayFixtureCase>, FixtureLoadError> {
    let text = fs::read_to_string(path)
        .map_err(|err| FixtureLoadError::Io(format!("{}: {err}", path.display())))?;
    let mut cases = Vec::new();
    for block in text.split("\n\n") {
        let block = block.trim();
        if block.is_empty() || block.starts_with('#') {
            continue;
        }
        cases.push(parse_case_block(block)?);
    }
    if cases.is_empty() {
        Err(FixtureLoadError::EmptyFixtureSet)
    } else {
        Ok(cases)
    }
}

pub fn run_fixture_case(
    case: &ReplayFixtureCase,
    output_dir: &Path,
) -> Result<SmokeReport, FixtureLoadError> {
    let artifact_binding = GoldMomentumKernel::binding(
        case.candidate_bundle.clone(),
        case.resolved_context_bundle.clone(),
        case.signal_kernel.clone(),
    )
    .map_err(|err| FixtureLoadError::Io(format!("artifact binding failed: {err:?}")))?;

    let inputs = case
        .closes
        .iter()
        .enumerate()
        .map(|(index, close_ticks)| BarInput {
            sequence_number: (index + 1) as u64,
            close_ticks: *close_ticks,
        })
        .collect::<Vec<_>>();
    let actual =
        GoldMomentumKernel::evaluate_series(case.lookback_bars, case.threshold_ticks, &inputs);
    let diffs = compare_expected(case, &actual);

    let mut log_records = vec![
        SmokeLogRecord {
            level: "INFO",
            event: "kernel_fixture_loaded",
            message: format!(
                "loaded case {} with {} closes through {}",
                case.case_id,
                case.closes.len(),
                default_fixture_path().display()
            ),
        },
        SmokeLogRecord {
            level: "INFO",
            event: "kernel_identity_bound",
            message: format!(
                "digest={} bundle={} replay={} kernel={}",
                artifact_binding.identity.canonical_digest(),
                artifact_binding.candidate_bundle.relative_path(),
                artifact_binding.resolved_context_bundle.relative_path(),
                artifact_binding.signal_kernel.relative_path(),
            ),
        },
    ];

    let mismatch_artifact_path = if diffs.is_empty() {
        log_records.push(SmokeLogRecord {
            level: "INFO",
            event: "kernel_fixture_passed",
            message: format!(
                "case {} produced {} deterministic decisions",
                case.case_id,
                actual.len()
            ),
        });
        None
    } else {
        fs::create_dir_all(output_dir)
            .map_err(|err| FixtureLoadError::Io(format!("{}: {err}", output_dir.display())))?;
        let path = output_dir.join(format!("{}_expected_vs_actual.json", case.case_id));
        let payload = render_diff_payload(case, &artifact_binding, &actual, &diffs);
        fs::write(&path, payload)
            .map_err(|err| FixtureLoadError::Io(format!("{}: {err}", path.display())))?;
        log_records.push(SmokeLogRecord {
            level: "ERROR",
            event: "kernel_fixture_mismatch",
            message: format!(
                "case {} diverged on {} decision(s); diff artifact written to {}",
                case.case_id,
                diffs.len(),
                path.display()
            ),
        });
        Some(path)
    };

    Ok(SmokeReport {
        case_id: case.case_id.clone(),
        identity_digest: artifact_binding.identity.canonical_digest(),
        artifact_binding,
        actual,
        diffs,
        log_records,
        mismatch_artifact_path,
    })
}

pub fn render_smoke_report_json(report: &SmokeReport) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    push_json_line(
        &mut output,
        1,
        "entry_path",
        "rust.bin.gold_momentum_smoke",
        true,
    );
    push_json_line(&mut output, 1, "case_id", &report.case_id, true);
    push_json_line(
        &mut output,
        1,
        "identity_digest",
        &report.identity_digest,
        true,
    );
    output.push_str("  \"identity\": {\n");
    push_json_line(
        &mut output,
        2,
        "strategy_family_id",
        report.artifact_binding.identity.strategy_family_id,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "rust_crate",
        report.artifact_binding.identity.rust_crate,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "python_binding_module",
        report.artifact_binding.identity.python_binding_module,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "kernel_abi_version",
        report.artifact_binding.identity.kernel_abi_version,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "state_serialization_version",
        report.artifact_binding.identity.state_serialization_version,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "semantic_version",
        report.artifact_binding.identity.semantic_version,
        true,
    );
    push_json_line(
        &mut output,
        2,
        "canonical_digest",
        &report.identity_digest,
        false,
    );
    output.push_str("  },\n");
    push_json_line(
        &mut output,
        1,
        "candidate_bundle",
        report.artifact_binding.candidate_bundle.relative_path(),
        true,
    );
    push_json_line(
        &mut output,
        1,
        "resolved_context_bundle",
        report
            .artifact_binding
            .resolved_context_bundle
            .relative_path(),
        true,
    );
    push_json_line(
        &mut output,
        1,
        "signal_kernel",
        report.artifact_binding.signal_kernel.relative_path(),
        true,
    );
    output.push_str("  \"actual\": [\n");
    for (index, decision) in report.actual.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"sequence_number\": {}, \"disposition\": \"{}\", \"score_ticks\": {}",
            decision.sequence_number,
            decision.disposition.as_str(),
            decision.score_ticks,
        );
        output.push('}');
        if index + 1 != report.actual.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ],\n");
    output.push_str("  \"diffs\": [\n");
    for (index, diff) in report.diffs.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"sequence_number\": {}, \"expected_disposition\": \"{}\", \"actual_disposition\": {}, \"expected_score_ticks\": {}, \"actual_score_ticks\": {}",
            diff.sequence_number,
            diff.expected_disposition.as_str(),
            diff.actual_disposition
                .map(|item| format!("\"{}\"", item.as_str()))
                .unwrap_or_else(|| "null".to_owned()),
            diff.expected_score_ticks,
            diff.actual_score_ticks
                .map(|item| item.to_string())
                .unwrap_or_else(|| "null".to_owned()),
        );
        output.push('}');
        if index + 1 != report.diffs.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ],\n");
    output.push_str("  \"log_records\": [\n");
    for (index, record) in report.log_records.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"level\": \"{}\", \"event\": \"{}\", \"message\": \"{}\"",
            record.level,
            record.event,
            escape_json(&record.message),
        );
        output.push('}');
        if index + 1 != report.log_records.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ],\n");
    match &report.mismatch_artifact_path {
        Some(path) => push_json_line(
            &mut output,
            1,
            "mismatch_artifact_path",
            &path.display().to_string(),
            false,
        ),
        None => output.push_str("  \"mismatch_artifact_path\": null\n"),
    }
    output.push_str("}\n");
    output
}

fn parse_case_block(block: &str) -> Result<ReplayFixtureCase, FixtureLoadError> {
    let mut case_id = None;
    let mut lookback_bars = None;
    let mut threshold_ticks = None;
    let mut candidate_bundle = None;
    let mut resolved_context_bundle = None;
    let mut signal_kernel = None;
    let mut closes = None;
    let mut expected = None;

    for line in block.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            return Err(FixtureLoadError::InvalidCaseSeparator);
        };
        let value = value.trim();
        match key.trim() {
            "case_id" => case_id = Some(value.to_owned()),
            "lookback_bars" => {
                lookback_bars =
                    Some(
                        value
                            .parse::<usize>()
                            .map_err(|_| FixtureLoadError::InvalidNumber {
                                field: "lookback_bars",
                                value: value.to_owned(),
                            })?,
                    )
            }
            "threshold_ticks" => {
                threshold_ticks =
                    Some(
                        value
                            .parse::<i64>()
                            .map_err(|_| FixtureLoadError::InvalidNumber {
                                field: "threshold_ticks",
                                value: value.to_owned(),
                            })?,
                    )
            }
            "candidate_bundle" => candidate_bundle = Some(value.to_owned()),
            "resolved_context_bundle" => resolved_context_bundle = Some(value.to_owned()),
            "signal_kernel" => signal_kernel = Some(value.to_owned()),
            "closes" => closes = Some(parse_i64_list("closes", value)?),
            "expected" => expected = Some(parse_expected(value)?),
            _ => {}
        }
    }

    Ok(ReplayFixtureCase {
        case_id: case_id.ok_or(FixtureLoadError::MissingField("case_id"))?,
        lookback_bars: lookback_bars.ok_or(FixtureLoadError::MissingField("lookback_bars"))?,
        threshold_ticks: threshold_ticks
            .ok_or(FixtureLoadError::MissingField("threshold_ticks"))?,
        candidate_bundle: candidate_bundle
            .ok_or(FixtureLoadError::MissingField("candidate_bundle"))?,
        resolved_context_bundle: resolved_context_bundle
            .ok_or(FixtureLoadError::MissingField("resolved_context_bundle"))?,
        signal_kernel: signal_kernel.ok_or(FixtureLoadError::MissingField("signal_kernel"))?,
        closes: closes.ok_or(FixtureLoadError::MissingField("closes"))?,
        expected: expected.ok_or(FixtureLoadError::MissingField("expected"))?,
    })
}

fn parse_i64_list(field: &'static str, value: &str) -> Result<Vec<i64>, FixtureLoadError> {
    value
        .split(',')
        .map(|item| {
            let item = item.trim();
            item.parse::<i64>()
                .map_err(|_| FixtureLoadError::InvalidNumber {
                    field,
                    value: item.to_owned(),
                })
        })
        .collect()
}

fn parse_expected(value: &str) -> Result<Vec<FixtureDecision>, FixtureLoadError> {
    value
        .split(';')
        .filter(|item| !item.trim().is_empty())
        .map(|item| {
            let mut parts = item.trim().split(':');
            let Some(sequence_number) = parts.next() else {
                return Err(FixtureLoadError::InvalidExpectedEntry(item.to_owned()));
            };
            let Some(disposition) = parts.next() else {
                return Err(FixtureLoadError::InvalidExpectedEntry(item.to_owned()));
            };
            let Some(score_ticks) = parts.next() else {
                return Err(FixtureLoadError::InvalidExpectedEntry(item.to_owned()));
            };
            if parts.next().is_some() {
                return Err(FixtureLoadError::InvalidExpectedEntry(item.to_owned()));
            }
            let sequence_number = sequence_number
                .parse::<u64>()
                .map_err(|_| FixtureLoadError::InvalidExpectedEntry(item.to_owned()))?;
            let disposition = SignalDisposition::parse(disposition)
                .ok_or_else(|| FixtureLoadError::InvalidDisposition(disposition.to_owned()))?;
            let score_ticks = score_ticks
                .parse::<i64>()
                .map_err(|_| FixtureLoadError::InvalidExpectedEntry(item.to_owned()))?;
            Ok(FixtureDecision {
                sequence_number,
                disposition,
                score_ticks,
            })
        })
        .collect()
}

fn compare_expected(case: &ReplayFixtureCase, actual: &[SignalDecision]) -> Vec<SmokeDiff> {
    let mut diffs = Vec::new();
    let len = case.expected.len().max(actual.len());
    for index in 0..len {
        let expected = case.expected.get(index);
        let actual = actual.get(index);
        let mismatch = match (expected, actual) {
            (Some(expected), Some(actual)) => {
                expected.sequence_number != actual.sequence_number
                    || expected.disposition != actual.disposition
                    || expected.score_ticks != actual.score_ticks
            }
            _ => true,
        };
        if mismatch {
            diffs.push(SmokeDiff {
                sequence_number: expected
                    .map(|item| item.sequence_number)
                    .or_else(|| actual.map(|item| item.sequence_number))
                    .unwrap_or(0),
                expected_disposition: expected
                    .map(|item| item.disposition)
                    .unwrap_or(SignalDisposition::Flat),
                actual_disposition: actual.map(|item| item.disposition),
                expected_score_ticks: expected.map(|item| item.score_ticks).unwrap_or_default(),
                actual_score_ticks: actual.map(|item| item.score_ticks),
            });
        }
    }
    diffs
}

fn render_diff_payload(
    case: &ReplayFixtureCase,
    artifact_binding: &KernelArtifactBinding,
    actual: &[SignalDecision],
    diffs: &[SmokeDiff],
) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    push_json_line(&mut output, 1, "case_id", &case.case_id, true);
    push_json_line(
        &mut output,
        1,
        "identity_digest",
        &artifact_binding.identity.canonical_digest(),
        true,
    );
    push_json_line(
        &mut output,
        1,
        "candidate_bundle",
        artifact_binding.candidate_bundle.relative_path(),
        true,
    );
    push_json_line(
        &mut output,
        1,
        "resolved_context_bundle",
        artifact_binding.resolved_context_bundle.relative_path(),
        true,
    );
    push_json_line(
        &mut output,
        1,
        "signal_kernel",
        artifact_binding.signal_kernel.relative_path(),
        true,
    );
    output.push_str("  \"expected\": [\n");
    for (index, decision) in case.expected.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"sequence_number\": {}, \"disposition\": \"{}\", \"score_ticks\": {}",
            decision.sequence_number,
            decision.disposition.as_str(),
            decision.score_ticks,
        );
        output.push('}');
        if index + 1 != case.expected.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ],\n");
    output.push_str("  \"actual\": [\n");
    for (index, decision) in actual.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"sequence_number\": {}, \"disposition\": \"{}\", \"score_ticks\": {}",
            decision.sequence_number,
            decision.disposition.as_str(),
            decision.score_ticks,
        );
        output.push('}');
        if index + 1 != actual.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ],\n");
    output.push_str("  \"diffs\": [\n");
    for (index, diff) in diffs.iter().enumerate() {
        output.push_str("    {");
        let _ = write!(
            output,
            "\"sequence_number\": {}, \"expected_disposition\": \"{}\", \"actual_disposition\": {}, \"expected_score_ticks\": {}, \"actual_score_ticks\": {}",
            diff.sequence_number,
            diff.expected_disposition.as_str(),
            diff.actual_disposition
                .map(|item| format!("\"{}\"", item.as_str()))
                .unwrap_or_else(|| "null".to_owned()),
            diff.expected_score_ticks,
            diff.actual_score_ticks
                .map(|item| item.to_string())
                .unwrap_or_else(|| "null".to_owned()),
        );
        output.push('}');
        if index + 1 != diffs.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n");
    output.push_str("}\n");
    output
}

fn push_json_line(
    output: &mut String,
    indent: usize,
    key: &str,
    value: &str,
    trailing_comma: bool,
) {
    let indent = "  ".repeat(indent);
    let _ = write!(
        output,
        "{indent}\"{}\": \"{}\"",
        key,
        value.replace('\\', "\\\\").replace('"', "\\\""),
    );
    if trailing_comma {
        output.push(',');
    }
    output.push('\n');
}

fn escape_json(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

#[cfg(test)]
mod tests {
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::{SignalDisposition, default_fixture_path, load_fixture_cases, run_fixture_case};

    #[test]
    fn fixture_cases_load_from_disk() {
        let cases = load_fixture_cases(&default_fixture_path()).expect("fixtures should parse");
        assert_eq!(2, cases.len());
        assert_eq!("gold_momentum_promotable", cases[0].case_id);
    }

    #[test]
    fn mismatch_artifact_is_retained_for_divergence() {
        let mut cases = load_fixture_cases(&default_fixture_path()).expect("fixtures should parse");
        let case = cases
            .iter_mut()
            .find(|item| item.case_id == "gold_momentum_promotable")
            .expect("fixture case should exist");
        case.expected[0].disposition = SignalDisposition::Flat;
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time should advance")
            .as_nanos();
        let output_dir =
            std::env::temp_dir().join(format!("backtesting_engine_kernel_mismatch_{unique}"));
        let report = run_fixture_case(case, &output_dir).expect("fixture run should succeed");
        assert!(!report.succeeded());
        let path = report
            .mismatch_artifact_path
            .expect("mismatch artifact should be written");
        let payload = std::fs::read_to_string(path).expect("artifact should be readable");
        assert!(payload.contains("\"case_id\": \"gold_momentum_promotable\""));
        assert!(payload.contains("\"diffs\""));
    }
}
