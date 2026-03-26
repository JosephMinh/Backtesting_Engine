"""Contract tests for integrity-bound artifacts and freshness-bound evidence."""

from __future__ import annotations

import unittest

from shared.policy.artifact_classes import (
    ArtifactClass,
    DependencyState,
    FreshnessState,
    VALIDATION_ERRORS,
    evaluate_artifact_admissibility,
    evaluate_gate_admissibility,
    freshness_bound_evidence_ids,
    get_artifact_definition,
    integrity_bound_artifact_ids,
)


class TestArtifactClassificationRegistry(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self):
        self.assertEqual([], VALIDATION_ERRORS)

    def test_integrity_and_freshness_registries_are_explicit(self):
        self.assertEqual(len(integrity_bound_artifact_ids()), 11)
        self.assertEqual(len(freshness_bound_evidence_ids()), 11)
        self.assertIn("resolved_context_bundle", integrity_bound_artifact_ids())
        self.assertIn("session_readiness_packet", freshness_bound_evidence_ids())

    def test_resolved_context_bundle_stays_integrity_bound(self):
        definition = get_artifact_definition("resolved_context_bundle")
        self.assertEqual(definition.artifact_class, ArtifactClass.INTEGRITY_BOUND)
        self.assertIn("do not expire", definition.expected_control.lower())


class TestArtifactAdmissibility(unittest.TestCase):
    def test_integrity_bound_artifact_ignores_freshness_expiry(self):
        diagnostic = evaluate_artifact_admissibility(
            "resolved_context_bundle",
            dependency_state=DependencyState.VALID,
            freshness_state=FreshnessState.EXPIRED,
        )
        self.assertEqual(diagnostic.status, "pass")
        self.assertTrue(diagnostic.admissible)
        self.assertEqual(diagnostic.invalidation_channel, "none")

    def test_freshness_bound_artifact_expires(self):
        diagnostic = evaluate_artifact_admissibility(
            "session_readiness_packet",
            freshness_state=FreshnessState.EXPIRED,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertFalse(diagnostic.admissible)
        self.assertEqual(diagnostic.reason_code, "ARTIFACT_FRESHNESS_EXPIRED")
        self.assertEqual(diagnostic.invalidation_channel, "freshness")

    def test_freshness_bound_artifact_rejects_incompatible_supersession(self):
        diagnostic = evaluate_artifact_admissibility(
            "paper_pass_evidence",
            freshness_state=FreshnessState.SUPERSEDED_INCOMPATIBLE,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "ARTIFACT_FRESHNESS_SUPERSEDED_INCOMPATIBLY",
        )

    def test_dependency_quarantine_blocks_even_integrity_bound_artifacts(self):
        diagnostic = evaluate_artifact_admissibility(
            "dataset_release",
            dependency_state=DependencyState.QUARANTINED,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "ARTIFACT_DEPENDENCY_QUARANTINED",
        )
        self.assertEqual(diagnostic.invalidation_channel, "dependency")

    def test_dependency_recertification_is_distinct_from_freshness_expiry(self):
        diagnostic = evaluate_artifact_admissibility(
            "databento_ibkr_bar_parity_study",
            dependency_state=DependencyState.RECERT_REQUIRED,
            freshness_state=FreshnessState.FRESH,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "ARTIFACT_DEPENDENCY_RECERT_REQUIRED",
        )
        self.assertEqual(diagnostic.invalidation_channel, "dependency")


class TestGateAdmissibility(unittest.TestCase):
    def test_gate_distinguishes_dependency_invalidation_from_freshness_failure(self):
        result = evaluate_gate_admissibility(
            gate_name="promotion_packet",
            integrity_artifacts=[
                {
                    "artifact_id": "resolved_context_bundle",
                    "dependency_state": "valid",
                    "freshness_state": "expired",
                },
                {
                    "artifact_id": "candidate_bundle",
                    "dependency_state": "quarantined",
                },
            ],
            freshness_evidence=[
                {
                    "artifact_id": "session_readiness_packet",
                    "dependency_state": "valid",
                    "freshness_state": "expired",
                },
                {
                    "artifact_id": "paper_pass_evidence",
                    "dependency_state": "valid",
                    "freshness_state": "superseded_compatible",
                },
            ],
        )

        self.assertFalse(result["allowed"])
        self.assertFalse(result["integrity_ready"])
        self.assertFalse(result["freshness_ready"])
        self.assertTrue(result["requires_dependency_review"])
        self.assertTrue(result["requires_new_freshness_evidence"])
        self.assertEqual(len(result["dependency_invalidations"]), 1)
        self.assertEqual(
            result["dependency_invalidations"][0]["reason_code"],
            "ARTIFACT_DEPENDENCY_QUARANTINED",
        )
        self.assertEqual(len(result["freshness_failures"]), 1)
        self.assertEqual(
            result["freshness_failures"][0]["reason_code"],
            "ARTIFACT_FRESHNESS_EXPIRED",
        )

    def test_gate_passes_when_integrity_is_valid_and_freshness_is_current(self):
        result = evaluate_gate_admissibility(
            gate_name="session_activation",
            integrity_artifacts=[
                {"artifact_id": "resolved_context_bundle"},
                {"artifact_id": "signed_manifest"},
            ],
            freshness_evidence=[
                {
                    "artifact_id": "session_readiness_packet",
                    "freshness_state": "fresh",
                },
                {
                    "artifact_id": "broker_margin_snapshot",
                    "freshness_state": "superseded_compatible",
                },
            ],
        )

        self.assertTrue(result["allowed"])
        self.assertTrue(result["integrity_ready"])
        self.assertTrue(result["freshness_ready"])
        self.assertFalse(result["requires_dependency_review"])
        self.assertFalse(result["requires_new_freshness_evidence"])


if __name__ == "__main__":
    unittest.main()
