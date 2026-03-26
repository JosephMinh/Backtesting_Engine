import json
import unittest
from pathlib import Path

from shared.policy.lifecycle_specs import (
    APPROVAL_REQUIRED_TAG,
    BUNDLE_READINESS_MACHINE_ID,
    COMPATIBILITY_DOMAIN_SPECS,
    DEFAULT_COMPATIBILITY_DOMAIN_IDS,
    DEPLOYMENT_INSTANCE_MACHINE_ID,
    FRESHNESS_REQUIRED_TAG,
    LifecycleContractStatus,
    RUNTIME_ACTIVE_TAG,
    STATE_MACHINE_SPECS,
    VALIDATION_ERRORS,
    CompatibilityDomain,
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
