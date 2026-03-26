"""Contract tests for candidate, readiness, deployment, promotion, and session packets."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.deployment_packets import (
    VALIDATION_ERRORS,
    CandidateBundle,
    BundleReadinessRecord,
    DeploymentInstance,
    DeploymentState,
    PacketStatus,
    PromotionPacket,
    ReadinessState,
    SessionReadinessPacket,
    SessionReadinessStatus,
    transition_bundle_readiness_record,
    transition_deployment_instance,
    validate_bundle_readiness_record,
    validate_candidate_bundle,
    validate_deployment_instance,
    validate_promotion_packet,
    validate_session_readiness_packet,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"deployment packet fixture failed to load: {exc}") from exc


def build_candidate(payload: dict[str, object]) -> CandidateBundle:
    return CandidateBundle.from_dict(payload)


def build_readiness(payload: dict[str, object]) -> BundleReadinessRecord:
    return BundleReadinessRecord.from_dict(payload)


def build_deployment(payload: dict[str, object]) -> DeploymentInstance:
    return DeploymentInstance.from_dict(payload)


def build_promotion(payload: dict[str, object]) -> PromotionPacket:
    return PromotionPacket.from_dict(payload)


def build_session(payload: dict[str, object]) -> SessionReadinessPacket:
    return SessionReadinessPacket.from_dict(payload)


class DeploymentPacketContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_all_packet_types(self) -> None:
        fixtures = load_cases()
        candidate = build_candidate(fixtures["candidate_cases"][0]["payload"])
        readiness = build_readiness(fixtures["readiness_cases"][0]["payload"])
        deployment = build_deployment(fixtures["deployment_cases"][0]["payload"])
        promotion = build_promotion(fixtures["promotion_cases"][0]["payload"])
        session = build_session(fixtures["session_cases"][0]["payload"])

        self.assertEqual(candidate, CandidateBundle.from_json(candidate.to_json()))
        self.assertEqual(readiness, BundleReadinessRecord.from_json(readiness.to_json()))
        self.assertEqual(deployment, DeploymentInstance.from_json(deployment.to_json()))
        self.assertEqual(promotion, PromotionPacket.from_json(promotion.to_json()))
        self.assertEqual(session, SessionReadinessPacket.from_json(session.to_json()))

    def test_from_json_rejects_invalid_candidate_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate_bundle: invalid JSON payload"):
            CandidateBundle.from_json("{not valid json")

    def test_candidate_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["candidate_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_candidate_bundle(
                    payload["case_id"],
                    build_candidate(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_readiness_fixture_and_transition_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["readiness_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_bundle_readiness_record(
                    payload["case_id"],
                    build_readiness(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

        for payload in fixtures["readiness_transition_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = transition_bundle_readiness_record(
                    payload["case_id"],
                    build_readiness(payload["payload"]),
                    ReadinessState(payload["to_state"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_deployment_fixture_and_transition_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["deployment_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_deployment_instance(
                    payload["case_id"],
                    build_deployment(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

        for payload in fixtures["deployment_transition_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = transition_deployment_instance(
                    payload["case_id"],
                    build_deployment(payload["payload"]),
                    DeploymentState(payload["to_state"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_promotion_and_session_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for payload in fixtures["promotion_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_promotion_packet(
                    payload["case_id"],
                    build_promotion(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

        for payload in fixtures["session_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_session_readiness_packet(
                    payload["case_id"],
                    build_session(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_candidate_report_is_structured_and_mentions_immutability(self) -> None:
        report = validate_candidate_bundle(
            "candidate-shape",
            build_candidate(load_cases()["candidate_cases"][0]["payload"]),
        )
        payload = report.to_dict()
        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "packet_kind",
                "packet_id",
                "status",
                "reason_code",
                "context",
                "missing_fields",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("immutable", report.explanation.lower())

    def test_session_packet_report_is_structured_and_green_when_valid(self) -> None:
        report = validate_session_readiness_packet(
            "session-shape",
            build_session(load_cases()["session_cases"][0]["payload"]),
        )
        payload = report.to_dict()
        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertEqual(SessionReadinessStatus.GREEN.value, report.context["session_status"])
        self.assertTrue(
            {
                "case_id",
                "packet_kind",
                "packet_id",
                "status",
                "reason_code",
                "context",
                "missing_fields",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("one deployment instance", report.explanation.lower())


if __name__ == "__main__":
    unittest.main()
