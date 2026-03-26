import json
import unittest
from pathlib import Path

from shared.policy.storage_tiers import (
    ContractStatus,
    PromotableExperimentBinding,
    STORAGE_ARTIFACT_CLASSES,
    StorageTier,
    TierAssignmentRequest,
    VALIDATION_ERRORS,
    artifact_classes_by_type,
    artifacts_by_tier,
    evaluate_tier_assignment,
    validate_promotable_experiment_binding,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "storage_tiers.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"storage tier fixture failed to load: {exc}") from exc


class StorageTierContractTest(unittest.TestCase):
    def test_storage_catalog_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_every_storage_tier_is_explicit_and_non_empty(self) -> None:
        self.assertTrue(STORAGE_ARTIFACT_CLASSES)
        for storage_tier in StorageTier:
            with self.subTest(storage_tier=storage_tier.value):
                self.assertTrue(artifacts_by_tier(storage_tier))

    def test_core_artifacts_land_in_expected_tiers(self) -> None:
        artifact_index = artifact_classes_by_type()
        self.assertEqual(StorageTier.TIER_A, artifact_index["raw_vendor_payload"].storage_tier)
        self.assertEqual(StorageTier.TIER_B, artifact_index["resolved_context_bundle"].storage_tier)
        self.assertEqual(StorageTier.TIER_C, artifact_index["dataset_release"].storage_tier)
        self.assertEqual(StorageTier.TIER_C, artifact_index["data_profile_release"].storage_tier)
        self.assertEqual(StorageTier.TIER_D, artifact_index["analytic_release"].storage_tier)
        self.assertEqual(StorageTier.TIER_E, artifact_index["parity_report"].storage_tier)

    def test_tier_assignment_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["tier_assignment_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_tier_assignment(
                    TierAssignmentRequest(
                        case_id=payload["case_id"],
                        artifact_type=payload["artifact_type"],
                        requested_tier=StorageTier(payload["requested_tier"]),
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(payload["expected_tier"], report.expected_tier)

    def test_tier_assignment_reports_are_structured(self) -> None:
        report = evaluate_tier_assignment(
            TierAssignmentRequest(
                case_id="report-shape",
                artifact_type="dataset_release",
                requested_tier=StorageTier.TIER_C,
            )
        )
        payload = report.to_dict()
        self.assertEqual(ContractStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "artifact_type",
                "status",
                "reason_code",
                "requested_tier",
                "expected_tier",
                "durability_role",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )

    def test_promotable_binding_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["binding_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_promotable_experiment_binding(
                    PromotableExperimentBinding(
                        case_id=payload["case_id"],
                        experiment_id=payload["experiment_id"],
                        dataset_release_id=payload["dataset_release_id"],
                        analytic_release_id=payload["analytic_release_id"],
                        data_profile_release_id=payload["data_profile_release_id"],
                        observation_cutoff_utc=payload["observation_cutoff_utc"],
                        resolved_context_bundle_id=payload["resolved_context_bundle_id"],
                        policy_bundle_hash=payload["policy_bundle_hash"],
                        compatibility_matrix_version=payload["compatibility_matrix_version"],
                        mutable_reference_reads=tuple(payload["mutable_reference_reads"]),
                        binding_mutated_after_freeze=payload["binding_mutated_after_freeze"],
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_promotable_binding_freezes_exact_artifact_set_and_cutoff(self) -> None:
        report = validate_promotable_experiment_binding(
            PromotableExperimentBinding(
                case_id="freeze-shape",
                experiment_id="run-freeze-shape",
                dataset_release_id="dataset_release_gold_2026q1_v1",
                analytic_release_id="analytic_release_gold_masks_v1",
                data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                observation_cutoff_utc="2026-03-01T00:00:00+00:00",
                resolved_context_bundle_id="resolved_context_bundle_xnys_comex_2026q1_v1",
                policy_bundle_hash="policy_bundle_sha256_001",
                compatibility_matrix_version="compat_matrix_v1",
            )
        )
        payload = report.to_dict()
        self.assertEqual(ContractStatus.PASS.value, report.status)
        self.assertEqual("2026-03-01T00:00:00+00:00", report.observation_cutoff_utc)
        self.assertEqual(
            {
                "dataset_release_id",
                "analytic_release_id",
                "data_profile_release_id",
                "observation_cutoff_utc",
                "resolved_context_bundle_id",
                "policy_bundle_hash",
                "compatibility_matrix_version",
            },
            set(report.actual_artifact_set.keys()),
        )
        self.assertTrue(
            {
                "case_id",
                "experiment_id",
                "status",
                "reason_code",
                "required_artifact_set",
                "actual_artifact_set",
                "observation_cutoff_utc",
                "mutable_reference_reads",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )


if __name__ == "__main__":
    unittest.main()
