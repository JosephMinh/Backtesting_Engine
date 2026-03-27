"""Contract tests for candidate, readiness, deployment, promotion, and session packets."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.deployment_packets import (
    VALIDATION_ERRORS,
    BundleReadinessRecord,
    CandidateBundle,
    CandidateBundleFreezeRegistration,
    CandidateBundleReplayContext,
    DeploymentInstance,
    DeploymentState,
    PacketStatus,
    PromotionPacket,
    PromotionPreflightRequest,
    ReadinessState,
    SessionReadinessPacket,
    SessionReadinessStatus,
    SessionTradeabilityRequest,
    build_candidate_bundle_freeze_registration,
    transition_bundle_readiness_record,
    transition_deployment_instance,
    validate_bundle_readiness_record,
    validate_candidate_bundle,
    validate_candidate_bundle_freeze_registration,
    validate_candidate_bundle_load,
    validate_candidate_bundle_replay_readiness,
    validate_deployment_instance,
    validate_promotion_preflight,
    validate_promotion_packet,
    validate_session_readiness_packet,
    validate_session_tradeability,
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


def build_preflight_request(payload: dict[str, object]) -> PromotionPreflightRequest:
    return PromotionPreflightRequest.from_dict(payload)


def build_session(payload: dict[str, object]) -> SessionReadinessPacket:
    return SessionReadinessPacket.from_dict(payload)


def build_session_tradeability_request(
    packet: SessionReadinessPacket, overrides: dict[str, object] | None = None
) -> SessionTradeabilityRequest:
    payload: dict[str, object] = {
        "tradeability_gate_id": "session_tradeability_gate_default",
        "session_packet": packet.to_dict(),
        "active_deployment_instance_id": packet.deployment_instance_id,
        "active_promotion_packet_id": packet.source_promotion_packet_id,
        "current_session_id": packet.session_id,
        "evaluated_at_utc": packet.valid_from_utc,
        "stale_check_ids": [],
        "failed_check_ids": [],
        "correlation_id": "corr-session-tradeability-default",
        "operator_reason_bundle": ["session tradeability gate evaluated"],
        "signed_gate_hash": "session_tradeability_sha256_default",
    }
    payload = deep_merge(payload, overrides or {})
    return SessionTradeabilityRequest.from_dict(payload)


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def candidate_payload_by_case(case_id: str) -> dict[str, object]:
    fixtures = load_cases()
    candidate_case = next(
        case for case in fixtures["candidate_cases"] if case["case_id"] == case_id
    )
    return dict(candidate_case["payload"])


def promotion_payload_by_case(case_id: str) -> dict[str, object]:
    fixtures = load_cases()
    promotion_case = next(
        case for case in fixtures["promotion_cases"] if case["case_id"] == case_id
    )
    return dict(promotion_case["payload"])


def build_freeze_registration(
    candidate: CandidateBundle, overrides: dict[str, object] | None = None
) -> CandidateBundleFreezeRegistration:
    registration = build_candidate_bundle_freeze_registration(
        candidate,
        registration_log_id="candidate_bundle_freeze_log_default",
        registration_artifact_id="signed_manifest_candidate_bundle_default",
        correlation_id="corr-candidate-freeze-default",
        operator_reason_bundle=("candidate bundle freeze recorded",),
    )
    payload = deep_merge(registration.to_dict(), overrides or {})
    return CandidateBundleFreezeRegistration.from_dict(payload)


def build_replay_context(
    registration: CandidateBundleFreezeRegistration,
    overrides: dict[str, object] | None = None,
) -> CandidateBundleReplayContext:
    payload: dict[str, object] = {
        "replay_context_id": "candidate_bundle_replay_context_default",
        "registration_log_id": registration.registration_log_id,
        "replay_fixture_id": "replay_fixture_candidate_bundle_default",
        "signed_manifest_id": registration.registration_artifact_id,
        "available_artifact_ids": [
            "replay_fixture_candidate_bundle_default",
            registration.registration_artifact_id,
        ],
        "available_feature_contract_hashes": list(registration.feature_contract_hashes),
        "available_signature_ids": list(registration.signature_ids),
        "dependency_manifest_hashes": [registration.dependency_dag_hash],
        "correlation_id": registration.correlation_id,
        "operator_reason_bundle": ["candidate bundle replay context retained"],
    }
    payload = deep_merge(payload, overrides or {})
    return CandidateBundleReplayContext.from_dict(payload)


def build_promotion_preflight_request(
    packet: PromotionPacket, overrides: dict[str, object] | None = None
) -> PromotionPreflightRequest:
    payload: dict[str, object] = {
        "preflight_report_id": "promotion_preflight_report_default",
        "promotion_packet": packet.to_dict(),
        "resolved_artifact_ids": [
            packet.candidate_bundle_id,
            packet.bundle_readiness_record_id,
            packet.replay_certification_id,
            packet.portability_certification_id,
            packet.execution_symbol_tradability_study_id,
            packet.fee_schedule_snapshot_id,
            packet.margin_snapshot_id,
            packet.market_data_entitlement_check_id,
            *packet.active_waiver_ids,
            *packet.incident_reference_ids,
        ],
        "integrity_verified_artifact_ids": [
            packet.candidate_bundle_id,
            packet.bundle_readiness_record_id,
            packet.replay_certification_id,
            packet.portability_certification_id,
            packet.execution_symbol_tradability_study_id,
            packet.fee_schedule_snapshot_id,
            packet.margin_snapshot_id,
            packet.market_data_entitlement_check_id,
            *packet.active_waiver_ids,
            *packet.incident_reference_ids,
        ],
        "verified_compatibility_domain_ids": [
            "data_protocol",
            "strategy_protocol",
            "ops_protocol",
            "policy_bundle_hash",
            "compatibility_matrix_version",
        ],
        "stale_evidence_ids": [],
        "superseded_artifact_ids": [],
        "broker_capability_check_id": "broker_capability_preflight_default",
        "backup_freshness_check_id": "backup_freshness_preflight_default",
        "restore_drill_check_id": "restore_drill_preflight_default",
        "clock_health_check_id": "clock_health_preflight_default",
        "secret_health_check_id": "ops_health_preflight_default",
        "failed_check_ids": [],
        "correlation_id": "corr-promotion-preflight-default",
        "operator_reason_bundle": ["promotion preflight completed"],
        "signed_preflight_hash": "promotion_preflight_sha256_default",
    }
    if packet.native_validation_id:
        payload["resolved_artifact_ids"].append(packet.native_validation_id)
        payload["integrity_verified_artifact_ids"].append(packet.native_validation_id)
    if packet.paper_pass_evidence_id:
        payload["resolved_artifact_ids"].append(packet.paper_pass_evidence_id)
        payload["integrity_verified_artifact_ids"].append(packet.paper_pass_evidence_id)
    if packet.shadow_pass_evidence_id:
        payload["resolved_artifact_ids"].append(packet.shadow_pass_evidence_id)
        payload["integrity_verified_artifact_ids"].append(packet.shadow_pass_evidence_id)
    payload = deep_merge(payload, overrides or {})
    return PromotionPreflightRequest.from_dict(payload)


class DeploymentPacketContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_all_packet_types(self) -> None:
        fixtures = load_cases()
        candidate = build_candidate(fixtures["candidate_cases"][0]["payload"])
        readiness = build_readiness(fixtures["readiness_cases"][0]["payload"])
        deployment = build_deployment(fixtures["deployment_cases"][0]["payload"])
        promotion = build_promotion(fixtures["promotion_cases"][0]["payload"])
        preflight = build_promotion_preflight_request(promotion)
        session = build_session(fixtures["session_cases"][0]["payload"])
        tradeability = build_session_tradeability_request(session)

        self.assertEqual(candidate, CandidateBundle.from_json(candidate.to_json()))
        self.assertEqual(readiness, BundleReadinessRecord.from_json(readiness.to_json()))
        self.assertEqual(deployment, DeploymentInstance.from_json(deployment.to_json()))
        self.assertEqual(promotion, PromotionPacket.from_json(promotion.to_json()))
        self.assertEqual(
            preflight,
            PromotionPreflightRequest.from_json(preflight.to_json()),
        )
        self.assertEqual(session, SessionReadinessPacket.from_json(session.to_json()))
        self.assertEqual(
            tradeability,
            SessionTradeabilityRequest.from_json(tradeability.to_json()),
        )

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

    def test_candidate_freeze_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for case in fixtures["candidate_freeze_cases"]:
            with self.subTest(case_id=case["case_id"]):
                candidate = build_candidate(candidate_payload_by_case(case["candidate_case_id"]))
                registration = build_freeze_registration(
                    candidate,
                    case.get("registration_overrides"),
                )
                report = validate_candidate_bundle_freeze_registration(
                    case["case_id"],
                    candidate,
                    registration,
                )
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

    def test_candidate_load_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for case in fixtures["candidate_load_cases"]:
            with self.subTest(case_id=case["case_id"]):
                baseline_candidate = build_candidate(
                    candidate_payload_by_case(case["candidate_case_id"])
                )
                registration = build_freeze_registration(
                    baseline_candidate,
                    case.get("registration_overrides"),
                )
                candidate = build_candidate(
                    deep_merge(
                        candidate_payload_by_case(case["candidate_case_id"]),
                        case.get("bundle_overrides", {}),
                    )
                )
                report = validate_candidate_bundle_load(
                    case["case_id"],
                    candidate,
                    registration,
                )
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

    def test_candidate_replay_fixture_cases_emit_expected_reports(self) -> None:
        fixtures = load_cases()
        for case in fixtures["candidate_replay_cases"]:
            with self.subTest(case_id=case["case_id"]):
                candidate = build_candidate(candidate_payload_by_case(case["candidate_case_id"]))
                registration = build_freeze_registration(
                    candidate,
                    case.get("registration_overrides"),
                )
                replay_context = build_replay_context(
                    registration,
                    case.get("replay_context_overrides"),
                )
                report = validate_candidate_bundle_replay_readiness(
                    case["case_id"],
                    candidate,
                    registration,
                    replay_context,
                )
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

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
                if "expected_machine_id" in payload:
                    self.assertEqual(payload["expected_machine_id"], report.machine_id)
                if "expected_allowed_next_states" in payload:
                    self.assertEqual(
                        tuple(payload["expected_allowed_next_states"]),
                        report.allowed_next_states,
                    )

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
                if "expected_machine_id" in payload:
                    self.assertEqual(payload["expected_machine_id"], report.machine_id)
                if "expected_allowed_next_states" in payload:
                    self.assertEqual(
                        tuple(payload["expected_allowed_next_states"]),
                        report.allowed_next_states,
                    )

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

        for case in fixtures["promotion_preflight_cases"]:
            with self.subTest(case_id=case["case_id"]):
                packet = build_promotion(
                    deep_merge(
                        promotion_payload_by_case(case["promotion_case_id"]),
                        case.get("promotion_overrides", {}),
                    )
                )
                request = build_promotion_preflight_request(
                    packet,
                    case.get("preflight_overrides"),
                )
                report = validate_promotion_preflight(case["case_id"], request)
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

        for payload in fixtures["session_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_session_readiness_packet(
                    payload["case_id"],
                    build_session(payload["payload"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

        for case in fixtures["session_tradeability_cases"]:
            with self.subTest(case_id=case["case_id"]):
                session = build_session(
                    deep_merge(
                        next(
                            payload["payload"]
                            for payload in fixtures["session_cases"]
                            if payload["case_id"] == case["session_case_id"]
                        ),
                        case.get("session_overrides", {}),
                    )
                )
                request = build_session_tradeability_request(
                    session,
                    case.get("request_overrides"),
                )
                report = validate_session_tradeability(case["case_id"], request)
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

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

    def test_candidate_registration_and_replay_context_round_trip(self) -> None:
        candidate = build_candidate(load_cases()["candidate_cases"][0]["payload"])
        registration = build_freeze_registration(candidate)
        replay_context = build_replay_context(registration)

        self.assertEqual(
            registration,
            CandidateBundleFreezeRegistration.from_json(registration.to_json()),
        )
        self.assertEqual(
            replay_context,
            CandidateBundleReplayContext.from_json(replay_context.to_json()),
        )

    def test_candidate_replay_report_mentions_closed_dependencies(self) -> None:
        case = next(
            case
            for case in load_cases()["candidate_replay_cases"]
            if case["case_id"] == "allow_candidate_bundle_replay_ready"
        )
        candidate = build_candidate(candidate_payload_by_case(case["candidate_case_id"]))
        registration = build_freeze_registration(
            candidate,
            case.get("registration_overrides"),
        )
        replay_context = build_replay_context(
            registration,
            case.get("replay_context_overrides"),
        )

        report = validate_candidate_bundle_replay_readiness(
            case["case_id"],
            candidate,
            registration,
            replay_context,
        )

        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertIn("closed dependencies", report.explanation.lower())
        self.assertEqual("candidate_bundle_replay", report.packet_kind)

    def test_transition_report_includes_machine_id_and_allowed_next_states(self) -> None:
        case = next(
            case
            for case in load_cases()["deployment_transition_cases"]
            if case["case_id"] == "allow_live_canary_to_live_active"
        )
        report = transition_deployment_instance(
            case["case_id"],
            build_deployment(case["payload"]),
            DeploymentState(case["to_state"]),
        )
        payload = report.to_dict()

        self.assertEqual("deployment_instance_lifecycle", report.machine_id)
        self.assertEqual(("LIVE_ACTIVE", "WITHDRAWN", "CLOSED"), report.allowed_next_states)
        self.assertTrue(
            {"machine_id", "allowed_next_states", "allowed", "from_state", "to_state"}.issubset(
                payload.keys()
            )
        )

    def test_promotion_preflight_report_mentions_signed_preflight(self) -> None:
        case = next(
            case
            for case in load_cases()["promotion_preflight_cases"]
            if case["case_id"] == "allow_live_promotion_preflight"
        )
        packet = build_promotion(
            deep_merge(
                promotion_payload_by_case(case["promotion_case_id"]),
                case.get("promotion_overrides", {}),
            )
        )
        request = build_promotion_preflight_request(
            packet,
            case.get("preflight_overrides"),
        )

        report = validate_promotion_preflight(case["case_id"], request)

        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertIn("signed activation preflight", report.explanation.lower())
        self.assertEqual("promotion_preflight", report.packet_kind)

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

    def test_session_tradeability_report_mentions_new_entries_gate(self) -> None:
        case = next(
            case
            for case in load_cases()["session_tradeability_cases"]
            if case["case_id"] == "allow_green_session_tradeability"
        )
        session = build_session(
            deep_merge(
                next(
                    payload["payload"]
                    for payload in load_cases()["session_cases"]
                    if payload["case_id"] == case["session_case_id"]
                ),
                case.get("session_overrides", {}),
            )
        )
        request = build_session_tradeability_request(
            session,
            case.get("request_overrides"),
        )

        report = validate_session_tradeability(case["case_id"], request)

        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertEqual("session_tradeability", report.packet_kind)
        self.assertIn("new entries", report.explanation.lower())


if __name__ == "__main__":
    unittest.main()
