"""Contract tests for signed release certification and correction handling."""

from __future__ import annotations

import unittest

from shared.policy.release_certification import (
    VALIDATION_ERRORS,
    CorrectionImpactClass,
    DependentPolicyUpdate,
    DependentSurfaceKind,
    DependentUpdateAction,
    ReleaseCertificationRecord,
    ReleaseCorrectionEvent,
    evaluate_release_correction,
    policy_actions_for_impact_class,
    validate_release_certification,
)
from shared.policy.release_schemas import ReleaseLifecycleState, ReleaseStatus


def make_certification_record(
    *,
    canary_required: bool = True,
    lifecycle_state: ReleaseLifecycleState = ReleaseLifecycleState.CERTIFIED,
    canary_ids: tuple[str, ...] = ("parity_fixture_gc_2026q1_v1",),
) -> ReleaseCertificationRecord:
    return ReleaseCertificationRecord(
        certification_id="release_cert_gc_2026q1_v1",
        release_kind="dataset_release",
        release_id="dataset_release_gc_2026q1_v1",
        deterministic_manifest_hash="manifest_sha256_001",
        prior_release_semantic_diff_hash="semantic_diff_sha256_001",
        validation_summary_hash="validation_summary_sha256_001",
        policy_evaluation_hash="policy_eval_sha256_001",
        canary_or_parity_required=canary_required,
        canary_or_parity_evidence_ids=canary_ids,
        signed_certification_report_hash="signed_cert_report_sha256_001",
        signer_ids=("ops_reviewer_a", "risk_reviewer_b"),
        certified_at_utc="2026-03-26T16:00:00+00:00",
        lifecycle_state=lifecycle_state,
    )


def make_correction_event(
    *,
    impact_class: CorrectionImpactClass = CorrectionImpactClass.RECERT_REQUIRED,
    dependent_updates: tuple[DependentPolicyUpdate, ...] | None = None,
    superseding_release_id: str | None = "dataset_release_gc_2026q1_v2",
) -> ReleaseCorrectionEvent:
    if dependent_updates is None:
        dependent_updates = (
            DependentPolicyUpdate(
                surface_kind=DependentSurfaceKind.ANALYTIC_RELEASE,
                surface_id="analytic_release_gc_features_v1",
                action=DependentUpdateAction.RECERTIFY,
                reason_bundle="Upstream correction materially changed certified input rows.",
            ),
            DependentPolicyUpdate(
                surface_kind=DependentSurfaceKind.CANDIDATE_READINESS_RECORD,
                surface_id="readiness_gc_candidate_v3",
                action=DependentUpdateAction.SUPERSEDE,
                reason_bundle="Dependent candidate readiness must point at the superseding dataset release.",
            ),
        )

    return ReleaseCorrectionEvent(
        correction_event_id="release_correction_gc_2026q1_v2",
        release_kind="dataset_release",
        release_id="dataset_release_gc_2026q1_v1",
        certified_vendor_revision_watermark="vendor_rev_2026-03-20",
        corrected_vendor_revision_watermark="vendor_rev_2026-03-25",
        semantic_impact_diff_hash="semantic_diff_sha256_002",
        impact_class=impact_class,
        preserves_prior_reproducibility=True,
        superseding_release_id=superseding_release_id,
        dependent_updates=dependent_updates,
        justification="The corrected vendor revision changes certified records after publication.",
        recorded_at_utc="2026-03-26T16:05:00+00:00",
    )


class ReleaseCertificationContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_records(self) -> None:
        certification = make_certification_record()
        correction = make_correction_event()

        self.assertEqual(
            certification,
            ReleaseCertificationRecord.from_json(certification.to_json()),
        )
        self.assertEqual(
            correction,
            ReleaseCorrectionEvent.from_json(correction.to_json()),
        )

    def test_certification_requires_release_evidence_and_usable_state(self) -> None:
        good_report = validate_release_certification(make_certification_record())
        draft_report = validate_release_certification(
            make_certification_record(lifecycle_state=ReleaseLifecycleState.DRAFT)
        )

        self.assertEqual(ReleaseStatus.PASS.value, good_report.status)
        self.assertTrue(good_report.usable)
        self.assertEqual("RELEASE_CERTIFICATION_USABLE", good_report.reason_code)
        self.assertEqual(ReleaseStatus.VIOLATION.value, draft_report.status)
        self.assertFalse(draft_report.usable)
        self.assertEqual(
            "RELEASE_CERTIFICATION_RELEASE_NOT_USABLE_STATE",
            draft_report.reason_code,
        )

    def test_certification_rejects_missing_required_canary_evidence(self) -> None:
        report = validate_release_certification(
            make_certification_record(canary_required=True, canary_ids=())
        )

        self.assertEqual(ReleaseStatus.VIOLATION.value, report.status)
        self.assertEqual(
            "RELEASE_CERTIFICATION_CANARY_EVIDENCE_REQUIRED",
            report.reason_code,
        )

    def test_policy_actions_for_impact_classes_are_explicit(self) -> None:
        self.assertEqual(("retain", "annotate"), policy_actions_for_impact_class(CorrectionImpactClass.NONE))
        self.assertEqual(
            ("recertify", "supersede"),
            policy_actions_for_impact_class(CorrectionImpactClass.RECERT_REQUIRED),
        )
        self.assertEqual(
            ("quarantine", "supersede"),
            policy_actions_for_impact_class(CorrectionImpactClass.SUSPECT),
        )

    def test_correction_event_passes_with_policy_matched_actions(self) -> None:
        report = evaluate_release_correction(make_correction_event())

        self.assertEqual(ReleaseStatus.PASS.value, report.status)
        self.assertEqual("RELEASE_CORRECTION_POLICY_CLASSIFIED", report.reason_code)
        self.assertIn("recertify", report.dependent_actions)
        self.assertIn("supersede", report.dependent_actions)

    def test_correction_event_rejects_action_mismatch(self) -> None:
        report = evaluate_release_correction(
            make_correction_event(
                impact_class=CorrectionImpactClass.DIAGNOSTIC_ONLY,
                dependent_updates=(
                    DependentPolicyUpdate(
                        surface_kind=DependentSurfaceKind.PORTABILITY_STUDY,
                        surface_id="portability_gc_mgc_v4",
                        action=DependentUpdateAction.RECERTIFY,
                        reason_bundle="This should not be allowed for diagnostic-only impact.",
                    ),
                ),
                superseding_release_id=None,
            )
        )

        self.assertEqual(ReleaseStatus.VIOLATION.value, report.status)
        self.assertEqual(
            "RELEASE_CORRECTION_POLICY_ACTION_MISMATCH",
            report.reason_code,
        )

    def test_correction_event_requires_superseding_release_for_supersede_action(self) -> None:
        report = evaluate_release_correction(
            make_correction_event(superseding_release_id=None)
        )

        self.assertEqual(ReleaseStatus.INVALID.value, report.status)
        self.assertEqual(
            "RELEASE_CORRECTION_SUPERSESSION_REQUIRES_RELEASE_ID",
            report.reason_code,
        )


if __name__ == "__main__":
    unittest.main()
