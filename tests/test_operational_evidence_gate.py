"""Contract tests for operational-evidence admissibility and promotion exit gate."""

from __future__ import annotations

import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from shared.policy.operational_evidence_gate import (
    OperationalEvidenceGateReport,
    OperationalEvidenceGateRequest,
    PromotionTransition,
    evaluate_operational_evidence_gate,
)
from shared.policy.paper_shadow_stage_policy import (
    PaperShadowStagePolicyRequest,
    evaluate_paper_shadow_stage_policy,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "operational_evidence_gate_cases.json"
)
STAGE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "paper_shadow_stage_policy_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operational_evidence_gate_smoke.py"
)


def load_fixture(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"fixture failed to load from {path}: {exc}") from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def apply_stage_objective_mutations(
    payload: dict[str, object],
    mutations: dict[str, dict[str, dict[str, object]]],
) -> dict[str, object]:
    mutated = dict(payload)
    for field_name in ("paper_objectives", "shadow_live_objectives"):
        if field_name not in mutations:
            continue
        objective_mutations = mutations[field_name]
        updated_records = []
        for record in mutated.get(field_name, []):
            updated = dict(record)
            record_mutation = objective_mutations.get(str(updated["objective_id"]))
            if record_mutation:
                updated.update(record_mutation)
            updated_records.append(updated)
        mutated[field_name] = updated_records
    return mutated


def build_stage_policy_report(case_id: str):
    fixture = load_fixture(STAGE_FIXTURE_PATH)
    case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    payload["case_id"] = case_id
    payload = apply_stage_objective_mutations(payload, dict(case.get("objective_mutations", {})))
    request = PaperShadowStagePolicyRequest.from_dict(payload)
    return evaluate_paper_shadow_stage_policy(request)


def load_json_payload(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as payload_file:
            return json.load(payload_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"failed to load JSON payload from {path}: {exc}") from exc


def build_request(case: dict[str, object]) -> OperationalEvidenceGateRequest:
    fixture = load_fixture(FIXTURE_PATH)
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    stage_report = build_stage_policy_report(str(payload.pop("stage_policy_case_id")))
    payload["case_id"] = case["case_id"]
    payload["stage_policy_report"] = stage_report.to_dict()
    return OperationalEvidenceGateRequest.from_dict(payload)


class OperationalEvidenceGateContractTest(unittest.TestCase):
    def test_request_json_roundtrip(self) -> None:
        case = load_fixture(FIXTURE_PATH)["cases"][0]
        request = build_request(case)

        reparsed = OperationalEvidenceGateRequest.from_json(request.to_json())

        self.assertEqual(request.case_id, reparsed.case_id)
        self.assertEqual(request.requested_transition, reparsed.requested_transition)
        self.assertEqual(request.current_deployment_state, reparsed.current_deployment_state)
        self.assertEqual(
            [record.to_dict() for record in request.operational_evidence],
            [record.to_dict() for record in reparsed.operational_evidence],
        )

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_fixture(FIXTURE_PATH)["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_operational_evidence_gate(build_request(case))

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(case["expected_promotion_allowed"], report.promotion_allowed)
                if "expected_target_state" in case:
                    self.assertEqual(case["expected_target_state"], report.approved_target_state)
                if "expected_blocked_evidence_id" in case:
                    self.assertIn(
                        case["expected_blocked_evidence_id"], report.blocked_evidence_ids
                    )
                if "expected_failed_criterion" in case:
                    self.assertIn(
                        case["expected_failed_criterion"],
                        report.context["failed_criteria"],
                    )

    def test_report_includes_required_artifacts_logs_and_reason_bundle(self) -> None:
        case = next(
            case
            for case in load_fixture(FIXTURE_PATH)["cases"]
            if case["case_id"] == "allow_shadow_live_to_live_canary_after_shadow_review"
        )
        report = evaluate_operational_evidence_gate(build_request(case)).to_dict()

        self.assertEqual(
            PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY.value,
            report["requested_transition"],
        )
        self.assertTrue(
            {
                "manifest_id",
                "generated_at_utc",
                "retention_class",
                "contains_secrets",
                "redaction_policy",
                "artifacts",
            }.issubset(report["artifact_manifest"].keys())
        )
        self.assertTrue(
            {
                "gate_summary",
                "stage_policy",
                "operational_evidence",
                "criteria",
                "operator_notes",
            }.issubset(report["operator_reason_bundle"].keys())
        )
        self.assertTrue(report["decision_trace"])
        self.assertIn("shadow_ops_gate_v1", report["promotion_admissible_evidence_ids"])
        self.assertIn("artifact_shadow_ops_gate_v1", report["retained_artifact_ids"])

    def test_report_json_roundtrip(self) -> None:
        case = next(
            case
            for case in load_fixture(FIXTURE_PATH)["cases"]
            if case["case_id"] == "block_live_canary_to_live_active_without_canary_review"
        )
        report = evaluate_operational_evidence_gate(build_request(case))

        reparsed = OperationalEvidenceGateReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.requested_transition, reparsed.requested_transition)
        self.assertEqual(report.context, reparsed.context)

    def test_smoke_script_emits_selected_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "smoke.json"
            stdout = io.StringIO()
            argv = [
                str(SCRIPT_PATH),
                "--case-id",
                "allow_live_canary_to_live_active_after_review",
                "--output",
                str(output_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(stdout):
                    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

            self.assertIn("allow_live_canary_to_live_active_after_review", stdout.getvalue())
            report = load_json_payload(output_path)
            self.assertEqual("LIVE_ACTIVE", report["approved_target_state"])


if __name__ == "__main__":
    unittest.main()
