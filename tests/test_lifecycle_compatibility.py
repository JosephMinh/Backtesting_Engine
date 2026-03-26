"""Contract tests for lifecycle state-machine specs and compatibility domains."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.lifecycle_compatibility import (
    COMPATIBILITY_DOMAIN_SPECS,
    LIFECYCLE_MACHINE_SPECS,
    VALIDATION_ERRORS,
    CompatibilityCheckRequest,
    CompatibilityDomain,
    CompatibilityVector,
    LifecycleMachine,
    LifecycleSpecStatus,
    compatibility_domain_names,
    evaluate_compatibility,
    evaluate_lifecycle_transition,
    machine_specs_by_id,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "lifecycle_compatibility_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(
            f"lifecycle compatibility fixture failed to load: {exc}"
        ) from exc


class LifecycleCompatibilityContractTest(unittest.TestCase):
    def test_contract_has_no_internal_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_canonical_domain_catalog_matches_expected_domains(self) -> None:
        self.assertEqual(
            (
                CompatibilityDomain.DATA_PROTOCOL.value,
                CompatibilityDomain.STRATEGY_PROTOCOL.value,
                CompatibilityDomain.OPS_PROTOCOL.value,
                CompatibilityDomain.POLICY_BUNDLE_HASH.value,
                CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value,
            ),
            compatibility_domain_names(),
        )

    def test_machine_catalog_covers_research_release_and_runtime_lifecycles(self) -> None:
        self.assertEqual(
            {
                LifecycleMachine.RESEARCH_RUN.value,
                LifecycleMachine.FAMILY_DECISION.value,
                LifecycleMachine.DATASET_RELEASE.value,
                LifecycleMachine.DERIVED_RELEASE.value,
                LifecycleMachine.BUNDLE_READINESS.value,
                LifecycleMachine.DEPLOYMENT_INSTANCE.value,
            },
            set(machine_specs_by_id()),
        )

    def test_every_machine_declares_consumers_domains_and_transitions(self) -> None:
        declared_domains = set(compatibility_domain_names())
        for spec in LIFECYCLE_MACHINE_SPECS:
            with self.subTest(machine_id=spec.machine_id):
                self.assertTrue(spec.consumers)
                self.assertTrue(spec.compatibility_domains)
                self.assertTrue(spec.transitions)
                self.assertTrue(set(spec.compatibility_domains).issubset(declared_domains))

    def test_transition_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["transition_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_lifecycle_transition(
                    case_id=payload["case_id"],
                    machine_id=payload["machine_id"],
                    from_state=payload["from_state"],
                    to_state=payload["to_state"],
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_affected_domains"]),
                    report.affected_domains,
                )
                self.assertEqual(
                    tuple(payload["expected_required_evidence_fields"]),
                    report.required_evidence_fields,
                )
                self.assertEqual(
                    payload["expected_transition_log_stages"],
                    [entry["stage"] for entry in report.to_dict()["transition_log"]],
                )

    def test_compatibility_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["compatibility_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_compatibility(
                    CompatibilityCheckRequest(
                        case_id=payload["case_id"],
                        subject_id=payload["subject_id"],
                        machine_id=payload["machine_id"],
                        baseline=CompatibilityVector(**payload["baseline"]),
                        candidate=CompatibilityVector(**payload["candidate"]),
                        declared_affected_domains=tuple(
                            payload["declared_affected_domains"]
                        ),
                        active_session=payload["active_session"],
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_changed_domains"]),
                    report.changed_domains,
                )
                self.assertEqual(
                    tuple(payload["expected_blocking_domains"]),
                    report.blocking_domains,
                )
                self.assertEqual(
                    tuple(payload["expected_recertification_domains"]),
                    report.recertification_domains,
                )

    def test_compatibility_reports_preserve_all_domain_results(self) -> None:
        report = evaluate_compatibility(
            CompatibilityCheckRequest(
                case_id="shape-check",
                subject_id="deployment_instance_shape",
                machine_id=LifecycleMachine.DEPLOYMENT_INSTANCE.value,
                baseline=CompatibilityVector(
                    data_protocol="data/v1",
                    strategy_protocol="strategy/v1",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v1",
                ),
                candidate=CompatibilityVector(
                    data_protocol="data/v1",
                    strategy_protocol="strategy/v2",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v2",
                ),
                declared_affected_domains=(
                    CompatibilityDomain.STRATEGY_PROTOCOL.value,
                    CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value,
                ),
            )
        )

        payload = report.to_dict()
        self.assertEqual(LifecycleSpecStatus.INCOMPATIBLE.value, report.status)
        self.assertEqual(len(COMPATIBILITY_DOMAIN_SPECS), len(payload["domain_results"]))
        self.assertTrue(
            {
                "case_id",
                "subject_id",
                "machine_id",
                "status",
                "reason_code",
                "compatible",
                "changed_domains",
                "blocking_domains",
                "recertification_domains",
                "declared_affected_domains",
                "domain_results",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )


if __name__ == "__main__":
    unittest.main()
