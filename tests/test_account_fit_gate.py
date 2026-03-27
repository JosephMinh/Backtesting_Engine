"""Contract tests for account-fit gating on the actual execution contract."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.account_fit_gate import (
    VALIDATION_ERRORS,
    AccountFitExecutionDecision,
    AccountFitReport,
    AccountFitRequest,
    AccountFitStatus,
    derive_account_fit_thresholds,
    evaluate_account_fit,
    select_account_fit_execution_symbol,
)

FIXTURE_PATH = Path("shared/fixtures/policy/account_fit_gate_cases.json")


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["cases"]


def check_results_by_id(report: AccountFitReport) -> dict[str, object]:
    return {result.check_id: result for result in report.check_results}


class AccountFitGateCatalogTests(unittest.TestCase):
    def test_account_fit_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_small_account_thresholds_are_derived_from_the_profile_catalog(self) -> None:
        thresholds = derive_account_fit_thresholds(
            product_profile_id="oneoz_comex_v1",
            account_profile_id="solo_small_gold_ibkr_5000_v1",
        )

        self.assertEqual("oneoz_comex_v1", thresholds.source_product_profile_id)
        self.assertEqual("solo_small_gold_ibkr_5000_v1", thresholds.source_account_profile_id)
        self.assertEqual("1OZ", thresholds.execution_symbol)
        self.assertEqual(5000, thresholds.approved_starting_equity_usd)
        self.assertEqual(("1OZ",), thresholds.approved_symbols)
        self.assertEqual(1, thresholds.max_position_size)
        self.assertEqual(0.25, thresholds.max_initial_margin_fraction)
        self.assertEqual(0.35, thresholds.max_maintenance_margin_fraction)
        self.assertEqual(0.025, thresholds.daily_loss_lockout_fraction)
        self.assertEqual(0.15, thresholds.max_drawdown_fraction)
        self.assertEqual(0.05, thresholds.overnight_gap_stress_fraction)


class AccountFitGateFixtureCases(unittest.TestCase):
    def test_fixture_cases_match_expected_outputs(self) -> None:
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                expected_parse_error = case.get("expected_parse_error")
                if expected_parse_error is not None:
                    with self.assertRaisesRegex(ValueError, str(expected_parse_error)):
                        AccountFitRequest.from_dict(dict(case["request"]))
                    continue

                request = AccountFitRequest.from_dict(dict(case["request"]))
                report = evaluate_account_fit(request)
                expected = dict(case["expected"])

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["failed_check_ids"]),
                    report.failed_check_ids,
                )
                self.assertEqual(
                    expected["allowed_execution_symbol"],
                    report.allowed_execution_symbol,
                )
                self.assertAlmostEqual(
                    expected["round_turn_fees_usd"],
                    report.round_turn_fees_usd,
                )

                if report.status in {
                    AccountFitStatus.STALE.value,
                    AccountFitStatus.INVALID.value,
                }:
                    self.assertEqual((), report.check_results)
                    continue

                checks = check_results_by_id(report)
                for check_id, expected_check in dict(expected["checks"]).items():
                    result = checks[check_id]
                    self.assertEqual(expected_check["applied"], result.applied)
                    self.assertEqual(expected_check["passed"], result.passed)
                    if "actual_fraction" in expected_check:
                        self.assertAlmostEqual(
                            expected_check["actual_fraction"],
                            result.actual_fraction,
                            places=6,
                        )


class AccountFitGateContractTests(unittest.TestCase):
    def test_report_round_trip_preserves_nested_checks_and_artifacts(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "oneoz_passes_small_account_actual_contract_gate"
        )
        request = AccountFitRequest.from_dict(dict(case["request"]))
        report = evaluate_account_fit(request)

        parsed = AccountFitReport.from_json(report.to_json())

        self.assertEqual(report, parsed)

    def test_execution_symbol_selection_restricts_promotion_to_oneoz(self) -> None:
        oneoz_case = next(
            case
            for case in load_cases()
            if case["case_id"] == "oneoz_passes_small_account_actual_contract_gate"
        )
        mgc_case = next(
            case
            for case in load_cases()
            if case["case_id"] == "mgc_fails_but_oneoz_can_proceed"
        )
        reports = (
            evaluate_account_fit(AccountFitRequest.from_dict(dict(mgc_case["request"]))),
            evaluate_account_fit(AccountFitRequest.from_dict(dict(oneoz_case["request"]))),
        )

        decision = select_account_fit_execution_symbol(reports)
        reparsed = AccountFitExecutionDecision.from_json(decision.to_json())

        self.assertEqual("pass", decision.status)
        self.assertEqual(
            "ACCOUNT_FIT_EXECUTION_SYMBOL_RESTRICTED_TO_1OZ",
            decision.reason_code,
        )
        self.assertEqual(("1OZ",), decision.allowed_execution_symbols)
        self.assertEqual("1OZ", decision.selected_execution_symbol)
        self.assertEqual(
            {"MGC": "fail", "1OZ": "pass"},
            decision.report_status_by_symbol,
        )
        self.assertEqual(decision, reparsed)

    def test_invalid_json_payloads_raise_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "account_fit_request: invalid JSON payload"):
            AccountFitRequest.from_json("not-json")

        with self.assertRaisesRegex(ValueError, "account_fit_report: invalid JSON payload"):
            AccountFitReport.from_json("not-json")

        with self.assertRaisesRegex(
            ValueError,
            "account_fit_execution_decision: invalid JSON payload",
        ):
            AccountFitExecutionDecision.from_json("not-json")


if __name__ == "__main__":
    unittest.main()
