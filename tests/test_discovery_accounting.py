from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.discovery_accounting import (
    DISCOVERY_ACCOUNTING_CHECK_IDS,
    REQUIRED_NULL_MODEL_IDS,
    VALIDATION_ERRORS,
    DiscoveryAccountingReport,
    DiscoveryAccountingRequest,
    DiscoveryAccountingStatus,
    evaluate_discovery_accounting,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "discovery_accounting_cases.json"
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


def build_request(overrides: dict[str, Any] | None = None) -> DiscoveryAccountingRequest:
    fixture = load_cases()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), overrides or {})
    return DiscoveryAccountingRequest.from_dict(payload)


class DiscoveryAccountingCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_required_null_models_match_plan_minimum(self) -> None:
        self.assertEqual(
            (
                "random_entry",
                "time_shifted_anchor",
                "side_flipped_or_ablated",
                "permutation",
                "regime_conditional",
            ),
            REQUIRED_NULL_MODEL_IDS,
        )


class DiscoveryAccountingFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_discovery_accounting(build_request(case["overrides"]))
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_check_ids"]),
                    report.triggered_check_ids,
                )

                if "family_total_spend_usd" in expected:
                    self.assertEqual(
                        expected["family_total_spend_usd"],
                        report.family_total_spend_usd,
                    )
                if "program_total_spend_usd" in expected:
                    self.assertEqual(
                        expected["program_total_spend_usd"],
                        report.program_total_spend_usd,
                    )
                if "remaining_exploratory_budget_usd" in expected:
                    self.assertEqual(
                        expected["remaining_exploratory_budget_usd"],
                        report.remaining_exploratory_budget_usd,
                    )
                if "completed_null_model_ids" in expected:
                    self.assertEqual(
                        tuple(expected["completed_null_model_ids"]),
                        report.completed_null_model_ids,
                    )

    def test_report_traces_every_check_in_catalog_order(self) -> None:
        report = evaluate_discovery_accounting(build_request())

        self.assertEqual(
            len(DISCOVERY_ACCOUNTING_CHECK_IDS),
            len(report.check_results),
        )
        self.assertEqual(
            DISCOVERY_ACCOUNTING_CHECK_IDS,
            tuple(result.check_id for result in report.check_results),
        )

    def test_round_trip_preserves_report_shape(self) -> None:
        report = evaluate_discovery_accounting(build_request())
        reparsed = DiscoveryAccountingReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)


class DiscoveryAccountingEdgeCaseTests(unittest.TestCase):
    def test_hidden_optimization_guardrail_is_emitted_for_missing_nulls(self) -> None:
        fixture = load_cases()
        case = next(
            case
            for case in fixture["evaluation_cases"]
            if case["case_id"] == "missing_required_null_family_blocks"
        )
        report = evaluate_discovery_accounting(build_request(case["overrides"]))

        self.assertEqual(DiscoveryAccountingStatus.VIOLATION.value, report.status)
        self.assertIsNotNone(report.guardrail_trace)
        if report.guardrail_trace is None:
            self.fail("missing guardrail trace for hidden optimization violation")
        self.assertEqual(
            "GUARDRAIL_P08_HIDDEN_OPTIMIZATION_SURFACE",
            report.guardrail_trace["reason_code"],
        )
        self.assertFalse(report.guardrail_trace["passed"])

    def test_continuation_record_id_is_retained_when_deeper_search_is_allowed(self) -> None:
        fixture = load_cases()
        case = next(
            case
            for case in fixture["evaluation_cases"]
            if case["case_id"] == "approved_continuation_allows_deeper_search"
        )
        report = evaluate_discovery_accounting(build_request(case["overrides"]))

        self.assertEqual("allow_with_continuation", report.decision)
        self.assertEqual(
            "family_decision_gold_breakout_continue_001",
            report.continuation_decision_record_id,
        )

    def test_request_json_must_decode_to_object(self) -> None:
        with self.assertRaises(ValueError):
            DiscoveryAccountingRequest.from_json("[]")

    def test_report_json_must_decode_to_object(self) -> None:
        with self.assertRaises(ValueError):
            DiscoveryAccountingReport.from_json("[]")


if __name__ == "__main__":
    unittest.main()
