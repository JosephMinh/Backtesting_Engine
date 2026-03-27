from __future__ import annotations

import io
import json
import runpy
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from shared.policy.bar_parity import (
    BarParityCertificationRequest,
    evaluate_databento_ibkr_bar_parity,
)
from shared.policy.deployment_packets import (
    CandidateBundle,
    CandidateBundleFreezeRegistration,
    CandidateBundleReplayContext,
    PromotionPacket,
    PromotionPreflightRequest,
    SessionReadinessPacket,
    SessionTradeabilityRequest,
    build_candidate_bundle_freeze_registration,
    validate_promotion_preflight,
    validate_session_tradeability,
)
from shared.policy.failure_explain_surfaces import (
    VALIDATION_ERRORS,
    FailureExplainOutcome,
    FailureExplainRemediationClass,
    FailureExplainReport,
    FailureExplainRequest,
    evaluate_failure_explain_surface,
)
from shared.policy.replay_certification import (
    ReplayCertificationRequest,
    evaluate_replay_certification,
)
from shared.policy.runtime_recovery import RecoveryFenceRequest, validate_recovery_fence

EXPLAIN_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "failure_explain_surfaces_cases.json"
)
DEPLOYMENT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
)
REPLAY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "replay_certification_cases.json"
)
PARITY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "bar_parity_cases.json"
)
RUNTIME_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "runtime_recovery_cases.json"
)
SMOKE_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "failure_explain_surfaces_smoke.py"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):  # pragma: no cover - defensive
        raise AssertionError(f"{label} must decode to an object")
    return decoded


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def find_case(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    return next(case for case in cases if case["case_id"] == case_id)


def deployment_fixture() -> dict[str, Any]:
    return load_json(DEPLOYMENT_FIXTURE_PATH)


def replay_fixture() -> dict[str, Any]:
    return load_json(REPLAY_FIXTURE_PATH)


def parity_fixture() -> dict[str, Any]:
    return load_json(PARITY_FIXTURE_PATH)


def runtime_fixture() -> dict[str, Any]:
    return load_json(RUNTIME_FIXTURE_PATH)


def explain_fixture() -> dict[str, Any]:
    return load_json(EXPLAIN_FIXTURE_PATH)


def candidate_payload_by_case(case_id: str) -> dict[str, Any]:
    fixtures = deployment_fixture()
    candidate_case = find_case(fixtures["candidate_cases"], case_id)
    return dict(candidate_case["payload"])


def build_candidate(payload: dict[str, Any]) -> CandidateBundle:
    return CandidateBundle.from_dict(payload)


def build_freeze_registration(
    candidate: CandidateBundle,
    overrides: dict[str, Any] | None = None,
) -> CandidateBundleFreezeRegistration:
    registration = build_candidate_bundle_freeze_registration(
        candidate,
        registration_log_id="candidate_bundle_freeze_log_default",
        registration_artifact_id="signed_manifest_candidate_bundle_default",
        correlation_id="corr-replay-certification-default",
        operator_reason_bundle=("candidate bundle freeze recorded",),
    )
    payload = deep_merge(registration.to_dict(), overrides or {})
    return CandidateBundleFreezeRegistration.from_dict(payload)


def build_replay_context(
    registration: CandidateBundleFreezeRegistration,
    overrides: dict[str, Any] | None = None,
) -> CandidateBundleReplayContext:
    payload: dict[str, Any] = {
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


def build_replay_request(case: dict[str, Any]) -> ReplayCertificationRequest:
    candidate = build_candidate(candidate_payload_by_case(str(case["candidate_case_id"])))
    registration = build_freeze_registration(
        candidate,
        dict(case.get("registration_overrides", {})),
    )
    replay_context = build_replay_context(
        registration,
        dict(case.get("replay_context_overrides", {})),
    )
    payload = {
        "case_id": case["case_id"],
        "certification_id": case["certification_id"],
        "bundle": candidate.to_dict(),
        "registration": registration.to_dict(),
        "replay_context": replay_context.to_dict(),
        "decision_trace_id": case["decision_trace_id"],
        "expected_signal_trace": case["expected_signal_trace"],
        "actual_signal_trace": case["actual_signal_trace"],
        "expected_order_intent_trace": case["expected_order_intent_trace"],
        "actual_order_intent_trace": case["actual_order_intent_trace"],
        "expected_risk_action_trace": case["expected_risk_action_trace"],
        "actual_risk_action_trace": case["actual_risk_action_trace"],
        "expected_contract_state_trace": case["expected_contract_state_trace"],
        "actual_contract_state_trace": case["actual_contract_state_trace"],
        "expected_freshness_watermark_trace": case[
            "expected_freshness_watermark_trace"
        ],
        "actual_freshness_watermark_trace": case["actual_freshness_watermark_trace"],
        "certification_mode": case.get("certification_mode", "full"),
        "dependency_change_scope": case.get("dependency_change_scope", "none"),
        "prior_certification_id": case.get("prior_certification_id"),
    }
    return ReplayCertificationRequest.from_dict(payload)


def build_parity_dimension(payload: dict[str, Any]):
    from shared.policy.bar_parity import (  # local import to keep the global import list small
        check_anchor_timing,
        check_bar_availability_timing,
        check_event_window_labeling,
        check_ohlcv_construction,
        check_session_boundaries,
    )

    kind = payload["kind"]
    if kind == "session_boundaries":
        return check_session_boundaries(
            boundary_alignment_ratio=float(payload["boundary_alignment_ratio"]),
            min_boundary_alignment_ratio=float(payload["min_boundary_alignment_ratio"]),
            boundary_mismatch_count=int(payload["boundary_mismatch_count"]),
            max_boundary_mismatch_count=int(payload["max_boundary_mismatch_count"]),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "ohlcv_construction":
        return check_ohlcv_construction(
            ohlc_diff_ticks=int(payload["ohlc_diff_ticks"]),
            max_allowed_ohlc_diff_ticks=int(payload["max_allowed_ohlc_diff_ticks"]),
            volume_diff_ratio=float(payload["volume_diff_ratio"]),
            max_allowed_volume_diff_ratio=float(
                payload["max_allowed_volume_diff_ratio"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "anchor_timing":
        return check_anchor_timing(
            max_anchor_drift_seconds=float(payload["max_anchor_drift_seconds"]),
            max_allowed_anchor_drift_seconds=float(
                payload["max_allowed_anchor_drift_seconds"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "event_window_labeling":
        return check_event_window_labeling(
            mislabeled_window_count=int(payload["mislabeled_window_count"]),
            max_allowed_mislabeled_window_count=int(
                payload["max_allowed_mislabeled_window_count"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "bar_availability_timing":
        return check_bar_availability_timing(
            max_availability_lag_seconds=float(payload["max_availability_lag_seconds"]),
            max_allowed_availability_lag_seconds=float(
                payload["max_allowed_availability_lag_seconds"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    raise AssertionError(f"unexpected bar parity dimension kind: {kind}")


def build_parity_request(payload: dict[str, Any]) -> BarParityCertificationRequest:
    return BarParityCertificationRequest(
        case_id=str(payload["case_id"]),
        data_profile_release_id=str(payload["data_profile_release_id"]),
        approved_bar_construction_semantics_id=str(
            payload["approved_bar_construction_semantics_id"]
        ),
        research_feed=str(payload["research_feed"]),
        live_feed=str(payload["live_feed"]),
        certified_at_utc=str(payload["certified_at_utc"]),
        freshness_expires_at_utc=str(payload["freshness_expires_at_utc"]),
        evaluation_time_utc=str(payload["evaluation_time_utc"]),
        parity_expectations=tuple(str(item) for item in payload["parity_expectations"]),
        mismatch_histogram_artifact_ids=tuple(
            str(item) for item in payload["mismatch_histogram_artifact_ids"]
        ),
        sampled_drilldown_artifact_ids=tuple(
            str(item) for item in payload["sampled_drilldown_artifact_ids"]
        ),
        dimensions=tuple(
            build_parity_dimension(dimension_payload)
            for dimension_payload in payload["dimensions"]
        ),
    )


def build_promotion_preflight_request(
    packet: PromotionPacket, overrides: dict[str, Any] | None = None
) -> PromotionPreflightRequest:
    payload: dict[str, Any] = {
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
        "secret_health_check_id": "ops_control_preflight_default",
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


def build_session_tradeability_request(
    packet: SessionReadinessPacket, overrides: dict[str, Any] | None = None
) -> SessionTradeabilityRequest:
    payload: dict[str, Any] = {
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


def build_source_report(source_fixture: dict[str, Any]):
    module = source_fixture["module"]
    case_id = source_fixture["case_id"]
    if module == "deployment_packets":
        fixtures = deployment_fixture()
        if source_fixture["group"] == "promotion_preflight_cases":
            case = find_case(fixtures["promotion_preflight_cases"], case_id)
            promotion_case = find_case(fixtures["promotion_cases"], case["promotion_case_id"])
            packet = PromotionPacket.from_dict(dict(promotion_case["payload"]))
            request = build_promotion_preflight_request(
                packet,
                dict(case.get("preflight_overrides", {})),
            )
            return validate_promotion_preflight(case["case_id"], request)
        case = find_case(fixtures["session_tradeability_cases"], case_id)
        session_case = find_case(fixtures["session_cases"], case["session_case_id"])
        session_payload = deep_merge(
            dict(session_case["payload"]),
            dict(case.get("session_overrides", {})),
        )
        packet = SessionReadinessPacket.from_dict(session_payload)
        request = build_session_tradeability_request(
            packet,
            dict(case.get("request_overrides", {})),
        )
        return validate_session_tradeability(case["case_id"], request)
    if module == "bar_parity":
        case = find_case(parity_fixture()["bar_parity_cases"], case_id)
        return evaluate_databento_ibkr_bar_parity(build_parity_request(case))
    if module == "replay_certification":
        case = find_case(replay_fixture()["cases"], case_id)
        return evaluate_replay_certification(build_replay_request(case))
    case = find_case(runtime_fixture()["recovery_fence_cases"], case_id)
    return validate_recovery_fence(
        case["case_id"],
        RecoveryFenceRequest.from_dict(dict(case["payload"])),
    )


def build_failure_request(case_id: str) -> FailureExplainRequest:
    fixture = explain_fixture()
    case = find_case(fixture["cases"], case_id)
    defaults = fixture["shared_request_defaults"]
    source_report = build_source_report(dict(case["source_fixture"]))
    payload: dict[str, Any] = {
        "case_id": case["case_id"],
        "explain_surface_id": f"failure_explain_{case['case_id']}",
        "source_kind": case["source_kind"],
        "runbook_references": list(case["runbook_references"]),
        "retained_log_ids": list(case.get("retained_log_ids", ())),
        "correlation_ids": list(case.get("correlation_ids", ())),
        "operator_notes": list(defaults["operator_notes"]),
    }
    source_kind = case["source_kind"]
    if source_kind in {"policy_failure", "readiness_rejection"}:
        payload["packet_report"] = source_report.to_dict()
    elif source_kind == "parity_drift":
        payload["parity_report"] = source_report.to_dict()
    elif source_kind == "replay_divergence":
        payload["replay_report"] = source_report.to_dict()
    else:
        payload["recovery_report"] = source_report.to_dict()
    return FailureExplainRequest.from_dict(payload)


class FailureExplainSurfaceContractTests(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_nested_source_report(self) -> None:
        request = build_failure_request(
            explain_fixture()["cases"][0]["case_id"]
        )
        self.assertEqual(request, FailureExplainRequest.from_json(request.to_json()))

    def test_report_round_trip_preserves_payload(self) -> None:
        request = build_failure_request("replay_divergence_explain")
        report = evaluate_failure_explain_surface(request)
        self.assertEqual(report, FailureExplainReport.from_json(report.to_json()))

    def test_fixture_cases_emit_expected_outcomes(self) -> None:
        for case in explain_fixture()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_failure_explain_surface(
                    build_failure_request(case["case_id"])
                )
                expected = case["expected"]
                self.assertEqual(expected["outcome"], report.outcome.value)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    expected["remediation_classification"],
                    report.remediation_classification.value,
                )
                self.assertGreaterEqual(
                    len(report.expected_vs_actual_diffs),
                    int(expected["expected_diff_min_count"]),
                )
                self.assertTrue(report.walkthrough_steps)
                self.assertTrue(report.stage_cards)
                self.assertTrue(report.next_actions)

    def test_replay_explain_report_preserves_trace_and_artifact_navigation(self) -> None:
        report = evaluate_failure_explain_surface(
            build_failure_request("replay_divergence_explain")
        )
        payload = report.to_dict()
        self.assertEqual(FailureExplainOutcome.BLOCKED.value, payload["outcome"])
        self.assertIn("artifact_manifest", payload["evidence_navigation"])
        self.assertIn("first_divergence", payload["evidence_navigation"])
        self.assertTrue(payload["expected_actual_diff_ids"])
        self.assertTrue(payload["retained_log_ids"])
        self.assertTrue(payload["correlation_ids"])

    def test_parity_explain_requires_explicit_correlation_id(self) -> None:
        request = build_failure_request("parity_drift_explain")
        payload = request.to_dict()
        payload["correlation_ids"] = []
        invalid_report = evaluate_failure_explain_surface(
            FailureExplainRequest.from_dict(payload)
        )
        self.assertEqual(FailureExplainOutcome.INVALID, invalid_report.outcome)
        self.assertEqual(
            "FAILURE_EXPLAIN_CORRELATION_ID_REQUIRED",
            invalid_report.reason_code,
        )
        self.assertEqual(
            FailureExplainRemediationClass.REPAIR_EXPLAIN_REQUEST,
            invalid_report.remediation_classification,
        )

    def test_report_is_operator_and_developer_readable(self) -> None:
        report = evaluate_failure_explain_surface(
            build_failure_request("readiness_tradeability_blocked_status_explain")
        )
        payload = report.to_dict()
        self.assertTrue(
            {
                "schema_version",
                "case_id",
                "explain_surface_id",
                "source_kind",
                "outcome",
                "reason_code",
                "blocking_reason_code",
                "stage_cards",
                "walkthrough_steps",
                "evidence_navigation",
                "expected_vs_actual_diffs",
                "correlation_ids",
                "expected_actual_diff_ids",
                "retained_artifact_ids",
                "retained_log_ids",
                "operator_reason_bundle",
                "operator_summary",
                "developer_summary",
                "remediation_classification",
                "remediation",
                "next_actions",
                "generated_at_utc",
            }.issubset(payload.keys())
        )
        self.assertIn("green", payload["developer_summary"].lower())
        self.assertIn("block", payload["operator_summary"].lower())

    def test_smoke_script_emits_selected_case_and_writes_output(self) -> None:
        with TemporaryDirectory() as tmpdir:
            buffer = io.StringIO()
            argv = [
                str(SMOKE_SCRIPT_PATH),
                "--case-id",
                "recovery_fence_missing_fresh_packet_explain",
                "--output-dir",
                tmpdir,
            ]
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(buffer):
                    with self.assertRaises(SystemExit) as exit_context:
                        runpy.run_path(str(SMOKE_SCRIPT_PATH), run_name="__main__")
            self.assertEqual(0, exit_context.exception.code)
            payload = decode_json_object(buffer.getvalue(), label="smoke output")
            reports = payload["reports"]
            self.assertEqual(1, len(reports))
            self.assertEqual(
                "RECOVERY_FENCE_SESSION_PACKET_REQUIRED_AFTER_RESET",
                reports[0]["reason_code"],
            )
            output_path = (
                Path(tmpdir)
                / "recovery_fence_missing_fresh_packet_explain.failure-explain.json"
            )
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
