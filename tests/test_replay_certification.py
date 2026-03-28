"""Contract tests for deterministic replay certification."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - test harness intentionally executes a trusted repo-local script
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.deployment_packets import (
    CandidateBundle,
    CandidateBundleFreezeRegistration,
    CandidateBundleReplayContext,
    build_candidate_bundle_freeze_registration,
)
from shared.policy.replay_certification import (
    VALIDATION_ERRORS,
    ReplayCertificationRequest,
    ReplayCertificationReport,
    evaluate_replay_certification,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "replay_certification_cases.json"
)
DEPLOYMENT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "replay_certification_smoke.py"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"replay certification fixture failed to load: {exc}") from exc


def load_deployment_fixture() -> dict[str, object]:
    try:
        with DEPLOYMENT_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"deployment packet fixture failed to load: {exc}") from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def candidate_payload_by_case(case_id: str) -> dict[str, object]:
    fixtures = load_deployment_fixture()
    candidate_case = next(
        case for case in fixtures["candidate_cases"] if case["case_id"] == case_id
    )
    return dict(candidate_case["payload"])


def build_candidate(payload: dict[str, object]) -> CandidateBundle:
    return CandidateBundle.from_dict(payload)


def build_freeze_registration(
    candidate: CandidateBundle,
    overrides: dict[str, object] | None = None,
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


def build_request(case: dict[str, object]) -> ReplayCertificationRequest:
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


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} must decode to a JSON object")
    return decoded


class ReplayCertificationContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_nested_trace_data(self) -> None:
        case = load_cases()["cases"][0]
        request = build_request(case)
        reparsed = ReplayCertificationRequest.from_json(request.to_json())

        self.assertEqual(request.certification_id, reparsed.certification_id)
        self.assertEqual(request.bundle.bundle_id, reparsed.bundle.bundle_id)
        self.assertEqual(
            [item.to_dict() for item in request.expected_signal_trace],
            [item.to_dict() for item in reparsed.expected_signal_trace],
        )
        self.assertEqual(
            [item.to_dict() for item in request.actual_order_intent_trace],
            [item.to_dict() for item in reparsed.actual_order_intent_trace],
        )

    def test_request_rejects_string_boolean_for_certification_mode_inputs(self) -> None:
        case = load_cases()["cases"][0]
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
            "expected_signal_trace": [{"signal_name": "alpha", "signal_value": 1.0, "timestamp_utc": "2026-03-27T00:00:00+00:00", "decision_sequence_number": 1}],
            "actual_signal_trace": [],
            "expected_order_intent_trace": [],
            "actual_order_intent_trace": [],
            "expected_risk_action_trace": [],
            "actual_risk_action_trace": [],
            "expected_contract_state_trace": [],
            "actual_contract_state_trace": [],
            "expected_freshness_watermark_trace": [],
            "actual_freshness_watermark_trace": [],
            "certification_mode": True,
            "dependency_change_scope": "none",
            "prior_certification_id": None,
        }

        with self.assertRaisesRegex(ValueError, "replay request.certification_mode"):
            ReplayCertificationRequest.from_dict(payload)

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_replay_certification(build_request(case))

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected_paper_entry_permitted"],
                    report.paper_entry_permitted,
                )
                self.assertEqual(
                    case["expected_diff_count"],
                    len(report.expected_vs_actual_diffs),
                )
                if "expected_first_divergence_stream" in case:
                    self.assertIsNotNone(report.first_divergence)
                    first_divergence = report.first_divergence
                    if first_divergence is None:  # pragma: no cover - defensive
                        self.fail("expected a first divergence entry")
                    self.assertEqual(
                        case["expected_first_divergence_stream"],
                        first_divergence["stream_name"],
                    )
                    self.assertEqual(
                        case["expected_first_divergence_field"],
                        first_divergence["field_name"],
                    )
                if "expected_replay_readiness_reason_code" in case:
                    self.assertEqual(
                        case["expected_replay_readiness_reason_code"],
                        report.replay_readiness_reason_code,
                    )

    def test_report_includes_required_artifacts_logs_and_reason_bundle(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "reject_signal_trace_divergence"
        )
        report = evaluate_replay_certification(build_request(case)).to_dict()

        self.assertTrue(report["stepwise_trace"])
        first_trace = report["stepwise_trace"][0]
        self.assertTrue(
            {
                "stream_name",
                "index",
                "matched",
                "expected_reference",
                "actual_reference",
                "expected_sequence_number",
                "actual_sequence_number",
                "divergence_fields",
                "diagnostic",
            }.issubset(first_trace.keys())
        )

        manifest = report["artifact_manifest"]
        self.assertTrue(
            {
                "manifest_id",
                "generated_at_utc",
                "retention_class",
                "contains_secrets",
                "redaction_policy",
                "artifacts",
            }.issubset(manifest.keys())
        )
        self.assertGreaterEqual(len(manifest["artifacts"]), 5)
        for artifact in manifest["artifacts"]:
            self.assertTrue(
                {
                    "artifact_id",
                    "artifact_role",
                    "relative_path",
                    "sha256",
                    "content_type",
                }.issubset(artifact.keys())
            )

        self.assertGreaterEqual(len(report["structured_logs"]), 3)
        for record in report["structured_logs"]:
            self.assertTrue(
                {
                    "schema_version",
                    "event_type",
                    "plane",
                    "event_id",
                    "recorded_at_utc",
                    "correlation_id",
                    "decision_trace_id",
                    "reason_code",
                    "reason_summary",
                    "referenced_ids",
                    "redacted_fields",
                    "omitted_fields",
                    "artifact_manifest",
                }.issubset(record.keys())
            )

    def test_report_round_trip_validates_boundary(self) -> None:
        case = load_cases()["cases"][0]
        report = evaluate_replay_certification(build_request(case))

        reparsed = ReplayCertificationReport.from_json(report.to_json())

        self.assertEqual(report.reason_code, reparsed.reason_code)
        self.assertEqual(report.status, reparsed.status)
        self.assertEqual(report.timestamp, reparsed.timestamp)

    def test_report_requires_timestamp_and_real_booleans(self) -> None:
        case = load_cases()["cases"][0]
        report = evaluate_replay_certification(build_request(case)).to_dict()
        payload = dict(report)

        missing_timestamp = dict(payload)
        missing_timestamp.pop("timestamp")
        with self.assertRaisesRegex(ValueError, "missing timestamp"):
            ReplayCertificationReport.from_dict(missing_timestamp)

        invalid_bool = dict(payload)
        invalid_bool["paper_entry_permitted"] = "true"
        with self.assertRaisesRegex(ValueError, "paper_entry_permitted"):
            ReplayCertificationReport.from_dict(invalid_bool)

        invalid_log_timestamp = dict(payload)
        invalid_log_timestamp["structured_logs"] = [
            {
                **payload["structured_logs"][0],
                "recorded_at_utc": "2026-03-27T00:00:00",
            },
            *payload["structured_logs"][1:],
        ]
        with self.assertRaisesRegex(
            ValueError,
            "replay structured log record.recorded_at_utc",
        ):
            ReplayCertificationReport.from_dict(invalid_log_timestamp)

        invalid_rule_trace = dict(payload)
        invalid_rule_trace["operator_reason_bundle"] = {
            **payload["operator_reason_bundle"],
            "rule_trace": "not-a-list",
        }
        with self.assertRaisesRegex(
            ValueError,
            "replay operator reason bundle.rule_trace",
        ):
            ReplayCertificationReport.from_dict(invalid_rule_trace)

        self.assertTrue(
            {
                "summary",
                "gate_summary",
                "rule_trace",
                "remediation_hints",
            }.issubset(payload["operator_reason_bundle"].keys())
        )

    def test_smoke_script_emits_selected_case_and_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted test harness invocation
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case-id",
                    "pass_full_replay_certification",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            parsed = decode_json_object(
                result.stdout,
                label="replay certification smoke output",
            )
            self.assertEqual(1, len(parsed["reports"]))
            self.assertEqual(
                "pass_full_replay_certification",
                parsed["reports"][0]["case_id"],
            )
            written = Path(output_dir) / "pass_full_replay_certification.json"
            self.assertTrue(written.exists())
            written_report = decode_json_object(
                written.read_text(encoding="utf-8"),
                label="replay certification smoke file",
            )
            self.assertEqual(
                "REPLAY_CERTIFICATION_PASSED",
                written_report["reason_code"],
            )


if __name__ == "__main__":
    unittest.main()
