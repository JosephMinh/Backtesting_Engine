"""Contract tests for operational runtime module boundaries and state ownership."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.operational_runtime import (
    ACTION_OWNER_MODULES,
    HIGH_PRIORITY_CONTROL_ACTIONS,
    RUNTIME_MODULES,
    RUNTIME_STATE_OWNERSHIP,
    VALIDATION_ERRORS,
    ControlActionRequest,
    RuntimeModuleId,
    RuntimeProcess,
    RuntimeStateSurface,
    SupervisionTraceBundle,
    boundary_for_module,
    evaluate_control_action_authority,
    evaluate_state_ownership,
    owner_for_state_surface,
    runtime_module_ids,
    validate_supervision_trace_bundle,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "operational_runtime_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"operational runtime fixture failed to load: {exc}") from exc


class OperationalRuntimeContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_plan_modules_are_all_represented(self) -> None:
        self.assertEqual(
            {
                "market_data",
                "strategy_runner",
                "risk",
                "broker",
                "state_store",
                "reconciliation",
                "ops_http",
                "guardian",
                "watchdog",
                "broker_gateway",
            },
            set(runtime_module_ids()),
        )

    def test_guardian_and_watchdog_keep_authority_boundaries(self) -> None:
        guardian = boundary_for_module(RuntimeModuleId.GUARDIAN)
        watchdog = boundary_for_module(RuntimeModuleId.WATCHDOG)
        ops_http = boundary_for_module(RuntimeModuleId.OPS_HTTP)

        self.assertEqual((RuntimeStateSurface.CONTROL_ACTION_EVIDENCE,), guardian.owned_state_surfaces)
        self.assertTrue(guardian.separate_process_required)
        self.assertEqual((), watchdog.owned_state_surfaces)
        self.assertEqual(
            {
                RuntimeProcess.OPSD,
                RuntimeProcess.GUARDIAN,
                RuntimeProcess.BROKER_GATEWAY,
            },
            set(watchdog.supervision_targets),
        )
        self.assertEqual((), ops_http.owned_state_surfaces)

    def test_orders_positions_fills_and_readiness_have_deterministic_owners(self) -> None:
        self.assertEqual(RuntimeModuleId.BROKER, owner_for_state_surface(RuntimeStateSurface.ORDERS))
        self.assertEqual(RuntimeModuleId.BROKER, owner_for_state_surface(RuntimeStateSurface.POSITIONS))
        self.assertEqual(RuntimeModuleId.BROKER, owner_for_state_surface(RuntimeStateSurface.FILLS))
        self.assertEqual(
            RuntimeModuleId.RECONCILIATION,
            owner_for_state_surface(RuntimeStateSurface.READINESS_STATE),
        )
        self.assertEqual(
            RuntimeModuleId.GUARDIAN,
            owner_for_state_surface(RuntimeStateSurface.CONTROL_ACTION_EVIDENCE),
        )

    def test_state_ownership_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["ownership_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_state_ownership(
                    payload["case_id"],
                    RuntimeStateSurface(payload["state_surface"]),
                    RuntimeModuleId(payload["claimant_module"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_control_action_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["control_action_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                request = ControlActionRequest.from_dict(payload["request"])
                report = evaluate_control_action_authority(request)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_supervision_trace_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["trace_bundle_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                bundle = SupervisionTraceBundle.from_dict(payload["bundle"])
                report = validate_supervision_trace_bundle(payload["case_id"], bundle)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_trace_bundle_round_trip_preserves_supervision_requirements(self) -> None:
        fixtures = load_cases()
        bundle = SupervisionTraceBundle.from_dict(fixtures["trace_bundle_cases"][0]["bundle"])
        self.assertEqual(bundle, SupervisionTraceBundle.from_json(bundle.to_json()))

    def test_every_action_owner_is_listed_on_the_boundary_and_high_priority_actions_are_known(self) -> None:
        for action, owner in ACTION_OWNER_MODULES.items():
            with self.subTest(action=action.value):
                self.assertIn(action, boundary_for_module(owner).allowed_control_actions)

        self.assertTrue(
            HIGH_PRIORITY_CONTROL_ACTIONS.issubset(set(ACTION_OWNER_MODULES)),
            "every high-priority action must have an owner",
        )

    def test_every_owned_surface_is_declared_by_exactly_one_module(self) -> None:
        declared_surfaces = {
            surface
            for boundary in RUNTIME_MODULES
            for surface in boundary.owned_state_surfaces
        }
        self.assertEqual(set(RuntimeStateSurface), declared_surfaces)
        self.assertEqual(set(RuntimeStateSurface), set(RUNTIME_STATE_OWNERSHIP))
