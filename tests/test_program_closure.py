from __future__ import annotations

import json
import subprocess  # nosec B404 - trusted repo-local smoke script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.program_closure import (
    ProgramClosureAction,
    ProgramClosureDecision,
    ProgramClosureReport,
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


if __name__ == "__main__":
    unittest.main()
