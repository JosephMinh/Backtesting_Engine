from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.baseline_risk_controls import (
    BASELINE_RISK_CONTROL_IDS,
    VALIDATION_ERRORS,
    BaselineRiskEvaluationReport,
    BaselineRiskEvaluationRequest,
    evaluate_baseline_risk_controls,
    inherited_baseline_risk_defaults,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "baseline_risk_control_cases.json"
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


def build_request(overrides: dict[str, Any] | None = None) -> BaselineRiskEvaluationRequest:
    fixture = load_cases()
    payload = deep_merge(
        dict(fixture["shared_request_defaults"]),
        overrides or {},
    )
    return BaselineRiskEvaluationRequest.from_dict(payload)


class BaselineRiskCatalogTests(unittest.TestCase):
    def test_baseline_risk_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


class BaselineRiskDefaultsTests(unittest.TestCase):
    def test_inherited_defaults_follow_product_account_and_strategy_contracts(self) -> None:
        request = build_request()

        defaults = inherited_baseline_risk_defaults(
            product_profile_id=request.product_profile_id,
            account_profile_id=request.account_profile_id,
            strategy_contract=request.strategy_contract,
        )

        self.assertEqual("oneoz_comex_v1", defaults.source_product_profile_id)
        self.assertEqual("solo_small_gold_ibkr_5000_v1", defaults.source_account_profile_id)
        self.assertEqual("gold_momentum_contract", defaults.source_strategy_contract_id)
        self.assertEqual("1OZ", defaults.execution_symbol)
        self.assertEqual(1, defaults.max_position_size)
        self.assertEqual(1, defaults.max_concurrent_order_intents)
        self.assertEqual(0.025, defaults.daily_loss_lockout_fraction)
        self.assertEqual(0.15, defaults.max_drawdown_fraction)
        self.assertEqual(0.25, defaults.max_initial_margin_fraction)
        self.assertEqual(0.35, defaults.max_maintenance_margin_fraction)
        self.assertEqual(
            ("intraday_flat_default", "overnight_strict"),
            defaults.allowed_operating_postures,
        )
        self.assertEqual("intraday_flat_default", defaults.default_operating_posture)
        self.assertTrue(defaults.overnight_only_with_strict_class)
        self.assertEqual(
            "block_tradeability_when_resolved_context_marks_expiring_contract",
            defaults.delivery_fence_rule,
        )
        self.assertTrue(defaults.delivery_fence_review_required)
        self.assertEqual(300, defaults.warmup_min_history_bars)
        self.assertEqual(0, defaults.warmup_min_history_minutes)
        self.assertTrue(defaults.warmup_requires_state_seed)


class BaselineRiskEvaluationTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = build_request(case["overrides"])
                report = evaluate_baseline_risk_controls(request)
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["action"], report.action)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_control_ids"]),
                    report.triggered_control_ids,
                )
                self.assertEqual(
                    tuple(expected["waiver_references"]),
                    report.waiver_references,
                )

    def test_every_report_traces_the_full_control_catalog(self) -> None:
        fixture = load_cases()
        for case in fixture["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_baseline_risk_controls(build_request(case["overrides"]))
                self.assertEqual(len(BASELINE_RISK_CONTROL_IDS), len(report.control_results))
                self.assertEqual(
                    BASELINE_RISK_CONTROL_IDS,
                    tuple(result.control_id for result in report.control_results),
                )

    def test_expired_waiver_does_not_bypass_inherited_limit(self) -> None:
        report = evaluate_baseline_risk_controls(
            build_request(
                {
                    "projected_position_size": 2,
                    "waivers": [
                        {
                            "waiver_id": "expired_position_limit_waiver",
                            "categories": ["baseline_risk_controls"],
                            "rule_ids": ["max_position_limit"],
                            "reason_codes": ["BASELINE_RISK_POSITION_LIMIT_EXCEEDED"],
                            "approved_by": "operator@example.com",
                            "justification": "Expired drill exception",
                            "expires_at_utc": "2026-03-25T23:59:59+00:00"
                        }
                    ]
                }
            )
        )

        self.assertEqual("violation", report.status)
        self.assertEqual("restrict", report.action)
        self.assertEqual("BASELINE_RISK_POSITION_LIMIT_EXCEEDED", report.reason_code)
        self.assertEqual(("max_position_limit",), report.triggered_control_ids)
        self.assertEqual((), report.waiver_references)

    def test_max_concurrent_order_intents_restricts_new_entries(self) -> None:
        report = evaluate_baseline_risk_controls(
            build_request({"pending_order_intent_count": 2})
        )

        self.assertEqual("violation", report.status)
        self.assertEqual("restrict", report.action)
        self.assertEqual(
            "BASELINE_RISK_CONCURRENT_ORDER_INTENT_LIMIT_EXCEEDED",
            report.reason_code,
        )
        self.assertEqual(("max_concurrent_order_intents",), report.triggered_control_ids)

    def test_drawdown_breach_forces_flatten(self) -> None:
        report = evaluate_baseline_risk_controls(
            build_request(
                {
                    "current_position_size": 1,
                    "projected_position_size": 1,
                    "drawdown_fraction": 0.16,
                }
            )
        )

        self.assertEqual("violation", report.status)
        self.assertEqual("flatten", report.action)
        self.assertEqual("BASELINE_RISK_MAX_DRAWDOWN", report.reason_code)
        self.assertEqual(("max_drawdown_flatten",), report.triggered_control_ids)

    def test_report_round_trip_preserves_nested_results(self) -> None:
        fixture = load_cases()
        waived_case = next(
            case for case in fixture["evaluation_cases"] if case["case_id"] == "max_position_waiver_path"
        )
        report = evaluate_baseline_risk_controls(build_request(waived_case["overrides"]))
        reparsed = BaselineRiskEvaluationReport.from_json(report.to_json())

        self.assertEqual(report.status, reparsed.status)
        self.assertEqual(report.action, reparsed.action)
        self.assertEqual(report.triggered_control_ids, reparsed.triggered_control_ids)
        self.assertEqual(report.waiver_references, reparsed.waiver_references)
        self.assertEqual(report.effective_defaults, reparsed.effective_defaults)
        self.assertEqual(report.control_results, reparsed.control_results)

    def test_request_loader_requires_explicit_integer_schema_version(self) -> None:
        payload = dict(load_cases()["shared_request_defaults"])
        payload.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "baseline_risk_evaluation_request: schema_version must be an integer",
        ):
            BaselineRiskEvaluationRequest.from_dict(payload)

        payload = dict(load_cases()["shared_request_defaults"])
        payload["schema_version"] = True
        with self.assertRaisesRegex(
            ValueError,
            "baseline_risk_evaluation_request: schema_version must be an integer",
        ):
            BaselineRiskEvaluationRequest.from_dict(payload)

    def test_request_loader_rejects_truthy_bool_coercions(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "pending_order_intent_count must be an integer",
        ):
            build_request({"pending_order_intent_count": True})

        with self.assertRaisesRegex(
            ValueError,
            "data_quality_degraded must be a boolean",
        ):
            build_request({"data_quality_degraded": "false"})

        with self.assertRaisesRegex(
            ValueError,
            "requested_initial_margin_fraction must be finite",
        ):
            build_request({"requested_initial_margin_fraction": True})

    def test_timestamp_fields_require_timezone_aware_strings(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "timestamp fields must be timezone-aware UTC-normalizable strings",
        ):
            build_request({"evaluated_at_utc": "2026-03-28T00:00:00"})

    def test_report_loader_rejects_truthy_control_flags(self) -> None:
        fixture = load_cases()
        report = evaluate_baseline_risk_controls(
            build_request(fixture["evaluation_cases"][0]["overrides"])
        )
        payload = report.to_dict()
        payload["control_results"][0]["passed"] = "true"
        with self.assertRaisesRegex(ValueError, "passed must be a boolean"):
            BaselineRiskEvaluationReport.from_dict(payload)

        payload = report.to_dict()
        payload["timestamp"] = "2026-03-28T00:00:00"
        with self.assertRaisesRegex(
            ValueError,
            "timestamp fields must be timezone-aware UTC-normalizable strings",
        ):
            BaselineRiskEvaluationReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
