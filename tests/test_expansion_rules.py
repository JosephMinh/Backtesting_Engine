"""Contract tests for the post-v1 expansion rules."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - smoke test intentionally executes a trusted repo-local script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.expansion_rules import (
    REQUIRED_RULE_IDS,
    RULE_REQUIREMENTS,
    VALIDATION_ERRORS,
    ExpansionRulesReport,
    evaluate_expansion_rules_case,
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
    / "expansion_rules_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "expansion_rules_smoke.py"
)


def load_fixture() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"expansion rules fixture failed to load: {exc}") from exc


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} must decode to a JSON object")
    return decoded


class ExpansionRulesContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_fixture_cases_emit_expected_outcomes(self) -> None:
        for case in load_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_expansion_rules_case(case["case_id"])
                self.assertEqual(case["expected"]["status"], report.status)
                self.assertEqual(case["expected"]["reason_code"], report.reason_code)

    def test_pass_case_covers_all_plan_expansion_rules(self) -> None:
        report = evaluate_expansion_rules_case("approve_all_post_v1_expansion_rules")

        self.assertEqual(set(REQUIRED_RULE_IDS), set(report.requested_rule_ids))
        self.assertEqual(set(REQUIRED_RULE_IDS), set(report.approved_rule_ids))
        self.assertEqual((), report.blocked_rule_ids)
        self.assertEqual({}, report.missing_requirement_ids)

    def test_missing_continuation_review_blocks_all_requested_expansion(self) -> None:
        report = evaluate_expansion_rules_case("block_without_continuation_review")

        self.assertEqual("violation", report.status)
        self.assertEqual(set(REQUIRED_RULE_IDS), set(report.blocked_rule_ids))
        self.assertEqual(
            {"continuation_review_approval"},
            {item for values in report.missing_requirement_ids.values() for item in values},
        )

    def test_missing_rule_specific_evidence_is_reported(self) -> None:
        report = evaluate_expansion_rules_case(
            "block_multiple_bundles_without_economic_justification"
        )

        self.assertEqual("violation", report.status)
        self.assertIn("multiple_active_live_bundles", report.blocked_rule_ids)
        self.assertEqual(
            ("economic_justification_proven",),
            report.missing_requirement_ids["multiple_active_live_bundles"],
        )
        self.assertEqual(
            RULE_REQUIREMENTS["multiple_active_live_bundles"],
            (
                "single_bundle_stability_proven",
                "economic_justification_proven",
            ),
        )

    def test_bead_103_is_mapped_into_shared_phase_9_profile(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.10.3" in profile.related_beads
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

    def test_phase_9_gate_bead_911_declares_continuation_review_workflow(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.9.11" in profile.related_beads
        ]

        self.assertEqual(1, len(matching))
        self.assertEqual(
            "phase_9_continuation_review_and_scope_governance_gate",
            matching[0].surface_id,
        )
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

    def test_roundtrip_preserves_report(self) -> None:
        report = evaluate_expansion_rules_case("approve_all_post_v1_expansion_rules")
        reparsed = ExpansionRulesReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.approved_rule_ids, reparsed.approved_rule_ids)
        self.assertEqual(report.operator_reason_bundle, reparsed.operator_reason_bundle)

    def test_smoke_script_emits_selected_case_and_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted repo-local script
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "approve_all_post_v1_expansion_rules",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = decode_json_object(result.stdout, label="smoke script stdout")
            self.assertEqual("approve_all_post_v1_expansion_rules", parsed["case_id"])
            self.assertEqual("pass", parsed["status"])
            self.assertEqual("EXPANSION_RULES_APPROVED", parsed["reason_code"])
            written = Path(output_dir) / "approve_all_post_v1_expansion_rules.json"
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="smoke script report",
            )
            self.assertEqual("EXPANSION_RULES_APPROVED", written_report["reason_code"])


if __name__ == "__main__":
    unittest.main()
