"""Contract tests for selection hard gates and secondary ranking views."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.selection_hard_gates import (
    SELECTION_HARD_GATE_IDS,
    VALIDATION_ERRORS,
    SelectionHardGatesReport,
    SelectionHardGatesRequest,
    evaluate_selection_hard_gates,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "selection_hard_gates_cases.json"
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


def build_request(
    overrides: dict[str, Any] | None = None,
) -> SelectionHardGatesRequest:
    fixture = load_cases()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), overrides or {})
    return SelectionHardGatesRequest.from_dict(payload)


class SelectionHardGatesCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_gate_catalog_matches_selection_policy(self) -> None:
        self.assertEqual(
            (
                "candidate_identity_alignment",
                "after_cost_profitability",
                "null_separation",
                "robustness_omission_lockbox",
                "portability_and_tradability",
                "account_fit",
                "absolute_dollar_viability_and_benchmarks",
                "execution_symbol_pin",
                "selection_artifact_bundle",
                "ranking_is_secondary",
            ),
            SELECTION_HARD_GATE_IDS,
        )


class SelectionHardGatesFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_selection_hard_gates(build_request(case["overrides"]))
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status.value)
                self.assertEqual(expected["decision"], report.decision.value)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_gate_ids"]),
                    report.triggered_gate_ids,
                )
                self.assertEqual(
                    expected["selected_execution_symbol"],
                    report.selected_execution_symbol,
                )
                self.assertEqual(
                    expected["secondary_ranking_considered"],
                    report.secondary_ranking_considered,
                )

    def test_ranking_is_secondary_even_for_frontier_leader(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "ranking_cannot_override_absolute_dollar_reject"
        )
        report = evaluate_selection_hard_gates(build_request(case["overrides"]))

        self.assertEqual("reject", report.decision.value)
        self.assertEqual(1, report.pareto_frontier_rank)
        self.assertIn(
            "absolute_dollar_viability_and_benchmarks",
            report.triggered_gate_ids,
        )

    def test_report_round_trip_preserves_all_gate_traces(self) -> None:
        report = evaluate_selection_hard_gates(build_request())
        reparsed = SelectionHardGatesReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)

    def test_invalid_json_payloads_raise_value_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "selection_hard_gates_request: invalid JSON payload"
        ):
            SelectionHardGatesRequest.from_json("not-json")

        with self.assertRaisesRegex(
            ValueError, "selection_hard_gates_report: invalid JSON payload"
        ):
            SelectionHardGatesReport.from_json("not-json")


if __name__ == "__main__":
    unittest.main()
