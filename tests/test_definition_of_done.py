"""Contract tests for the final definition-of-done gate."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - smoke test intentionally executes a trusted repo-local script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.definition_of_done import (
    ALLOWED_FINAL_OUTCOMES,
    REQUIRED_DONE_ITEM_IDS,
    REQUIRED_PHASE_GATES,
    VALIDATION_ERRORS,
    DefinitionOfDoneReport,
    evaluate_definition_of_done_case,
)
from shared.policy.verification_contract import (
    FixtureSource,
    VERIFICATION_PROFILES,
    VerificationClass,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "definition_of_done_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "definition_of_done_smoke.py"
)


def load_fixture() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"definition_of_done fixture failed to load: {exc}") from exc


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} must decode to a JSON object")
    return decoded


class DefinitionOfDoneContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_fixture_cases_emit_expected_outcomes(self) -> None:
        for case in load_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_definition_of_done_case(case["case_id"])
                self.assertEqual(case["expected"]["status"], report.status)
                self.assertEqual(case["expected"]["reason_code"], report.reason_code)

    def test_pass_case_covers_all_done_items_and_phase_gates(self) -> None:
        report = evaluate_definition_of_done_case("all_done_conditions_satisfied")

        self.assertEqual(set(REQUIRED_DONE_ITEM_IDS), set(report.satisfied_item_ids))
        self.assertEqual((), report.missing_item_ids)
        self.assertEqual((), report.missing_phase_gates)
        self.assertEqual({}, report.evidence_class_gaps)
        self.assertFalse(report.invalid_final_outcome)
        self.assertEqual("live_canary_approved", report.final_candidate_outcome)
        self.assertEqual(set(ALLOWED_FINAL_OUTCOMES), {"rejected", "live_canary_approved"})
        self.assertIn("phase_9", REQUIRED_PHASE_GATES)

    def test_bead_101_is_mapped_into_shared_phase_9_profile(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.10.1" in profile.related_beads
        ]

        self.assertEqual(1, len(matching))
        self.assertEqual("program_closure_and_continuation", matching[0].surface_id)
        self.assertEqual(("phase_9",), matching[0].phase_gates)
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.PLAN_SEEDED_FIXTURE,
            ),
            matching[0].fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            matching[0].golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), matching[0].failure_path)

    def test_missing_failure_path_coverage_is_reported(self) -> None:
        report = evaluate_definition_of_done_case("missing_failure_path_for_order_idempotency")

        self.assertEqual("violation", report.status)
        self.assertEqual(
            ("failure_path_artifact_ids",),
            report.evidence_class_gaps["order_idempotency_and_safe_ambiguity"],
        )

    def test_missing_phase_gate_and_invalid_terminal_outcome_are_reported(self) -> None:
        report = evaluate_definition_of_done_case(
            "missing_phase_9_and_invalid_terminal_outcome"
        )

        self.assertEqual("violation", report.status)
        self.assertEqual(("phase_9",), report.missing_phase_gates)
        self.assertTrue(report.invalid_final_outcome)

    def test_roundtrip_preserves_report(self) -> None:
        report = evaluate_definition_of_done_case("all_done_conditions_satisfied")
        reparsed = DefinitionOfDoneReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.satisfied_item_ids, reparsed.satisfied_item_ids)
        self.assertEqual(report.operator_reason_bundle, reparsed.operator_reason_bundle)

    def test_smoke_script_emits_selected_case_and_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted repo-local script
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "all_done_conditions_satisfied",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = decode_json_object(result.stdout, label="smoke script stdout")
            self.assertEqual("all_done_conditions_satisfied", parsed["case_id"])
            self.assertEqual("pass", parsed["status"])
            self.assertEqual("DEFINITION_OF_DONE_SATISFIED", parsed["reason_code"])
            written = Path(output_dir) / "all_done_conditions_satisfied.json"
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="smoke script report",
            )
            self.assertEqual(
                "DEFINITION_OF_DONE_SATISFIED",
                written_report["reason_code"],
            )


if __name__ == "__main__":
    unittest.main()
