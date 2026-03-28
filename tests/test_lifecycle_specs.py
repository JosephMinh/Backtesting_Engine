import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.lifecycle_specs import (
    APPROVAL_REQUIRED_TAG,
    BUNDLE_READINESS_MACHINE_ID,
    COMPATIBILITY_DOMAIN_SPECS,
    DEFAULT_COMPATIBILITY_DOMAIN_IDS,
    DEPLOYMENT_INSTANCE_MACHINE_ID,
    FRESHNESS_REQUIRED_TAG,
    LifecycleContractStatus,
    LifecycleMachineSpec,
    LifecycleTransitionReport,
    RUNTIME_ACTIVE_TAG,
    STATE_MACHINE_SPECS,
    VALIDATION_ERRORS,
    CompatibilityDomain,
    CompatibilityBindingReport,
    CompatibilityBindingRequest,
    build_enum_transition_map,
    evaluate_compatibility_binding,
    evaluate_transition,
    state_machine_spec,
    states_with_tag,
)
from shared.policy.deployment_packets import DeploymentState, ReadinessState

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "lifecycle_specs.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"lifecycle spec fixture failed to load: {exc}") from exc


class LifecycleSpecContractTest(unittest.TestCase):
    def test_catalog_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_machine_catalog_covers_expected_workflows(self) -> None:
        self.assertEqual(
            {
                "release_dataset_lifecycle",
                "release_derived_lifecycle",
                "bundle_readiness_lifecycle",
                "deployment_instance_lifecycle",
                "research_run_lifecycle",
                "family_decision_lifecycle",
            },
            {spec.machine_id for spec in STATE_MACHINE_SPECS},
        )

    def test_transition_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["state_machine_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_transition(
                    case_id=payload["case_id"],
                    machine_id=payload["machine_id"],
                    from_state=payload["from_state"],
                    to_state=payload["to_state"],
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_allowed_next_states"]),
                    report.transition_log.allowed_next_states,
                )

    def test_transition_report_rejects_unknown_machine_ids(self) -> None:
        report = evaluate_transition(
            case_id="unknown_machine",
            machine_id="unknown_machine",
            from_state="A",
            to_state="B",
        )
        self.assertEqual(LifecycleContractStatus.INVALID.value, report.status)
        self.assertEqual("STATE_MACHINE_UNKNOWN_MACHINE", report.reason_code)

    def test_compatibility_domain_catalog_matches_plan_minimum(self) -> None:
        self.assertEqual(
            (
                CompatibilityDomain.DATA_PROTOCOL.value,
                CompatibilityDomain.STRATEGY_PROTOCOL.value,
                CompatibilityDomain.OPS_PROTOCOL.value,
                CompatibilityDomain.POLICY_BUNDLE_HASH.value,
                CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value,
            ),
            DEFAULT_COMPATIBILITY_DOMAIN_IDS,
        )
        self.assertEqual(
            DEFAULT_COMPATIBILITY_DOMAIN_IDS,
            tuple(spec.domain_id.value for spec in COMPATIBILITY_DOMAIN_SPECS),
        )

    def test_compatibility_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["compatibility_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_compatibility_binding(
                    CompatibilityBindingRequest(
                        case_id=payload["case_id"],
                        subject_ref=payload["subject_ref"],
                        provided_domains=dict(payload["provided_domains"]),
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_missing_domains"]),
                    report.missing_domains,
                )
                self.assertEqual(
                    tuple(payload["expected_unknown_domains"]),
                    report.unknown_domains,
                )
                self.assertEqual(
                    tuple(payload["expected_blank_domains"]),
                    report.blank_domains,
                )

    def test_deployment_module_transition_maps_can_be_built_from_catalog(self) -> None:
        readiness_map = build_enum_transition_map(
            BUNDLE_READINESS_MACHINE_ID,
            ReadinessState,
        )
        deployment_map = build_enum_transition_map(
            DEPLOYMENT_INSTANCE_MACHINE_ID,
            DeploymentState,
        )
        self.assertEqual(
            {state.value for state in ReadinessState},
            {state.value for state in readiness_map},
        )
        self.assertEqual(
            {state.value for state in DeploymentState},
            {state.value for state in deployment_map},
        )

    def test_readiness_and_deployment_tags_drive_operational_sets(self) -> None:
        self.assertEqual(
            {
                ReadinessState.PORTABILITY_PASSED,
                ReadinessState.REPLAY_PASSED,
                ReadinessState.PAPER_ELIGIBLE,
                ReadinessState.PAPER_PASSED,
                ReadinessState.SHADOW_ELIGIBLE,
                ReadinessState.SHADOW_PASSED,
                ReadinessState.LIVE_ELIGIBLE,
            },
            states_with_tag(
                BUNDLE_READINESS_MACHINE_ID,
                APPROVAL_REQUIRED_TAG,
                ReadinessState,
            ),
        )
        self.assertEqual(
            {
                ReadinessState.PAPER_ELIGIBLE,
                ReadinessState.PAPER_PASSED,
                ReadinessState.SHADOW_ELIGIBLE,
                ReadinessState.SHADOW_PASSED,
                ReadinessState.LIVE_ELIGIBLE,
            },
            states_with_tag(
                BUNDLE_READINESS_MACHINE_ID,
                FRESHNESS_REQUIRED_TAG,
                ReadinessState,
            ),
        )
        self.assertEqual(
            {
                DeploymentState.PAPER_RUNNING,
                DeploymentState.SHADOW_RUNNING,
                DeploymentState.LIVE_CANARY,
                DeploymentState.LIVE_ACTIVE,
            },
            states_with_tag(
                DEPLOYMENT_INSTANCE_MACHINE_ID,
                RUNTIME_ACTIVE_TAG,
                DeploymentState,
            ),
        )

    def test_contract_snapshot_is_machine_readable(self) -> None:
        snapshot = state_machine_spec(BUNDLE_READINESS_MACHINE_ID).to_dict()
        self.assertEqual("bundle_readiness_lifecycle", snapshot["machine_id"])
        self.assertEqual("FROZEN", snapshot["initial_state"])

    def test_machine_spec_round_trip_preserves_catalog_shape(self) -> None:
        spec = state_machine_spec(BUNDLE_READINESS_MACHINE_ID)
        self.assertEqual(
            spec.to_dict(),
            LifecycleMachineSpec.from_json(spec.to_json()).to_dict(),
        )

    def test_machine_spec_loader_rejects_invalid_boundary_values(self) -> None:
        payload = deepcopy(state_machine_spec(BUNDLE_READINESS_MACHINE_ID).to_dict())
        invalid_cases = (
            ("non_object_payload", [], "lifecycle_machine_spec: must be an object"),
            (
                "states_string",
                lambda item: item.__setitem__("states", "state"),
                "states: must be a list of objects",
            ),
            (
                "allowed_transitions_string",
                lambda item: item.__setitem__("allowed_transitions", "A->B"),
                "allowed_transitions: must be an object",
            ),
            (
                "schema_version_unsupported",
                lambda item: item.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
            (
                "schema_version_missing",
                lambda item: item.pop("schema_version"),
                "schema_version: missing required field",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                if case_id == "non_object_payload":
                    with self.assertRaisesRegex(ValueError, error):
                        LifecycleMachineSpec.from_dict(mutate)
                    continue
                item = deepcopy(payload)
                mutate(item)
                with self.assertRaisesRegex(ValueError, error):
                    LifecycleMachineSpec.from_dict(item)

    def test_binding_request_and_report_round_trip_preserve_shape(self) -> None:
        compatibility_case = load_cases()["compatibility_cases"][0]
        request = CompatibilityBindingRequest.from_dict(
            {
                "case_id": compatibility_case["case_id"],
                "subject_ref": compatibility_case["subject_ref"],
                "provided_domains": compatibility_case["provided_domains"],
            }
        )
        self.assertEqual(
            request.to_dict(),
            CompatibilityBindingRequest.from_json(request.to_json()).to_dict(),
        )

        report = evaluate_compatibility_binding(request)
        self.assertEqual(
            report.to_dict(),
            CompatibilityBindingReport.from_json(report.to_json()).to_dict(),
        )

    def test_binding_and_transition_report_loaders_reject_invalid_boundary_values(self) -> None:
        compatibility_case = load_cases()["compatibility_cases"][0]
        request_payload = {
            "case_id": compatibility_case["case_id"],
            "subject_ref": compatibility_case["subject_ref"],
            "provided_domains": compatibility_case["provided_domains"],
        }

        invalid_request = deepcopy(request_payload)
        invalid_request["provided_domains"] = "domains"
        with self.assertRaisesRegex(ValueError, "provided_domains: must be an object"):
            CompatibilityBindingRequest.from_dict(invalid_request)

        compatibility_report = evaluate_compatibility_binding(
            CompatibilityBindingRequest.from_dict(request_payload)
        ).to_dict()
        invalid_report = deepcopy(compatibility_report)
        invalid_report["status"] = "ship"
        with self.assertRaisesRegex(
            ValueError,
            "status: must be a valid lifecycle contract status",
        ):
            CompatibilityBindingReport.from_dict(invalid_report)

        transition_report = evaluate_transition(
            case_id="roundtrip_transition",
            machine_id=BUNDLE_READINESS_MACHINE_ID,
            from_state="FROZEN",
            to_state="PORTABILITY_PENDING",
        ).to_dict()
        invalid_transition = deepcopy(transition_report)
        invalid_transition["transition_log"] = "trace"
        with self.assertRaisesRegex(ValueError, "transition_log: must be an object"):
            LifecycleTransitionReport.from_dict(invalid_transition)
