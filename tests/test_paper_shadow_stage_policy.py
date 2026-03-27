"""Contract tests for mandatory paper and shadow-live stage policy."""

from __future__ import annotations

import json
import io
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from shared.policy.paper_shadow_stage_policy import (
    PAPER_OBJECTIVE_SPECS,
    SHADOW_LIVE_OBJECTIVE_SPECS,
    PaperShadowStagePolicyReport,
    PaperShadowStagePolicyRequest,
    evaluate_paper_shadow_stage_policy,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "paper_shadow_stage_policy_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "paper_shadow_stage_policy_smoke.py"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"paper-shadow stage fixture failed to load: {exc}") from exc


def load_json_payload(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as payload_file:
            return json.load(payload_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"failed to load JSON payload from {path}: {exc}") from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def apply_objective_mutations(
    payload: dict[str, object],
    mutations: dict[str, dict[str, dict[str, object]]],
) -> dict[str, object]:
    mutated = dict(payload)
    for field_name in ("paper_objectives", "shadow_live_objectives"):
        if field_name not in mutations:
            continue
        objective_mutations = mutations[field_name]
        records = []
        for record in mutated.get(field_name, []):
            updated = dict(record)
            record_mutation = objective_mutations.get(str(updated["objective_id"]))
            if record_mutation:
                updated.update(record_mutation)
            records.append(updated)
        mutated[field_name] = records
    return mutated


def build_request(case: dict[str, object]) -> PaperShadowStagePolicyRequest:
    fixture = load_cases()
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    payload["case_id"] = case["case_id"]
    payload = apply_objective_mutations(payload, dict(case.get("objective_mutations", {})))
    return PaperShadowStagePolicyRequest.from_dict(payload)


class PaperShadowStagePolicyContractTest(unittest.TestCase):
    def test_request_json_roundtrip(self) -> None:
        case = load_cases()["cases"][0]
        request = build_request(case)

        reparsed = PaperShadowStagePolicyRequest.from_json(request.to_json())

        self.assertEqual(request.case_id, reparsed.case_id)
        self.assertEqual(request.requested_lane, reparsed.requested_lane)
        self.assertEqual(request.paper_pass_evidence_id, reparsed.paper_pass_evidence_id)
        self.assertEqual(
            [objective.to_dict() for objective in request.paper_objectives],
            [objective.to_dict() for objective in reparsed.paper_objectives],
        )

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_paper_shadow_stage_policy(build_request(case))

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected_requested_lane_permitted"],
                    report.requested_lane_permitted,
                )
                self.assertEqual(
                    case["expected_live_activation_permitted"],
                    report.live_activation_permitted,
                )
                self.assertEqual(
                    case["expected_paper_stage_complete"],
                    report.paper_stage_complete,
                )
                self.assertEqual(
                    case["expected_shadow_stage_complete"],
                    report.shadow_live_stage_complete,
                )
                self.assertEqual(
                    case["expected_overnight_evidence_complete"],
                    report.overnight_evidence_complete,
                )
                if "expected_diff_subject" in case:
                    self.assertTrue(
                        any(
                            diff["subject"] == case["expected_diff_subject"]
                            for diff in report.expected_vs_actual_diffs
                        )
                    )
                if "expected_missing_overnight_scenario" in case:
                    self.assertIn(
                        case["expected_missing_overnight_scenario"],
                        report.context["overnight_summary"]["missing_scenarios"],
                    )

    def test_report_includes_required_artifacts_logs_and_reason_bundle(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "allow_live_with_complete_overnight_evidence"
        )
        report = evaluate_paper_shadow_stage_policy(build_request(case)).to_dict()

        self.assertEqual(
            len(PAPER_OBJECTIVE_SPECS) + len(SHADOW_LIVE_OBJECTIVE_SPECS),
            len(report["decision_trace"]),
        )
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
        self.assertTrue(
            {
                "gate_summary",
                "paper_stage",
                "shadow_live_stage",
                "overnight",
                "operator_notes",
            }.issubset(report["operator_reason_bundle"].keys())
        )
        self.assertTrue(
            all(
                {
                    "schema_version",
                    "event_type",
                    "correlation_id",
                    "run_id",
                    "case_id",
                    "candidate_bundle_id",
                    "timestamp",
                }.issubset(entry.keys())
                for entry in report["structured_logs"]
            )
        )
        self.assertIn("paper_pass_evidence_v2", report["retained_artifact_ids"])
        self.assertIn("shadow_pass_evidence_v2", report["retained_artifact_ids"])
        self.assertIn("entitlement_check_live_20260327", report["retained_artifact_ids"])

    def test_report_json_roundtrip(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "block_live_on_failed_shadow_reconciliation"
        )
        report = evaluate_paper_shadow_stage_policy(build_request(case))

        reparsed = PaperShadowStagePolicyReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.requested_lane, reparsed.requested_lane)
        self.assertEqual(report.expected_vs_actual_diffs, reparsed.expected_vs_actual_diffs)

    def test_smoke_script_emits_selected_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "smoke.json"
            stdout = io.StringIO()
            argv = [
                str(SCRIPT_PATH),
                "--case-id",
                "allow_live_with_complete_overnight_evidence",
                "--output",
                str(output_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(stdout):
                    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

            self.assertIn("allow_live_with_complete_overnight_evidence", stdout.getvalue())
            report = load_json_payload(output_path)
            self.assertEqual(
                "PAPER_AND_SHADOW_STAGE_REQUIREMENTS_SATISFIED",
                report["reason_code"],
            )


if __name__ == "__main__":
    unittest.main()
