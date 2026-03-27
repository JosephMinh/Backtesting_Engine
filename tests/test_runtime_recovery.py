"""Contract tests for runtime recovery, degradation, reconciliation, and restore drills."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.deployment_packets import PacketStatus
from shared.policy.runtime_recovery import (
    VALIDATION_ERRORS,
    DegradationAssessment,
    GracefulShutdownRecord,
    LedgerCloseArtifact,
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


if __name__ == "__main__":
    unittest.main()
