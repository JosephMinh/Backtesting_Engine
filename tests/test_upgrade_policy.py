"""Contract tests for upgrade policy and startup compatibility checks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.upgrade_policy import (
    REQUIRED_STARTUP_SURFACES,
    RETAINED_MIGRATION_ARTIFACTS,
    REPO_STRUCTURE_RULES,
    VALIDATION_ERRORS,
    MigrationDeclaration,
    StartupCompatibilityRequest,
    StartupSnapshot,
    classify_repo_path,
    evaluate_startup_compatibility,
)
from shared.policy.lifecycle_compatibility import CompatibilityVector, LifecycleSpecStatus

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "upgrade_policy_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"upgrade policy fixture failed to load: {exc}") from exc


def load_snapshot(payload: dict[str, object]) -> StartupSnapshot:
    return StartupSnapshot(
        binary_version=payload["binary_version"],
        database_schema_version=payload["database_schema_version"],
        snapshot_journal_format=payload["snapshot_journal_format"],
        policy_bundle_hash=payload["policy_bundle_hash"],
        artifact_compatibility_matrix=payload["artifact_compatibility_matrix"],
        compatibility_vector=CompatibilityVector(**payload["compatibility_vector"]),
    )


class UpgradePolicyContractTest(unittest.TestCase):
    def test_contract_has_no_internal_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_startup_surface_catalog_matches_plan_required_surfaces(self) -> None:
        self.assertEqual(
            (
                "binary_version",
                "database_schema_version",
                "snapshot_journal_format",
                "policy_bundle_hash",
                "artifact_compatibility_matrix",
            ),
            REQUIRED_STARTUP_SURFACES,
        )

    def test_repo_structure_rules_cover_the_declared_plane_roots(self) -> None:
        self.assertIn(("shared/", "shared_contracts"), REPO_STRUCTURE_RULES)
        self.assertIn(("tests/", "tests"), REPO_STRUCTURE_RULES)
        self.assertIn(("infra/", "infra_support"), REPO_STRUCTURE_RULES)

    def test_repo_path_classifier_rejects_unknown_roots(self) -> None:
        aligned = classify_repo_path("shared/policy/upgrade_policy.py")
        invalid = classify_repo_path("misc/runtime_patch.py")
        self.assertTrue(aligned.aligned)
        self.assertEqual("shared_contracts", aligned.plane)
        self.assertFalse(invalid.aligned)
        self.assertIsNone(invalid.plane)

    def test_startup_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["startup_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_startup_compatibility(
                    StartupCompatibilityRequest(
                        case_id=payload["case_id"],
                        subject_id=payload["subject_id"],
                        machine_id=payload["machine_id"],
                        migration=MigrationDeclaration(
                            migration_id=payload["migration"]["migration_id"],
                            description=payload["migration"]["description"],
                            affected_domains=tuple(payload["migration"]["affected_domains"]),
                            startup_surfaces=tuple(payload["migration"]["startup_surfaces"]),
                            replay_required=payload["migration"]["replay_required"],
                            recertification_required=payload["migration"][
                                "recertification_required"
                            ],
                            new_promotion_packet_required=payload["migration"][
                                "new_promotion_packet_required"
                            ],
                            forward_only=payload["migration"]["forward_only"],
                            recoverability_evidence_id=payload["migration"][
                                "recoverability_evidence_id"
                            ],
                            rollback_or_restore_path=payload["migration"][
                                "rollback_or_restore_path"
                            ],
                            repo_paths=tuple(payload["migration"]["repo_paths"]),
                            incident_override=payload["migration"]["incident_override"],
                        ),
                        baseline=load_snapshot(payload["baseline"]),
                        candidate=load_snapshot(payload["candidate"]),
                        active_session=payload["active_session"],
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_changed_startup_surfaces"]),
                    report.changed_startup_surfaces,
                )
                self.assertEqual(
                    tuple(payload["expected_blocking_startup_surfaces"]),
                    report.blocking_startup_surfaces,
                )

    def test_readable_report_payload_contains_nested_compatibility_and_repo_structure(
        self,
    ) -> None:
        report = evaluate_startup_compatibility(
            StartupCompatibilityRequest(
                case_id="shape-check",
                subject_id="opsd-startup-shape",
                machine_id="deployment_instance_lifecycle",
                migration=MigrationDeclaration(
                    migration_id="mig_shape",
                    description="Governed binary upgrade with no protocol drift.",
                    affected_domains=(),
                    startup_surfaces=("binary_version",),
                    replay_required=False,
                    recertification_required=False,
                    new_promotion_packet_required=False,
                    forward_only=False,
                    recoverability_evidence_id=None,
                    rollback_or_restore_path="docs/runbooks/restore_drill_baseline.md",
                    repo_paths=("shared/policy/upgrade_policy.py",),
                ),
                baseline=StartupSnapshot(
                    binary_version="opsd-1.0.0",
                    database_schema_version="schema-1",
                    snapshot_journal_format="journal-1",
                    policy_bundle_hash="policy/sha256:111",
                    artifact_compatibility_matrix="matrix/v1",
                    compatibility_vector=CompatibilityVector(
                        data_protocol="data/v1",
                        strategy_protocol="strategy/v1",
                        ops_protocol="ops/v1",
                        policy_bundle_hash="policy/sha256:111",
                        compatibility_matrix_version="matrix/v1",
                    ),
                ),
                candidate=StartupSnapshot(
                    binary_version="opsd-1.1.0",
                    database_schema_version="schema-1",
                    snapshot_journal_format="journal-1",
                    policy_bundle_hash="policy/sha256:111",
                    artifact_compatibility_matrix="matrix/v1",
                    compatibility_vector=CompatibilityVector(
                        data_protocol="data/v1",
                        strategy_protocol="strategy/v1",
                        ops_protocol="ops/v1",
                        policy_bundle_hash="policy/sha256:111",
                        compatibility_matrix_version="matrix/v1",
                    ),
                ),
            )
        )

        payload = report.to_dict()
        self.assertEqual(LifecycleSpecStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "subject_id",
                "machine_id",
                "status",
                "reason_code",
                "changed_startup_surfaces",
                "blocking_startup_surfaces",
                "replay_required",
                "recertification_required",
                "new_promotion_packet_required",
                "retained_artifacts",
                "repo_structure_report",
                "compatibility_report",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertEqual(RETAINED_MIGRATION_ARTIFACTS, report.retained_artifacts)
        self.assertTrue(payload["repo_structure_report"]["aligned"])
        self.assertEqual("pass", payload["compatibility_report"]["status"])


if __name__ == "__main__":
    unittest.main()
