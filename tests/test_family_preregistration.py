from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.family_preregistration import (
    CONTINUATION_CHECK_IDS,
    PREREGISTRATION_CHECK_IDS,
    VALIDATION_ERRORS,
    FamilyBudgetDecisionReport,
    FamilyBudgetDecisionRequest,
    FamilyGovernanceStatus,
    FamilyPreregistrationReport,
    StrategyFamilyPreregistration,
    evaluate_family_budget_decision,
    validate_family_preregistration,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "family_preregistration_cases.json"
)


def load_cases() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_preregistration(
    overrides: dict[str, Any] | None = None,
) -> StrategyFamilyPreregistration:
    fixture = load_cases()
    payload = deep_merge(
        dict(fixture["shared_preregistration_defaults"]),
        overrides or {},
    )
    return StrategyFamilyPreregistration.from_dict(payload)


def build_budget_request(
    overrides: dict[str, Any] | None = None,
) -> FamilyBudgetDecisionRequest:
    fixture = load_cases()
    payload = deep_merge(
        dict(fixture["shared_budget_request_defaults"]),
        overrides or {},
    )
    return FamilyBudgetDecisionRequest.from_dict(payload)


class FamilyPreregistrationCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


class FamilyPreregistrationFixtureTests(unittest.TestCase):
    def test_preregistration_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["preregistration_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = validate_family_preregistration(
                    build_preregistration(case["overrides"])
                )
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_check_ids"]),
                    report.triggered_check_ids,
                )

    def test_preregistration_report_traces_every_check_in_catalog_order(self) -> None:
        report = validate_family_preregistration(build_preregistration())

        self.assertEqual(len(PREREGISTRATION_CHECK_IDS), len(report.check_results))
        self.assertEqual(
            PREREGISTRATION_CHECK_IDS,
            tuple(result.check_id for result in report.check_results),
        )

    def test_preregistration_report_round_trip_preserves_shape(self) -> None:
        report = validate_family_preregistration(build_preregistration())
        reparsed = FamilyPreregistrationReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)


class FamilyBudgetDecisionFixtureTests(unittest.TestCase):
    def test_budget_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["budget_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_family_budget_decision(
                    build_budget_request(case["overrides"])
                )
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_check_ids"]),
                    report.triggered_check_ids,
                )
                self.assertEqual(
                    expected["deep_budget_requested"],
                    report.deep_budget_requested,
                )
                self.assertEqual(
                    expected["viability_gate_required"],
                    report.viability_gate_required,
                )
                self.assertEqual(
                    expected["viability_gate_passed"],
                    report.viability_gate_passed,
                )

    def test_budget_report_traces_every_check_in_catalog_order(self) -> None:
        report = evaluate_family_budget_decision(build_budget_request())

        self.assertEqual(len(CONTINUATION_CHECK_IDS), len(report.check_results))
        self.assertEqual(
            CONTINUATION_CHECK_IDS,
            tuple(result.check_id for result in report.check_results),
        )

    def test_deep_budget_failure_emits_guardrail_trace(self) -> None:
        report = evaluate_family_budget_decision(
            build_budget_request({"viability_reference": None})
        )

        self.assertEqual(FamilyGovernanceStatus.VIOLATION.value, report.status)
        self.assertIsNotNone(report.guardrail_trace)
        guardrail_trace = report.guardrail_trace
        if guardrail_trace is None:
            self.fail("missing guardrail trace for deep-budget viability failure")
        self.assertEqual(
            "GUARDRAIL_P13_PREMATURE_BUDGET_ALLOCATION",
            guardrail_trace["reason_code"],
        )
        self.assertFalse(guardrail_trace["passed"])

    def test_metric_reference_must_be_preregistered(self) -> None:
        report = evaluate_family_budget_decision(
            build_budget_request(
                {
                    "evidence_summary": {
                        "metric_references": ["unknown_metric"]
                    }
                }
            )
        )

        self.assertEqual(FamilyGovernanceStatus.INVALID.value, report.status)
        self.assertEqual(
            "FAMILY_CONTINUATION_STRUCTURED_SUMMARY_INVALID",
            report.reason_code,
        )
        self.assertEqual(
            ("structured_evidence_and_economics",),
            report.triggered_check_ids,
        )

    def test_budget_report_round_trip_preserves_shape(self) -> None:
        report = evaluate_family_budget_decision(build_budget_request())
        reparsed = FamilyBudgetDecisionReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)


class FamilyPreregistrationJsonValidationTests(unittest.TestCase):
    def test_request_json_must_decode_to_object(self) -> None:
        with self.assertRaises(ValueError):
            FamilyBudgetDecisionRequest.from_json("[]")

    def test_report_json_must_decode_to_object(self) -> None:
        with self.assertRaises(ValueError):
            FamilyBudgetDecisionReport.from_json("[]")


if __name__ == "__main__":
    unittest.main()
