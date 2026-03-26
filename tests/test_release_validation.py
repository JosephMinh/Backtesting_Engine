"""Contract tests for release validation, sidecar masks, and lifecycle semantics."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.release_validation import (
    DATASET_ALLOWED_TRANSITIONS,
    DERIVED_ALLOWED_TRANSITIONS,
    VALIDATION_ERRORS,
    DatasetLifecycleState,
    DependencyAction,
    DerivedLifecycleState,
    LifecycleStatus,
    NewWorkPosture,
    QualityTier,
    ReleaseCertificationStatus,
    ReleaseKind,
    ReleaseLifecycleTransitionRequest,
    ReleaseValidationRequest,
    ValidationFindingClass,
    ValidationStatus,
    describe_release_lifecycle_state,
    evaluate_release_lifecycle_transition,
    evaluate_release_validation,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "release_validation_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"release validation fixture failed to load: {exc}") from exc


class ReleaseValidationContractTest(unittest.TestCase):
    def test_release_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_validation_finding_catalog_covers_named_failure_modes(self) -> None:
        self.assertEqual(
            {
                "structural_schema_failure",
                "session_misalignment",
                "gaps",
                "price_anomaly",
                "duplicate_or_out_of_order",
                "suspicious_zero_or_locked",
                "event_window_sensitivity",
            },
            {finding_class.value for finding_class in ValidationFindingClass},
        )

    def test_dataset_lifecycle_includes_staging_while_derived_releases_do_not(self) -> None:
        self.assertIn(DatasetLifecycleState.STAGING, DATASET_ALLOWED_TRANSITIONS)
        self.assertNotIn("STAGING", {state.value for state in DerivedLifecycleState})
        self.assertEqual(
            {
                DerivedLifecycleState.CERTIFIED,
                DerivedLifecycleState.REVOKED,
            },
            DERIVED_ALLOWED_TRANSITIONS[DerivedLifecycleState.DRAFT],
        )

    def test_validation_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["validation_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_release_validation(
                    ReleaseValidationRequest(
                        case_id=payload["case_id"],
                        release_id=payload["release_id"],
                        release_kind=ReleaseKind(payload["release_kind"]),
                        structural_schema_failures=payload["structural_schema_failures"],
                        session_misalignment_events=payload["session_misalignment_events"],
                        gap_events=payload["gap_events"],
                        price_anomaly_events=payload["price_anomaly_events"],
                        duplicate_or_out_of_order_events=payload[
                            "duplicate_or_out_of_order_events"
                        ],
                        suspicious_zero_or_locked_events=payload[
                            "suspicious_zero_or_locked_events"
                        ],
                        event_window_sensitive_events=payload["event_window_sensitive_events"],
                        failing_records_preserved=payload["failing_records_preserved"],
                        source_truth_preserved=payload["source_truth_preserved"],
                        destructive_rewrite_attempted=payload[
                            "destructive_rewrite_attempted"
                        ],
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(payload["expected_quality_tier"], report.quality_tier)
                self.assertEqual(
                    payload["expected_certification_status"],
                    report.certification_status,
                )
                self.assertEqual(
                    sorted(payload["expected_mask_classes"]),
                    sorted(mask.finding_class for mask in report.sidecar_masks),
                )

    def test_validation_reports_are_structured_and_operator_readable(self) -> None:
        report = evaluate_release_validation(
            ReleaseValidationRequest(
                case_id="report-shape",
                release_id="analytic_release_gold_masks_v1",
                release_kind=ReleaseKind.ANALYTIC,
                gap_events=2,
                price_anomaly_events=1,
                failing_records_preserved=True,
                source_truth_preserved=True,
            )
        )
        payload = report.to_dict()
        self.assertEqual(ValidationStatus.REVIEW.value, report.status)
        self.assertEqual(QualityTier.DEGRADED.value, report.quality_tier)
        self.assertEqual(
            ReleaseCertificationStatus.BLOCKED.value,
            report.certification_status,
        )
        self.assertTrue(
            {
                "case_id",
                "release_id",
                "release_kind",
                "status",
                "reason_code",
                "quality_tier",
                "certification_status",
                "finding_counts",
                "sidecar_masks",
                "failing_records_preserved",
                "source_truth_preserved",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertEqual(
            {"gaps", "price_anomaly"},
            {mask["finding_class"] for mask in payload["sidecar_masks"]},
        )
        self.assertIn("sidecar masks", report.explanation.lower())

    def test_lifecycle_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["lifecycle_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_release_lifecycle_transition(
                    ReleaseLifecycleTransitionRequest(
                        case_id=payload["case_id"],
                        release_id=payload["release_id"],
                        release_kind=ReleaseKind(payload["release_kind"]),
                        from_state=payload["from_state"],
                        to_state=payload["to_state"],
                        dependent_artifact_ids=tuple(payload["dependent_artifact_ids"]),
                        reproducibility_stamp_present=payload[
                            "reproducibility_stamp_present"
                        ],
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    payload["expected_new_work_posture"],
                    report.new_work_posture,
                )
                self.assertEqual(
                    payload["expected_dependency_action"],
                    report.dependency_action,
                )
                self.assertEqual(
                    payload["expected_reproducibility_preserved"],
                    report.reproducibility_preserved,
                )

    def test_lifecycle_state_semantics_match_release_rules(self) -> None:
        active = describe_release_lifecycle_state(ReleaseKind.DATASET, "ACTIVE")
        superseded = describe_release_lifecycle_state(ReleaseKind.ANALYTIC, "SUPERSEDED")
        quarantined = describe_release_lifecycle_state(ReleaseKind.DATA_PROFILE, "QUARANTINED")
        revoked = describe_release_lifecycle_state(ReleaseKind.DATASET, "REVOKED")

        self.assertEqual(NewWorkPosture.PROMOTABLE.value, active.new_work_posture)
        self.assertEqual(
            DependencyAction.NONE.value,
            active.dependency_action,
        )
        self.assertEqual(
            NewWorkPosture.REPRODUCIBLE_ONLY.value,
            superseded.new_work_posture,
        )
        self.assertTrue(superseded.reproducible)
        self.assertEqual(
            DependencyAction.BLOCK_NEW_EXPERIMENTS.value,
            quarantined.dependency_action,
        )
        self.assertTrue(quarantined.blocks_new_experiments)
        self.assertEqual(NewWorkPosture.SUSPECT.value, revoked.new_work_posture)
        self.assertTrue(revoked.marks_dependents_suspect)

    def test_transition_reports_are_structured(self) -> None:
        report = evaluate_release_lifecycle_transition(
            ReleaseLifecycleTransitionRequest(
                case_id="transition-shape",
                release_id="dataset_release_gold_2026q1_v1",
                release_kind=ReleaseKind.DATASET,
                from_state="ACTIVE",
                to_state="SUPERSEDED",
                dependent_artifact_ids=("analytic_release_gold_masks_v1",),
                reproducibility_stamp_present=True,
            )
        )
        payload = report.to_dict()
        self.assertEqual(LifecycleStatus.PASS.value, report.status)
        self.assertEqual(
            DependencyAction.FREEZE_EXISTING_REFERENCES.value,
            report.dependency_action,
        )
        self.assertEqual(
            NewWorkPosture.REPRODUCIBLE_ONLY.value,
            report.new_work_posture,
        )
        self.assertTrue(
            {
                "case_id",
                "release_id",
                "release_kind",
                "status",
                "reason_code",
                "from_state",
                "to_state",
                "new_work_posture",
                "dependency_action",
                "reproducibility_preserved",
                "dependent_artifact_ids",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("reproducible", report.explanation.lower())


if __name__ == "__main__":
    unittest.main()
