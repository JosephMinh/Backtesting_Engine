from __future__ import annotations

import json
import subprocess  # nosec B404 - smoke test intentionally executes a trusted repo-local script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.execution_lane_scenarios import (
    ExecutionLaneScenarioRequest,
    evaluate_execution_lane_scenario,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "execution_lane_scenarios_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "execution_lane_scenarios_smoke.py"
)


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} was not valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} did not decode to an object")
    return decoded


def load_fixture() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"execution lane scenario fixture failed to load: {exc}") from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_request(case: dict[str, object]) -> ExecutionLaneScenarioRequest:
    fixture = load_fixture()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), dict(case["overrides"]))
    payload["case_id"] = case["case_id"]
    return ExecutionLaneScenarioRequest.from_dict(payload)


class ExecutionLaneScenarioContractTests(unittest.TestCase):
    def test_request_round_trip_serialization_preserves_payload(self) -> None:
        case = load_fixture()["cases"][0]
        request = build_request(case)
        self.assertEqual(request, ExecutionLaneScenarioRequest.from_json(request.to_json()))

    def test_fixture_cases_emit_expected_decisions(self) -> None:
        for case in load_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_execution_lane_scenario(build_request(case))
                payload = report.to_dict()

                self.assertEqual(case["expected_decision"], report.decision)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                if report.vertical_slice_report is not None:
                    self.assertEqual(
                        case["expected_vertical_slice_reason_code"],
                        report.vertical_slice_report["viability_gate"]["reason_code"],
                    )
                if report.calibration_report is not None:
                    self.assertEqual(
                        case["expected_certification_reason_code"],
                        report.calibration_report["portability_and_native_validation"]["reason_code"],
                    )
                    self.assertEqual(
                        case["expected_fidelity_reason_code"],
                        report.calibration_report["fidelity_calibration"]["reason_code"],
                    )
                self.assertEqual(payload["case_id"], case["case_id"])
                self.assertTrue(payload["decision_trace"])

    def test_report_includes_required_manifest_and_log_contracts(self) -> None:
        case = next(
            case
            for case in load_fixture()["cases"]
            if case["case_id"] == "calibration_passes_with_portability_and_fidelity"
        )
        report = evaluate_execution_lane_scenario(build_request(case)).to_dict()

        manifest = report["artifact_manifest"]
        self.assertTrue(
            {
                "manifest_id",
                "generated_at_utc",
                "retention_class",
                "contains_secrets",
                "redaction_policy",
                "artifacts",
            }.issubset(manifest.keys())
        )
        self.assertGreaterEqual(len(manifest["artifacts"]), 3)
        for artifact in manifest["artifacts"]:
            self.assertTrue(
                {
                    "artifact_id",
                    "artifact_role",
                    "relative_path",
                    "sha256",
                    "content_type",
                }.issubset(artifact.keys())
            )

        self.assertGreaterEqual(len(report["structured_logs"]), 3)
        for record in report["structured_logs"]:
            self.assertTrue(
                {
                    "schema_version",
                    "event_type",
                    "plane",
                    "event_id",
                    "recorded_at_utc",
                    "correlation_id",
                    "decision_trace_id",
                    "reason_code",
                    "reason_summary",
                    "referenced_ids",
                    "redacted_fields",
                    "omitted_fields",
                    "artifact_manifest",
                }.issubset(record.keys())
            )

        self.assertTrue(
            {
                "summary",
                "gate_summary",
                "rule_trace",
                "remediation_hints",
            }.issubset(report["operator_reason_bundle"].keys())
        )

    def test_smoke_script_emits_selected_case_and_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted test harness invocation
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "vertical_slice_passes_cleanly",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = decode_json_object(result.stdout, label="smoke script stdout")
            self.assertEqual(1, len(parsed["reports"]))
            self.assertEqual(
                "vertical_slice_passes_cleanly",
                parsed["reports"][0]["case_id"],
            )
            written = Path(output_dir) / "vertical_slice_passes_cleanly.json"
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="smoke script report",
            )
            self.assertEqual(
                "EXECUTION_LANE_VERTICAL_SLICE_PASS",
                written_report["reason_code"],
            )


if __name__ == "__main__":
    unittest.main()
