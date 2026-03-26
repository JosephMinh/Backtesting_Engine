import json
import unittest
from pathlib import Path

from shared.policy.feature_availability import (
    BacktestEvaluationMode,
    ContractSeriesMode,
    ContinuousSeriesUsage,
    DecisionLatencyClass,
    FeatureAvailabilityContract,
    FeatureAvailabilityGateRequest,
    FeatureDecisionSurface,
    FallbackBehavior,
    PolicyGateStatus,
    RollPolicyRequest,
    RollPolicySurface,
    RollTransitionAction,
    VALIDATION_ERRORS,
    evaluate_feature_availability_gate,
    evaluate_roll_policy,
    validate_feature_availability_contract,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "feature_availability.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"feature availability fixture failed to load: {exc}") from exc


def build_feature_contract(payload: dict[str, object]) -> FeatureAvailabilityContract:
    return FeatureAvailabilityContract.from_dict(payload)


class FeatureAvailabilityContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_contract_payload(self) -> None:
        contract = FeatureAvailabilityContract(
            feature_block_id="roundtrip_feature_block_v1",
            source_artifact_ids=("analytic_release_gold_core_v1",),
            source_fields=("close", "volume"),
            value_timestamp_rule="derived_from_bar_close_timestamp",
            available_at_rule="available_immediately_after_bar_close",
            requires_bar_close=True,
            requires_session_close=False,
            decision_latency_class=DecisionLatencyClass.BAR_CLOSE,
            fallback_behavior=FallbackBehavior.BLOCK_SURFACE,
            compatible_data_profile_release_ids=("ibkr_1oz_comex_bars_1m_v1",),
            feature_contract_hash="sha256:roundtrip-feature-001",
        )

        self.assertEqual(contract, FeatureAvailabilityContract.from_json(contract.to_json()))

    def test_from_json_rejects_invalid_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "feature_availability_contract: invalid JSON payload",
        ):
            FeatureAvailabilityContract.from_json("{not valid json")

    def test_invalid_contract_rejects_session_close_without_bar_close(self) -> None:
        report = validate_feature_availability_contract(
            "session-close-shape",
            FeatureAvailabilityContract(
                feature_block_id="bad_feature_v1",
                source_artifact_ids=("analytic_release_gold_core_v1",),
                source_fields=("session_close",),
                value_timestamp_rule="derived_from_session_close_timestamp",
                available_at_rule="available_after_session_close_review",
                requires_bar_close=False,
                requires_session_close=True,
                decision_latency_class=DecisionLatencyClass.SESSION_CLOSE,
                fallback_behavior=FallbackBehavior.SKIP_FEATURE_BLOCK,
                compatible_data_profile_release_ids=("ibkr_1oz_comex_bars_1m_v1",),
                feature_contract_hash="sha256:bad-feature-001",
            ),
        )

        self.assertEqual(PolicyGateStatus.INVALID.value, report.status)
        self.assertEqual(
            "FEATURE_CONTRACT_SESSION_CLOSE_REQUIRES_BAR_CLOSE",
            report.reason_code,
        )

    def test_feature_gate_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["feature_gate_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_feature_availability_gate(
                    FeatureAvailabilityGateRequest(
                        case_id=payload["case_id"],
                        surface_name=FeatureDecisionSurface(payload["surface_name"]),
                        decision_latency_class=DecisionLatencyClass(
                            payload["decision_latency_class"]
                        ),
                        bound_data_profile_release_id=payload["bound_data_profile_release_id"],
                        feature_contracts=tuple(
                            build_feature_contract(item)
                            for item in payload["feature_contracts"]
                        ),
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_accepted_feature_block_ids"]),
                    report.accepted_feature_block_ids,
                )
                self.assertEqual(
                    tuple(payload["expected_rejected_feature_block_ids"]),
                    report.rejected_feature_block_ids,
                )
                self.assertEqual(
                    set(payload["expected_accepted_feature_block_ids"])
                    | set(payload["expected_rejected_feature_block_ids"]),
                    set(report.decision_trace),
                )

    def test_roll_policy_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["roll_policy_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_roll_policy(
                    RollPolicyRequest(
                        case_id=payload["case_id"],
                        surface_name=RollPolicySurface(payload["surface_name"]),
                        product_profile_id=payload["product_profile_id"],
                        resolved_context_bundle_id=payload["resolved_context_bundle_id"],
                        roll_map_id=payload["roll_map_id"],
                        roll_calendar_source=payload["roll_calendar_source"],
                        contract_series_mode=ContractSeriesMode(payload["contract_series_mode"]),
                        continuous_series_usage=ContinuousSeriesUsage(
                            payload["continuous_series_usage"]
                        ),
                        selected_contract_segment_id=payload["selected_contract_segment_id"],
                        next_contract_segment_id=payload["next_contract_segment_id"],
                        active_contract_is_point_in_time=payload[
                            "active_contract_is_point_in_time"
                        ],
                        active_contract_is_delivery_aware=payload[
                            "active_contract_is_delivery_aware"
                        ],
                        delivery_fence_enforced=payload["delivery_fence_enforced"],
                        delivery_window_active=payload["delivery_window_active"],
                        reviewed_roll_approved=payload["reviewed_roll_approved"],
                        backtest_evaluation_mode=BacktestEvaluationMode(
                            payload["backtest_evaluation_mode"]
                        ),
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(payload["expected_transition_action"], report.transition_action)
                self.assertEqual(
                    payload["expected_blocked_by_delivery_fence"],
                    report.blocked_by_delivery_fence,
                )

    def test_feature_gate_reports_are_structured_and_explainable(self) -> None:
        report = evaluate_feature_availability_gate(
            FeatureAvailabilityGateRequest(
                case_id="shape-case",
                surface_name=FeatureDecisionSurface.LIVE_ACTIVATION,
                decision_latency_class=DecisionLatencyClass.BAR_CLOSE,
                bound_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                feature_contracts=(
                    FeatureAvailabilityContract(
                        feature_block_id="shape_feature_block_v1",
                        source_artifact_ids=("analytic_release_gold_core_v1",),
                        source_fields=("close",),
                        value_timestamp_rule="derived_from_bar_close_timestamp",
                        available_at_rule="available_immediately_after_bar_close",
                        requires_bar_close=True,
                        requires_session_close=False,
                        decision_latency_class=DecisionLatencyClass.BAR_CLOSE,
                        fallback_behavior=FallbackBehavior.BLOCK_SURFACE,
                        compatible_data_profile_release_ids=(
                            "ibkr_1oz_comex_bars_1m_v1",
                        ),
                        feature_contract_hash="sha256:shape-feature-001",
                    ),
                ),
            )
        )

        payload = report.to_dict()
        self.assertEqual(PolicyGateStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "surface_name",
                "status",
                "reason_code",
                "decision_latency_class",
                "bound_data_profile_release_id",
                "accepted_feature_block_ids",
                "rejected_feature_block_ids",
                "decision_trace",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("data-profile release", report.explanation.lower())

    def test_roll_policy_report_exposes_transition_and_context_binding(self) -> None:
        report = evaluate_roll_policy(
            RollPolicyRequest(
                case_id="roll-shape",
                surface_name=RollPolicySurface.LIVE,
                product_profile_id="mgc_comex_v1",
                resolved_context_bundle_id="resolved_context_bundle_mgc_rolls_v1",
                roll_map_id="roll_map_mgc_v1",
                roll_calendar_source="resolved_context_bundle_roll_windows",
                contract_series_mode=ContractSeriesMode.ACTUAL_SEGMENTS,
                continuous_series_usage=ContinuousSeriesUsage.NONE,
                selected_contract_segment_id="MGCM6",
                next_contract_segment_id="MGCQ6",
                active_contract_is_point_in_time=True,
                active_contract_is_delivery_aware=True,
                delivery_fence_enforced=True,
                delivery_window_active=True,
                reviewed_roll_approved=True,
            )
        )

        payload = report.to_dict()
        self.assertEqual(PolicyGateStatus.PASS.value, report.status)
        self.assertEqual(
            RollTransitionAction.ROLL_TO_NEXT_SEGMENT.value,
            report.transition_action,
        )
        self.assertTrue(
            {
                "case_id",
                "surface_name",
                "product_profile_id",
                "status",
                "reason_code",
                "transition_action",
                "blocked_by_delivery_fence",
                "selected_contract_segment_id",
                "next_contract_segment_id",
                "expected_roll_calendar_source",
                "actual_roll_calendar_source",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("delivery-aware", report.explanation.lower())


if __name__ == "__main__":
    unittest.main()
