from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.phase_25_vertical_slice_gate import (
    VALIDATION_ERRORS,
    Phase25VerticalSliceHarnessReport,
    Phase25VerticalSliceGateReport,
    Phase25VerticalSliceGateRequest,
    evaluate_phase_25_vertical_slice_gate,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "phase_25_vertical_slice_gate_cases.json"
)


def load_fixture() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(
            f"phase 2.5 gate fixture failed to load: {exc}"
        ) from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_request(case: dict[str, object]) -> Phase25VerticalSliceGateRequest:
    fixture = load_fixture()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), dict(case["overrides"]))
    payload["case_id"] = case["case_id"]
    return Phase25VerticalSliceGateRequest.from_dict(payload)


class Phase25VerticalSliceGateContractTests(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_serialization_preserves_payload(self) -> None:
        case = load_fixture()["cases"][0]
        request = build_request(case)
        self.assertEqual(request, Phase25VerticalSliceGateRequest.from_json(request.to_json()))

    def test_report_round_trip_preserves_payload(self) -> None:
        case = load_fixture()["cases"][0]
        report = evaluate_phase_25_vertical_slice_gate(build_request(case))
        self.assertEqual(report, Phase25VerticalSliceGateReport.from_json(report.to_json()))

    def test_request_loader_rejects_fail_open_boundary_values(self) -> None:
        case = load_fixture()["cases"][0]
        payload = deep_merge(
            dict(load_fixture()["shared_request_defaults"]),
            dict(case["overrides"]),
        )
        payload["case_id"] = case["case_id"]

        invalid_runtime = deep_merge(
            payload,
            {
                "runtime_evidence": {
                    "broker_reconnect_observed": "true",
                }
            },
        )
        with self.assertRaisesRegex(ValueError, "broker_reconnect_observed"):
            Phase25VerticalSliceGateRequest.from_dict(invalid_runtime)

        invalid_notes = deep_merge(
            payload,
            {
                "operator_notes": "note-1",
            },
        )
        with self.assertRaisesRegex(ValueError, "operator_notes"):
            Phase25VerticalSliceGateRequest.from_dict(invalid_notes)

    def test_nested_report_loader_rejects_missing_logs_and_bad_timestamp(self) -> None:
        harness_payload = dict(load_fixture()["shared_request_defaults"]["vertical_slice_report"])
        harness_payload.pop("retained_logs")
        with self.assertRaisesRegex(ValueError, "retained_logs"):
            Phase25VerticalSliceHarnessReport.from_dict(harness_payload)

        bad_timestamp_payload = dict(load_fixture()["shared_request_defaults"]["vertical_slice_report"])
        bad_timestamp_payload["timestamp"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "timestamp"):
            Phase25VerticalSliceHarnessReport.from_dict(bad_timestamp_payload)

        missing_schema_payload = dict(load_fixture()["shared_request_defaults"]["vertical_slice_report"])
        missing_schema_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version field is required"):
            Phase25VerticalSliceHarnessReport.from_dict(missing_schema_payload)

    def test_fixture_cases_emit_expected_statuses(self) -> None:
        for case in load_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_phase_25_vertical_slice_gate(build_request(case))
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

    def test_pass_report_is_structured_and_operator_readable(self) -> None:
        case = next(
            case
            for case in load_fixture()["cases"]
            if case["case_id"] == "phase_25_passes_cleanly"
        )
        report = evaluate_phase_25_vertical_slice_gate(build_request(case))
        payload = report.to_dict()

        self.assertEqual("phase_2_5", report.phase_gate)
        self.assertTrue(
            {
                "schema_version",
                "case_id",
                "phase_gate",
                "status",
                "reason_code",
                "scenario_decision",
                "scenario_reason_code",
                "correlation_id",
                "run_id",
                "decision_trace",
                "expected_vs_actual_diffs",
                "retained_artifact_ids",
                "operator_reason_bundle",
                "context",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("scripts/opsd_vertical_slice_smoke.py", report.retained_artifact_ids)
        self.assertIn(
            "artifact/opsd_vertical_slice_manifest.json",
            report.retained_artifact_ids,
        )
        self.assertEqual([], report.context["missing_surfaces"])
        self.assertEqual(
            "PHASE_25_VERTICAL_SLICE_PASS",
            report.operator_reason_bundle["gate_summary"]["reason_code"],
        )

    def test_runtime_gap_case_records_runtime_diff(self) -> None:
        case = next(
            case
            for case in load_fixture()["cases"]
            if case["case_id"] == "phase_25_pivots_on_missing_runtime_evidence"
        )
        report = evaluate_phase_25_vertical_slice_gate(build_request(case))

        self.assertEqual("pivot", report.status)
        self.assertTrue(
            any(
                diff["subject"] == "session_reset_observation"
                for diff in report.expected_vs_actual_diffs
            )
        )

    def test_report_loader_rejects_invalid_status_and_malformed_trace(self) -> None:
        case = load_fixture()["cases"][0]
        report_payload = evaluate_phase_25_vertical_slice_gate(build_request(case)).to_dict()

        invalid_status = dict(report_payload)
        invalid_status["status"] = "green"
        with self.assertRaisesRegex(ValueError, "status"):
            Phase25VerticalSliceGateReport.from_dict(invalid_status)

        invalid_trace = dict(report_payload)
        invalid_trace["decision_trace"] = "not-a-list"
        with self.assertRaisesRegex(ValueError, "decision_trace"):
            Phase25VerticalSliceGateReport.from_dict(invalid_trace)

        invalid_request = deep_merge(
            dict(load_fixture()["shared_request_defaults"]),
            dict(case["overrides"]),
        )
        invalid_request["case_id"] = case["case_id"]
        invalid_request.pop("runtime_evidence")
        with self.assertRaisesRegex(ValueError, "runtime_evidence field is required"):
            Phase25VerticalSliceGateRequest.from_dict(invalid_request)

        missing_context = dict(report_payload)
        missing_context.pop("context")
        with self.assertRaisesRegex(ValueError, "context field is required"):
            Phase25VerticalSliceGateReport.from_dict(missing_context)


if __name__ == "__main__":
    unittest.main()
