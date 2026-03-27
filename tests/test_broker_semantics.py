"""Contract tests for broker conformance, idempotency, and fixture replay semantics."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.broker_semantics import (
    TRADEABLE_LANES,
    VALIDATION_ERRORS,
    BrokerConformanceRequest,
    BrokerMutationScenario,
    BrokerSessionFixtureLibrary,
    OrderIntentIdentity,
    evaluate_broker_conformance,
    evaluate_broker_session_fixture_library,
    evaluate_order_intent_idempotency,
    required_broker_session_scenarios,
)
from shared.policy.product_profiles import ProductLane, product_profiles_by_id

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "broker_semantics_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"broker semantics fixture failed to load: {exc}") from exc


class BrokerSemanticsContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_required_session_scenarios_are_unique_and_plan_complete(self) -> None:
        self.assertEqual(
            (
                "clean_fill_flow",
                "partial_fills",
                "unsolicited_cancel",
                "reject_after_acknowledgement",
                "disconnect_reconnect_mid_order",
                "daily_reset_and_post_reset_resume",
                "contract_definition_mismatch_detection",
                "timeout_with_no_response",
            ),
            required_broker_session_scenarios(),
        )

    def test_tradeable_lanes_remain_explicit(self) -> None:
        self.assertEqual(
            {ProductLane.PAPER, ProductLane.SHADOW_LIVE, ProductLane.LIVE},
            set(TRADEABLE_LANES),
        )

    def test_tradeable_profile_requires_broker_conformance_controls(self) -> None:
        profile = product_profiles_by_id()["oneoz_comex_v1"]
        assumptions = profile.broker_capability_assumptions

        self.assertTrue(assumptions.contract_conformance_required)
        self.assertTrue(assumptions.flatten_supported)
        self.assertTrue(assumptions.modify_cancel_supported)
        self.assertTrue(assumptions.session_definition_required)

    def test_conformance_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["conformance_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                request = BrokerConformanceRequest.from_dict(dict(payload["request"]))
                report = evaluate_broker_conformance(request)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_order_intent_id_is_deterministic_from_identity(self) -> None:
        identity = OrderIntentIdentity(
            deployment_instance_id="deploy_gold_live_001",
            decision_sequence_number=41,
            leg_id="entry",
            side="buy",
            intent_purpose="tighten_stop",
        )
        self.assertEqual(
            "deploy_gold_live_001:41:entry:buy:tighten_stop",
            identity.deterministic_id(),
        )

    def test_idempotency_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["idempotency_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                scenario = BrokerMutationScenario.from_dict(dict(payload["scenario"]))
                report = evaluate_order_intent_idempotency(scenario)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_idempotency_fixtures_cover_required_race_and_recovery_scenarios(self) -> None:
        fixtures = load_cases()
        case_ids = {payload["case_id"] for payload in fixtures["idempotency_cases"]}
        self.assertTrue(
            {
                "submit_timeout_reconciles_without_resend",
                "acknowledgement_loss_reconciles_without_duplicate_submit",
                "reconnect_before_ack_preserves_single_intent_mapping",
                "duplicate_fill_callbacks_must_deduplicate_state",
                "cancel_replace_race_reuses_single_order_intent_mapping",
                "operator_retry_race_must_reuse_original_intent_id",
            }.issubset(case_ids)
        )

    def test_broker_mutation_round_trip_preserves_identity(self) -> None:
        fixtures = load_cases()
        scenario = BrokerMutationScenario.from_dict(
            dict(fixtures["idempotency_cases"][0]["scenario"])
        )
        reparsed = BrokerMutationScenario.from_json(scenario.to_json())

        self.assertEqual(
            scenario.order_intent_identity.deterministic_id(),
            reparsed.order_intent_identity.deterministic_id(),
        )
        self.assertEqual(scenario.timeline_event_types, reparsed.timeline_event_types)

    def test_fixture_library_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["fixture_library_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                library = BrokerSessionFixtureLibrary.from_dict(dict(payload["library"]))
                report = evaluate_broker_session_fixture_library(payload["case_id"], library)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_fixture_library_round_trip_preserves_required_scenarios(self) -> None:
        fixtures = load_cases()
        library = BrokerSessionFixtureLibrary.from_dict(
            dict(fixtures["fixture_library_cases"][0]["library"])
        )
        reparsed = BrokerSessionFixtureLibrary.from_json(library.to_json())

        self.assertEqual(library.library_id, reparsed.library_id)
        self.assertEqual(
            {fixture.scenario_kind for fixture in library.fixtures},
            {fixture.scenario_kind for fixture in reparsed.fixtures},
        )
