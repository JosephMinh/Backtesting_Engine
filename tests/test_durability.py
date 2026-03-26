"""Contract tests for durability, backup, restore, and restore-drill policy."""

from __future__ import annotations

import unittest

from shared.policy.durability import (
    DURABILITY_CONTROLS,
    RECOVERY_OBJECTIVES,
    durability_control_keys,
    evaluate_backup_coverage,
    evaluate_durability_policy,
    evaluate_off_host_durability,
    evaluate_recovery_objective,
    evaluate_restore_artifacts,
    evaluate_restore_drill,
    evaluate_tamper_evidence,
    recovery_objective_keys,
)


def healthy_backup_posture() -> dict[str, object]:
    return {
        "recovery_point_lag_minutes": 5,
        "wal_archiving_enabled": True,
        "equivalent_point_in_time_coverage": False,
        "backup_freshness_green": True,
        "off_host_storage_present": True,
        "storage_mode": "versioned",
        "same_failure_domain": False,
        "journals_hash_chained": True,
        "snapshot_barriers_hash_chained": True,
    }


def healthy_restore_evidence() -> dict[str, object]:
    return {
        "restore_manifest_present": True,
        "manifest_binds_database_backup": True,
        "manifest_binds_artifact_checkpoint": True,
        "restore_runbook_present": True,
    }


def healthy_restore_drill() -> dict[str, object]:
    return {
        "before_first_live_approval": False,
        "last_drill_age_days": 30,
        "last_drill_succeeded": True,
        "files_restored": 120,
        "expected_files": 120,
        "hashes_match": True,
        "recovery_point_verified": True,
        "structured_logs_present": True,
        "timing_metrics_present": True,
        "data_loss_window_measured": True,
        "rpo_metric_present": True,
        "rto_metric_present": True,
        "correlation_id_present": True,
        "expected_vs_actual_diff_present": True,
        "artifact_manifest_present": True,
        "operator_reason_bundle_present": True,
        "idempotent": True,
        "safe_for_test_environments": True,
    }


def healthy_recovery_metrics() -> dict[str, object]:
    return {
        "measured_data_loss_window_minutes": 4,
        "measured_rto_minutes": 90,
        "deterministic_vendor_repull_documented": True,
    }


class TestDurabilityRegistry(unittest.TestCase):
    def test_control_registry_is_explicit(self):
        self.assertEqual(len(DURABILITY_CONTROLS), 5)
        self.assertEqual(
            durability_control_keys(),
            [
                "postgres_pitr_backup",
                "off_host_durability",
                "tamper_evident_journals",
                "restore_evidence",
                "restore_drill",
            ],
        )
        self.assertTrue(all(control.plan_section == "3.6" for control in DURABILITY_CONTROLS))

    def test_recovery_objectives_are_explicit(self):
        self.assertEqual(len(RECOVERY_OBJECTIVES), 3)
        self.assertEqual(
            recovery_objective_keys(),
            [
                "canonical_metadata_and_live_state",
                "live_capable_host",
                "raw_historical_reingestion",
            ],
        )


class TestDurabilityChecks(unittest.TestCase):
    def test_backup_coverage_passes_when_pitr_and_freshness_are_green(self):
        diagnostic = evaluate_backup_coverage(
            recovery_point_lag_minutes=3,
            wal_archiving_enabled=True,
            equivalent_point_in_time_coverage=False,
            backup_freshness_green=True,
        )
        self.assertEqual(diagnostic.status, "pass")
        self.assertIsNone(diagnostic.reason_code)

    def test_backup_coverage_rejects_missing_pitr(self):
        diagnostic = evaluate_backup_coverage(
            recovery_point_lag_minutes=3,
            wal_archiving_enabled=False,
            equivalent_point_in_time_coverage=False,
            backup_freshness_green=True,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "DURABILITY_BACKUP_PITR_NOT_AVAILABLE",
        )

    def test_off_host_durability_rejects_shared_failure_domain(self):
        diagnostic = evaluate_off_host_durability(
            off_host_storage_present=True,
            storage_mode="versioned",
            same_failure_domain=True,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "DURABILITY_FAILURE_DOMAIN_SHARED",
        )

    def test_tamper_evidence_requires_hash_chaining(self):
        diagnostic = evaluate_tamper_evidence(
            journals_hash_chained=True,
            snapshot_barriers_hash_chained=False,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "DURABILITY_HASH_CHAIN_INCOMPLETE",
        )

    def test_restore_artifacts_require_manifest_binding_and_runbook(self):
        diagnostic = evaluate_restore_artifacts(
            restore_manifest_present=True,
            manifest_binds_database_backup=True,
            manifest_binds_artifact_checkpoint=False,
            restore_runbook_present=True,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "DURABILITY_RESTORE_MANIFEST_INCOMPLETE",
        )


class TestRestoreDrillChecks(unittest.TestCase):
    def test_restore_drill_requires_quarterly_success_after_live_activation(self):
        drill = healthy_restore_drill()
        drill["last_drill_age_days"] = 120

        diagnostics = evaluate_restore_drill(**drill)
        self.assertEqual(diagnostics[0].status, "violation")
        self.assertEqual(
            diagnostics[0].reason_code,
            "DURABILITY_RESTORE_DRILL_STALE",
        )

    def test_restore_drill_requires_integrity_verification(self):
        drill = healthy_restore_drill()
        drill["files_restored"] = 119

        diagnostics = evaluate_restore_drill(**drill)
        integrity = next(
            item
            for item in diagnostics
            if item.evidence_surface == "restore_drill_integrity"
        )
        self.assertEqual(integrity.status, "violation")
        self.assertEqual(
            integrity.reason_code,
            "DURABILITY_RESTORE_INTEGRITY_FAILED",
        )

    def test_restore_drill_requires_structured_observability_bundle(self):
        drill = healthy_restore_drill()
        drill["operator_reason_bundle_present"] = False

        diagnostics = evaluate_restore_drill(**drill)
        observability = next(
            item
            for item in diagnostics
            if item.evidence_surface == "restore_drill_observability"
        )
        self.assertEqual(observability.status, "violation")
        self.assertEqual(
            observability.reason_code,
            "DURABILITY_RESTORE_OBSERVABILITY_INCOMPLETE",
        )

    def test_restore_drill_requires_idempotent_test_safe_workflow(self):
        drill = healthy_restore_drill()
        drill["idempotent"] = False

        diagnostics = evaluate_restore_drill(**drill)
        safety = next(
            item for item in diagnostics if item.evidence_surface == "restore_drill_safety"
        )
        self.assertEqual(safety.status, "violation")
        self.assertEqual(
            safety.reason_code,
            "DURABILITY_RESTORE_DRILL_NOT_SAFE",
        )


class TestRecoveryObjectives(unittest.TestCase):
    def test_recovery_objectives_reject_rpo_rto_or_missing_repull_docs(self):
        rpo = evaluate_recovery_objective(
            "canonical_metadata_and_live_state",
            measured_data_loss_window_minutes=18,
            measured_rto_minutes=90,
            deterministic_vendor_repull_documented=True,
        )
        self.assertEqual(rpo.status, "violation")
        self.assertEqual(rpo.reason_code, "DURABILITY_RPO_TARGET_MISSED")

        rto = evaluate_recovery_objective(
            "live_capable_host",
            measured_data_loss_window_minutes=4,
            measured_rto_minutes=400,
            deterministic_vendor_repull_documented=True,
        )
        self.assertEqual(rto.status, "violation")
        self.assertEqual(rto.reason_code, "DURABILITY_RTO_TARGET_MISSED")

        raw = evaluate_recovery_objective(
            "raw_historical_reingestion",
            measured_data_loss_window_minutes=4,
            measured_rto_minutes=90,
            deterministic_vendor_repull_documented=False,
        )
        self.assertEqual(raw.status, "violation")
        self.assertEqual(
            raw.reason_code,
            "DURABILITY_RAW_REINGESTION_UNDOCUMENTED",
        )


class TestAggregatePolicyEvaluation(unittest.TestCase):
    def test_healthy_durability_policy_passes_and_exposes_readiness_inputs(self):
        result = evaluate_durability_policy(
            backup_posture=healthy_backup_posture(),
            restore_evidence=healthy_restore_evidence(),
            restore_drill=healthy_restore_drill(),
            recovery_metrics=healthy_recovery_metrics(),
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(
            result["readiness_inputs"],
            {
                "backup_freshness_green": True,
                "restore_drill_green": True,
                "restore_evidence_green": True,
                "promotion_gate_ready": True,
            },
        )
        self.assertTrue(
            all(item["status"] == "pass" for item in result["diagnostics"])
        )

    def test_policy_evaluation_collects_restore_and_target_failures(self):
        backup_posture = healthy_backup_posture()
        backup_posture["same_failure_domain"] = True

        restore_evidence = healthy_restore_evidence()
        restore_evidence["restore_runbook_present"] = False

        restore_drill = healthy_restore_drill()
        restore_drill["expected_vs_actual_diff_present"] = False

        recovery_metrics = healthy_recovery_metrics()
        recovery_metrics["measured_rto_minutes"] = 500

        result = evaluate_durability_policy(
            backup_posture=backup_posture,
            restore_evidence=restore_evidence,
            restore_drill=restore_drill,
            recovery_metrics=recovery_metrics,
        )

        self.assertFalse(result["allowed"])
        self.assertFalse(result["readiness_inputs"]["promotion_gate_ready"])
        reason_codes = {item["reason_code"] for item in result["diagnostics"]}
        self.assertIn("DURABILITY_FAILURE_DOMAIN_SHARED", reason_codes)
        self.assertIn("DURABILITY_RESTORE_RUNBOOK_MISSING", reason_codes)
        self.assertIn("DURABILITY_RESTORE_OBSERVABILITY_INCOMPLETE", reason_codes)
        self.assertIn("DURABILITY_RTO_TARGET_MISSED", reason_codes)
