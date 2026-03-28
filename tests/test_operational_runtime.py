"""Contract tests for operational runtime module boundaries and state ownership."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.operational_runtime import (
    ACTION_OWNER_MODULES,
    HIGH_PRIORITY_CONTROL_ACTIONS,
    RUNTIME_MODULES,
    RUNTIME_STATE_OWNERSHIP,
    VALIDATION_ERRORS,
    ControlActionAuthorityReport,
    ControlActionRequest,
    RuntimeStateOwnershipReport,
    RuntimeModuleId,
    RuntimeProcess,
    RuntimeStateSurface,
    SupervisionTraceReport,
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

    def test_runtime_reports_round_trip_through_validated_json_loaders(self) -> None:
        ownership_report = evaluate_state_ownership(
            "ownership_roundtrip",
            RuntimeStateSurface.ORDERS,
            RuntimeModuleId.BROKER,
        )
        self.assertEqual(
            ownership_report,
            RuntimeStateOwnershipReport.from_json(ownership_report.to_json()),
        )

        control_report = evaluate_control_action_authority(
            ControlActionRequest.from_dict(load_cases()["control_action_cases"][0]["request"])
        )
        self.assertEqual(
            control_report,
            ControlActionAuthorityReport.from_json(control_report.to_json()),
        )

        trace_case = load_cases()["trace_bundle_cases"][0]
        trace_report = validate_supervision_trace_bundle(
            trace_case["case_id"],
            SupervisionTraceBundle.from_dict(trace_case["bundle"]),
        )
        self.assertEqual(
            trace_report,
            SupervisionTraceReport.from_json(trace_report.to_json()),
        )

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

    def test_control_action_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = deepcopy(load_cases()["control_action_cases"][0]["request"])
        invalid_cases = (
            (
                "authorization_truthy_string",
                lambda payload: payload.__setitem__("authorization_token_present", "true"),
                "authorization_token_present must be a boolean",
            ),
            (
                "requested_by_invalid",
                lambda payload: payload.__setitem__("requested_by", "scheduler"),
                "requested_by must be a valid runtime module id",
            ),
            (
                "target_deployment_instance_id_bool",
                lambda payload: payload.__setitem__("target_deployment_instance_id", False),
                "target_deployment_instance_id must be a non-empty string",
            ),
            (
                "case_id_bool",
                lambda payload: payload.__setitem__("case_id", True),
                "case_id must be a non-empty string",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    ControlActionRequest.from_dict(payload)

    def test_supervision_trace_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = deepcopy(load_cases()["trace_bundle_cases"][0]["bundle"])
        invalid_cases = (
            (
                "required_processes_string",
                lambda payload: payload.__setitem__("required_processes", "opsd"),
                "required_processes must be a sequence of runtime process values",
            ),
            (
                "event_high_priority_truthy_string",
                lambda payload: payload["events"][0].__setitem__("high_priority_lane", "true"),
                "high_priority_lane must be a boolean",
            ),
            (
                "event_sequence_bool",
                lambda payload: payload["events"][0].__setitem__("sequence_number", True),
                "sequence_number must be an integer",
            ),
            (
                "event_state_surface_invalid",
                lambda payload: payload["events"][0].__setitem__("state_surface", "book_state"),
                "state_surface must be a valid runtime state surface",
            ),
            (
                "events_string",
                lambda payload: payload.__setitem__("events", "event"),
                "events must be a sequence of objects",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    SupervisionTraceBundle.from_dict(payload)

    def test_from_json_rejects_non_object_payloads(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "control_action_request: expected JSON object",
        ):
            ControlActionRequest.from_json("[]")

        with self.assertRaisesRegex(
            ValueError,
            "supervision_trace_bundle: expected JSON object",
        ):
            SupervisionTraceBundle.from_json("[]")

        with self.assertRaisesRegex(
            ValueError,
            "runtime_state_ownership_report: expected JSON object",
        ):
            RuntimeStateOwnershipReport.from_json("[]")

        with self.assertRaisesRegex(
            ValueError,
            "control_action_authority_report: expected JSON object",
        ):
            ControlActionAuthorityReport.from_json("[]")

        with self.assertRaisesRegex(
            ValueError,
            "supervision_trace_report: expected JSON object",
        ):
            SupervisionTraceReport.from_json("[]")

    def test_report_loaders_reject_invalid_status_boolean_and_missing_timestamp(self) -> None:
        ownership_payload = evaluate_state_ownership(
            "ownership_invalid",
            RuntimeStateSurface.ORDERS,
            RuntimeModuleId.BROKER,
        ).to_dict()
        ownership_payload.pop("timestamp")
        with self.assertRaisesRegex(
            ValueError,
            "timestamp must be a timezone-aware ISO-8601 timestamp",
        ):
            RuntimeStateOwnershipReport.from_dict(ownership_payload)

        control_payload = evaluate_control_action_authority(
            ControlActionRequest.from_dict(load_cases()["control_action_cases"][0]["request"])
        ).to_dict()
        control_payload["allowed"] = "true"
        with self.assertRaisesRegex(ValueError, "allowed must be a boolean"):
            ControlActionAuthorityReport.from_dict(control_payload)

        trace_case = load_cases()["trace_bundle_cases"][0]
        trace_payload = validate_supervision_trace_bundle(
            trace_case["case_id"],
            SupervisionTraceBundle.from_dict(trace_case["bundle"]),
        ).to_dict()
        trace_payload["status"] = "green"
        with self.assertRaisesRegex(ValueError, "status must be a valid runtime report status"):
            SupervisionTraceReport.from_dict(trace_payload)
