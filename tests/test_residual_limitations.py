"""Contract tests for the residual-limitations register."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - smoke test intentionally executes a trusted repo-local script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.residual_limitations import (
    REQUIRED_DECISION_SURFACES,
    REQUIRED_LIMITATION_IDS,
    VALIDATION_ERRORS,
    ResidualLimitationsRegisterReport,
    evaluate_residual_limitations_case,
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
    / "residual_limitations_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "residual_limitations_smoke.py"
)


def load_fixture() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"residual limitations fixture failed to load: {exc}") from exc


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} must decode to a JSON object")
    return decoded


class ResidualLimitationsContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_fixture_cases_emit_expected_outcomes(self) -> None:
        for case in load_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_residual_limitations_case(case["case_id"])
                self.assertEqual(case["expected"]["status"], report.status)
                self.assertEqual(case["expected"]["reason_code"], report.reason_code)

    def test_complete_case_covers_all_plan_limitations_and_surfaces(self) -> None:
        report = evaluate_residual_limitations_case("explicit_register_is_complete")

        self.assertEqual(set(REQUIRED_LIMITATION_IDS), set(report.covered_limitation_ids))
        self.assertEqual({}, report.decision_surface_gaps)
        self.assertEqual((), report.nonobjective_limitation_ids)
        self.assertEqual((), report.missing_guardrail_ids)
        self.assertEqual((), report.missing_limitation_ids)
        self.assertEqual(
            set(REQUIRED_DECISION_SURFACES),
            set(report.operator_reason_bundle["decision_surfaces_required"]),
        )

    def test_bead_102_is_mapped_into_shared_phase_9_profile(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.10.2" in profile.related_beads
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

    def test_missing_required_limitation_is_reported(self) -> None:
        report = evaluate_residual_limitations_case("missing_single_host_limit")

        self.assertEqual("violation", report.status)
        self.assertIn(
            "single_host_infrastructure_concentration",
            report.missing_limitation_ids,
        )

    def test_missing_decision_surface_is_reported(self) -> None:
        report = evaluate_residual_limitations_case(
            "liquidity_limit_missing_continuation_surface"
        )

        self.assertEqual("violation", report.status)
        self.assertEqual(
            ("continuation_review",),
            report.decision_surface_gaps["one_oz_liquidity_heterogeneity"],
        )

    def test_nonobjective_acceptance_is_reported(self) -> None:
        report = evaluate_residual_limitations_case("capital_limit_not_objective_bound")

        self.assertEqual("violation", report.status)
        self.assertIn("live_capital_posture_limit", report.nonobjective_limitation_ids)

    def test_roundtrip_preserves_report(self) -> None:
        report = evaluate_residual_limitations_case("explicit_register_is_complete")
        reparsed = ResidualLimitationsRegisterReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.covered_limitation_ids, reparsed.covered_limitation_ids)
        self.assertEqual(report.operator_reason_bundle, reparsed.operator_reason_bundle)

    def test_smoke_script_emits_selected_case_and_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted repo-local script
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "explicit_register_is_complete",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = decode_json_object(result.stdout, label="smoke script stdout")
            self.assertEqual("explicit_register_is_complete", parsed["case_id"])
            self.assertEqual("pass", parsed["status"])
            self.assertEqual(
                "RESIDUAL_LIMITATIONS_REGISTER_COMPLETE",
                parsed["reason_code"],
            )
            written = Path(output_dir) / "explicit_register_is_complete.json"
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="smoke script report",
            )
            self.assertEqual(
                "RESIDUAL_LIMITATIONS_REGISTER_COMPLETE",
                written_report["reason_code"],
            )


if __name__ == "__main__":
    unittest.main()
