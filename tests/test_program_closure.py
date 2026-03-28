from __future__ import annotations

import json
import subprocess  # nosec B404 - trusted repo-local smoke script
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.program_closure import (
    ProgramClosureAction,
    ProgramClosureDecision,
    ProgramClosureReport,
    ProgramClosureRequest,
    evaluate_program_closure_case,
    load_program_closure_fixture,
    validate_program_closure_contract,
)

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "program_closure_smoke.py"
)


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} was not valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} did not decode to an object")
    return decoded


class ProgramClosureContractTests(unittest.TestCase):
    def test_contract_validator_has_no_errors(self) -> None:
        self.assertEqual([], validate_program_closure_contract())

    def test_fixture_cases_emit_expected_governed_decisions(self) -> None:
        for case in load_program_closure_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_program_closure_case(case["case_id"])
                expected = case["expected"]

                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["recommended_action"], report.recommended_action)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_rule_ids"]),
                    report.triggered_rule_ids,
                )

    def test_report_round_trip_preserves_trigger_reports(self) -> None:
        report = evaluate_program_closure_case(
            "remain_paper_only_when_operational_friction_dominates_edge"
        )
        self.assertEqual(
            report.to_dict(),
            ProgramClosureReport.from_json(report.to_json()).to_dict(),
        )

    def test_continue_case_preserves_evidence_bundle_and_clear_decision(self) -> None:
        report = evaluate_program_closure_case(
            "continue_when_all_program_closure_checks_clear"
        )

        self.assertEqual(ProgramClosureDecision.CONTINUE.value, report.decision)
        self.assertEqual(
            ProgramClosureAction.CONTINUE_CURRENT_LANE.value,
            report.recommended_action,
        )
        self.assertEqual((), report.triggered_rule_ids)
        self.assertIn("tradability_report_id", report.source_evidence_ids)
        self.assertIn("runtime_report_id", report.source_evidence_ids)
        self.assertTrue(report.retained_artifact_ids)
        self.assertIn("approved operator-time and capital posture", report.operator_rationale)

    def test_termination_case_retains_multiple_trigger_ids(self) -> None:
        report = evaluate_program_closure_case(
            "terminate_when_tradability_and_economics_fail_together"
        )

        self.assertEqual(ProgramClosureDecision.TERMINATE.value, report.decision)
        self.assertEqual(
            ProgramClosureAction.TERMINATE_PROGRAM.value,
            report.recommended_action,
        )
        self.assertEqual(
            (
                "program_closure.execution_symbol_tradability",
                "program_closure.de_minimis_economics",
            ),
            report.triggered_rule_ids,
        )
        self.assertIn("termination", report.operator_rationale.lower())

    def test_smoke_script_runs_selected_case_and_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted repo-local smoke script
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "raise_capital_when_posture_requirements_exceed_current_lane",
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
                "raise_capital_when_posture_requirements_exceed_current_lane",
                parsed["reports"][0]["case_id"],
            )
            written = (
                Path(output_dir)
                / "raise_capital_when_posture_requirements_exceed_current_lane.json"
            )
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="smoke report",
            )
            self.assertEqual("pivot", written_report["decision"])
            self.assertEqual(
                "PROGRAM_CLOSURE_POSTURE_RAISE_CAPITAL",
                written_report["reason_code"],
            )

    def test_request_loader_rejects_invalid_boundary_values(self) -> None:
        fixture = load_program_closure_fixture()
        base_payload = deepcopy(fixture["shared_request_defaults"])
        case_payload = deepcopy(fixture["cases"][0])
        base_payload["case_id"] = case_payload["case_id"]
        base_payload.setdefault("review_id", f"program_closure_{case_payload['case_id']}")
        for key, value in case_payload.get("overrides", {}).items():
            base_payload[key] = deepcopy(value)
        invalid_cases = (
            (
                "tradability_truthy_string",
                lambda payload: payload.__setitem__("tradability_verified", "true"),
                "tradability_verified: must be boolean",
            ),
            (
                "approved_live_capital_bool",
                lambda payload: payload.__setitem__("approved_live_capital_usd", True),
                "approved_live_capital_usd: must be numeric",
            ),
            (
                "approved_live_capital_nan",
                lambda payload: payload.__setitem__("approved_live_capital_usd", "nan"),
                "approved_live_capital_usd: must be finite",
            ),
            (
                "case_id_bool",
                lambda payload: payload.__setitem__("case_id", False),
                "case_id: must be a non-empty string",
            ),
            (
                "schema_version_bool",
                lambda payload: payload.__setitem__("schema_version", True),
                "schema_version: must be an integer",
            ),
            (
                "schema_version_unsupported",
                lambda payload: payload.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
            (
                "retained_artifact_ids_string",
                lambda payload: payload.__setitem__("retained_artifact_ids", "artifact-1"),
                "retained_artifact_ids: must be a list of strings",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    ProgramClosureRequest.from_dict(payload)

    def test_report_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = evaluate_program_closure_case(
            "continue_when_all_program_closure_checks_clear"
        ).to_dict()
        invalid_cases = (
            (
                "decision_invalid",
                lambda payload: payload.__setitem__("decision", "ship"),
                "decision: must be a valid program closure decision",
            ),
            (
                "recommended_action_invalid",
                lambda payload: payload.__setitem__("recommended_action", "ship_now"),
                "recommended_action: must be a valid program closure action",
            ),
            (
                "trigger_reports_string",
                lambda payload: payload.__setitem__("trigger_reports", "report"),
                "trigger_reports: must be a list of objects",
            ),
            (
                "trigger_id_invalid",
                lambda payload: payload["trigger_reports"][0].__setitem__("trigger_id", "bad"),
                "trigger_id: must be a valid program closure trigger id",
            ),
            (
                "timestamp_naive",
                lambda payload: payload.__setitem__("timestamp", "2026-03-28T00:00:00"),
                "timestamp: must be timezone-aware",
            ),
            (
                "schema_version_bool",
                lambda payload: payload.__setitem__("schema_version", False),
                "schema_version: must be an integer",
            ),
            (
                "schema_version_unsupported",
                lambda payload: payload.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    ProgramClosureReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
