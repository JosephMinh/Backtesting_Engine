"""Contract tests for runtime recovery, degradation, reconciliation, and restore drills."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.deployment_packets import PacketStatus
from shared.policy.runtime_recovery import (
    VALIDATION_ERRORS,
    DegradationAssessment,
    GracefulShutdownRecord,
    LedgerCloseArtifact,
    RecoveryValidationReport,
    RecoveryFenceRequest,
    RestoreDrillArtifact,
    validate_degradation_assessment,
    validate_graceful_shutdown,
    validate_ledger_close,
    validate_recovery_fence,
    validate_restore_drill,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "runtime_recovery_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"runtime recovery fixture failed to load: {exc}") from exc


def build_recovery(payload: dict[str, object]) -> RecoveryFenceRequest:
    return RecoveryFenceRequest.from_dict(payload)


def build_shutdown(payload: dict[str, object]) -> GracefulShutdownRecord:
    return GracefulShutdownRecord.from_dict(payload)


def build_degradation(payload: dict[str, object]) -> DegradationAssessment:
    return DegradationAssessment.from_dict(payload)


def build_ledger_close(payload: dict[str, object]) -> LedgerCloseArtifact:
    return LedgerCloseArtifact.from_dict(payload)


def build_restore(payload: dict[str, object]) -> RestoreDrillArtifact:
    return RestoreDrillArtifact.from_dict(payload)


class RuntimeRecoveryContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_all_runtime_recovery_artifacts(self) -> None:
        fixtures = load_cases()
        recovery = build_recovery(fixtures["recovery_fence_cases"][0]["payload"])
        shutdown = build_shutdown(fixtures["graceful_shutdown_cases"][0]["payload"])
        degradation = build_degradation(fixtures["degradation_cases"][0]["payload"])
        ledger_close = build_ledger_close(fixtures["ledger_close_cases"][0]["payload"])
        restore = build_restore(fixtures["restore_drill_cases"][0]["payload"])

        self.assertEqual(recovery, RecoveryFenceRequest.from_json(recovery.to_json()))
        self.assertEqual(shutdown, GracefulShutdownRecord.from_json(shutdown.to_json()))
        self.assertEqual(
            degradation,
            DegradationAssessment.from_json(degradation.to_json()),
        )
        self.assertEqual(
            ledger_close,
            LedgerCloseArtifact.from_json(ledger_close.to_json()),
        )
        self.assertEqual(restore, RestoreDrillArtifact.from_json(restore.to_json()))

    def test_artifact_loaders_reject_invalid_boundary_values(self) -> None:
        fixtures = load_cases()
        recovery_payload = deepcopy(fixtures["recovery_fence_cases"][0]["payload"])
        recovery_payload["entered_recovering_state"] = "true"
        with self.assertRaisesRegex(ValueError, "entered_recovering_state: must be boolean"):
            RecoveryFenceRequest.from_dict(recovery_payload)

        recovery_payload = deepcopy(fixtures["recovery_fence_cases"][0]["payload"])
        recovery_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version: missing required field"):
            RecoveryFenceRequest.from_dict(recovery_payload)

        recovery_payload = deepcopy(fixtures["recovery_fence_cases"][0]["payload"])
        recovery_payload.pop("fresh_session_packet")
        with self.assertRaisesRegex(ValueError, "fresh_session_packet: missing required field"):
            RecoveryFenceRequest.from_dict(recovery_payload)

        shutdown_payload = deepcopy(fixtures["graceful_shutdown_cases"][0]["payload"])
        shutdown_payload["schema_version"] = 2
        with self.assertRaisesRegex(
            ValueError,
            "schema_version: unsupported schema version 2; expected 1",
        ):
            GracefulShutdownRecord.from_dict(shutdown_payload)

        shutdown_payload = deepcopy(fixtures["graceful_shutdown_cases"][0]["payload"])
        shutdown_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version: missing required field"):
            GracefulShutdownRecord.from_dict(shutdown_payload)

        degradation_payload = deepcopy(fixtures["degradation_cases"][0]["payload"])
        degradation_payload["operator_reason_bundle"] = "reason"
        with self.assertRaisesRegex(
            ValueError,
            "operator_reason_bundle: must be a list of strings",
        ):
            DegradationAssessment.from_dict(degradation_payload)

        degradation_payload = deepcopy(fixtures["degradation_cases"][0]["payload"])
        degradation_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version: missing required field"):
            DegradationAssessment.from_dict(degradation_payload)

        ledger_payload = deepcopy(fixtures["ledger_close_cases"][0]["payload"])
        ledger_payload["next_session_eligibility"] = "resume"
        with self.assertRaisesRegex(
            ValueError,
            "next_session_eligibility: must be a valid next-session eligibility",
        ):
            LedgerCloseArtifact.from_dict(ledger_payload)

        ledger_payload = deepcopy(fixtures["ledger_close_cases"][0]["payload"])
        ledger_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version: missing required field"):
            LedgerCloseArtifact.from_dict(ledger_payload)

        ledger_payload = deepcopy(fixtures["ledger_close_cases"][0]["payload"])
        ledger_payload.pop("review_or_waiver_id")
        with self.assertRaisesRegex(ValueError, "review_or_waiver_id: missing required field"):
            LedgerCloseArtifact.from_dict(ledger_payload)

        restore_payload = deepcopy(fixtures["restore_drill_cases"][0]["payload"])
        restore_payload["rpo_target_minutes"] = True
        with self.assertRaisesRegex(ValueError, "rpo_target_minutes: must be an integer"):
            RestoreDrillArtifact.from_dict(restore_payload)

        restore_payload = deepcopy(fixtures["restore_drill_cases"][0]["payload"])
        restore_payload.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "schema_version: missing required field"):
            RestoreDrillArtifact.from_dict(restore_payload)

        restore_payload = deepcopy(fixtures["restore_drill_cases"][0]["payload"])
        restore_payload.pop("reviewed_waiver_id")
        with self.assertRaisesRegex(ValueError, "reviewed_waiver_id: missing required field"):
            RestoreDrillArtifact.from_dict(restore_payload)

    def test_recovery_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["recovery_fence_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_recovery_fence(
                    payload["case_id"],
                    build_recovery(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_shutdown_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["graceful_shutdown_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_graceful_shutdown(
                    payload["case_id"],
                    build_shutdown(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_degradation_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["degradation_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_degradation_assessment(
                    payload["case_id"],
                    build_degradation(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_ledger_close_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["ledger_close_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_ledger_close(
                    payload["case_id"],
                    build_ledger_close(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_restore_drill_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["restore_drill_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_restore_drill(
                    payload["case_id"],
                    build_restore(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_recovery_report_is_structured_and_mentions_recovering(self) -> None:
        report = validate_recovery_fence(
            "recovery-shape",
            build_recovery(load_cases()["recovery_fence_cases"][0]["payload"]),
        )
        payload = report.to_dict()
        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertEqual("recovery_fence", report.artifact_kind)
        self.assertIn("recovering", report.explanation.lower())
        self.assertTrue(
            {
                "case_id",
                "artifact_kind",
                "artifact_id",
                "status",
                "reason_code",
                "context",
                "missing_fields",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )

    def test_recovery_validation_report_round_trip_preserves_emitted_shape(self) -> None:
        report = validate_recovery_fence(
            "recovery-shape",
            build_recovery(load_cases()["recovery_fence_cases"][0]["payload"]),
        )
        self.assertEqual(
            report.to_dict(),
            RecoveryValidationReport.from_json(report.to_json()).to_dict(),
        )

    def test_recovery_validation_report_loader_rejects_invalid_boundary_values(self) -> None:
        report = validate_recovery_fence(
            "recovery-shape",
            build_recovery(load_cases()["recovery_fence_cases"][0]["payload"]),
        )
        payload = report.to_dict()

        invalid_status = deepcopy(payload)
        invalid_status["status"] = "ship"
        with self.assertRaisesRegex(ValueError, "status: must be a valid packet status"):
            RecoveryValidationReport.from_dict(invalid_status)

        invalid_missing_fields = deepcopy(payload)
        invalid_missing_fields["missing_fields"] = "field"
        with self.assertRaisesRegex(
            ValueError,
            "missing_fields: must be a list of strings",
        ):
            RecoveryValidationReport.from_dict(invalid_missing_fields)

        missing_artifact_id = deepcopy(payload)
        missing_artifact_id.pop("artifact_id")
        with self.assertRaisesRegex(ValueError, "artifact_id: missing required field"):
            RecoveryValidationReport.from_dict(missing_artifact_id)

        missing_context = deepcopy(payload)
        missing_context.pop("context")
        with self.assertRaisesRegex(ValueError, "context: missing required field"):
            RecoveryValidationReport.from_dict(missing_context)

        invalid_timestamp = deepcopy(payload)
        invalid_timestamp["timestamp"] = "2026-03-28T00:00:00"
        with self.assertRaisesRegex(ValueError, "timestamp: must be timezone-aware"):
            RecoveryValidationReport.from_dict(invalid_timestamp)


if __name__ == "__main__":
    unittest.main()
