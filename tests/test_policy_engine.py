"""Contract tests for the shared policy engine and normalized decision traces."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.deployment_packets import (
    BundleReadinessRecord,
    PromotionPacket,
    SessionReadinessPacket,
)
from shared.policy.policy_engine import (
    VALIDATION_ERRORS,
    PolicyDecisionTrace,
    PolicyEngine,
    PolicyWaiver,
)
from shared.policy.release_validation import (
    ReleaseKind,
    ReleaseLifecycleTransitionRequest,
)
from shared.policy.research_state import (
    FamilyDecisionRecord,
    FamilyDecisionType,
    ResearchAdmissibilityClass,
    ResearchRunPurpose,
    ResearchRunRecord,
    ResearchStateStore,
    ReviewerAttestation,
    record_family_decision,
    record_research_run,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "policy_engine_cases.json"
)
EVALUATED_AT_UTC = "2026-03-26T18:00:00+00:00"


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"policy engine fixture failed to load: {exc}") from exc


def build_request(payload: dict[str, object]) -> ReleaseLifecycleTransitionRequest:
    return ReleaseLifecycleTransitionRequest(
        case_id=str(payload["case_id"]),
        release_id=str(payload["release_id"]),
        release_kind=ReleaseKind(str(payload["release_kind"])),
        from_state=str(payload["from_state"]),
        to_state=str(payload["to_state"]),
        dependent_artifact_ids=tuple(
            str(item) for item in payload.get("dependent_artifact_ids", ())
        ),
        reproducibility_stamp_present=bool(
            payload.get("reproducibility_stamp_present", True)
        ),
    )


def build_readiness(payload: dict[str, object]) -> BundleReadinessRecord:
    return BundleReadinessRecord.from_dict(payload)


def build_session(payload: dict[str, object]) -> SessionReadinessPacket:
    return SessionReadinessPacket.from_dict(payload)


def build_promotion(payload: dict[str, object]) -> PromotionPacket:
    return PromotionPacket.from_dict(payload)


def build_waivers(payloads: list[dict[str, object]]) -> tuple[PolicyWaiver, ...]:
    return tuple(PolicyWaiver.from_dict(payload) for payload in payloads)


def sample_attestation(reviewer_id: str = "operator_self") -> ReviewerAttestation:
    return ReviewerAttestation(
        reviewer_id=reviewer_id,
        attested_controls=("budget_review", "evidence_review"),
        signed_at_utc="2026-03-26T15:00:00+00:00",
    )


def sample_research_run() -> ResearchRunRecord:
    return ResearchRunRecord(
        research_run_id="run-001",
        family_id="gold_breakout",
        subfamily_id="baseline",
        run_purpose=ResearchRunPurpose.VALIDATION,
        code_digests=("kernel:abc123", "research:def456"),
        environment_lock_id="uv.lock:sha256:001",
        dataset_release_id="dataset_release_v1",
        analytic_release_id="analytic_release_v1",
        data_profile_release_id="data_profile_release_v1",
        execution_profile_id="execution_profile_v1",
        parameter_reference_id="params_v1",
        seeds=(7, 11),
        policy_bundle_hash="policy_bundle_sha256_001",
        compatibility_matrix_version="compat_v1",
        output_artifact_digests=("artifact_a", "artifact_b"),
        admissibility_class=ResearchAdmissibilityClass.DIAGNOSTIC_ONLY,
        parent_run_ids=(),
    )


def sample_decision() -> FamilyDecisionRecord:
    return FamilyDecisionRecord(
        decision_record_id="decision-001",
        family_id="gold_breakout",
        decision_timestamp_utc="2026-03-26T15:05:00+00:00",
        decision_type=FamilyDecisionType.CONTINUE,
        evidence_references=("run-001",),
        budget_consumed_usd=250.0,
        next_budget_authorized_usd=500.0,
        reviewer_self_attestations=(sample_attestation(),),
        reason_bundle=("evidence_quality_green", "budget_remaining_sufficient"),
        revisit_at_utc=None,
    )


def sample_store() -> ResearchStateStore:
    store = ResearchStateStore()
    record_research_run(store, sample_research_run())
    record_family_decision(store, sample_decision())
    return store


def non_null_reason_codes(trace: PolicyDecisionTrace) -> list[str]:
    return [rule.reason_code for rule in trace.evaluated_rules if rule.reason_code]


class PolicyEngineContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_trace_round_trip_preserves_serialized_shape(self) -> None:
        case = load_cases()["lifecycle_cases"][0]
        trace = PolicyEngine(
            policy_bundle_hash=case["policy_bundle_hash"],
            evaluated_at_utc=EVALUATED_AT_UTC,
        ).evaluate_lifecycle_transition(build_request(case["request"]))

        self.assertEqual(trace, PolicyDecisionTrace.from_json(trace.to_json()))

    def test_lifecycle_fixture_cases_emit_expected_decisions(self) -> None:
        for payload in load_cases()["lifecycle_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                trace = PolicyEngine(
                    policy_bundle_hash=payload["policy_bundle_hash"],
                    waivers=build_waivers(payload["waivers"]),
                    evaluated_at_utc=EVALUATED_AT_UTC,
                ).evaluate_lifecycle_transition(build_request(payload["request"]))
                self.assertEqual(payload["expected_decision"], trace.decision)
                self.assertEqual(
                    payload["expected_decision_reason_code"],
                    trace.decision_reason_code,
                )
                self.assertEqual(
                    payload["expected_rule_reason_codes"],
                    non_null_reason_codes(trace),
                )
                self.assertEqual(
                    tuple(payload["expected_waiver_references"]),
                    trace.waiver_references,
                )

    def test_freshness_fixture_cases_emit_expected_decisions(self) -> None:
        for payload in load_cases()["freshness_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                trace = PolicyEngine(
                    policy_bundle_hash=payload["policy_bundle_hash"],
                    waivers=build_waivers(payload["waivers"]),
                    evaluated_at_utc=EVALUATED_AT_UTC,
                ).evaluate_freshness_gate(
                    gate_name=payload["gate_name"],
                    integrity_artifacts=payload["integrity_artifacts"],
                    freshness_evidence=payload["freshness_evidence"],
                )
                self.assertEqual(payload["expected_decision"], trace.decision)
                self.assertEqual(
                    payload["expected_decision_reason_code"],
                    trace.decision_reason_code,
                )
                self.assertEqual(
                    payload["expected_rule_reason_codes"],
                    non_null_reason_codes(trace),
                )
                self.assertEqual(
                    tuple(payload["expected_waiver_references"]),
                    trace.waiver_references,
                )

    def test_session_fixture_cases_emit_expected_decisions(self) -> None:
        for payload in load_cases()["session_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                trace = PolicyEngine(
                    policy_bundle_hash=payload["policy_bundle_hash"],
                    waivers=build_waivers(payload["waivers"]),
                    evaluated_at_utc=EVALUATED_AT_UTC,
                ).evaluate_session_readiness(
                    case_id=payload["case_id"],
                    readiness_record=build_readiness(payload["readiness"]),
                    session_packet=build_session(payload["session"]),
                )
                self.assertEqual(payload["expected_decision"], trace.decision)
                self.assertEqual(
                    payload["expected_decision_reason_code"],
                    trace.decision_reason_code,
                )
                self.assertEqual(
                    payload["expected_rule_reason_codes"],
                    non_null_reason_codes(trace),
                )
                self.assertEqual(
                    tuple(payload["expected_waiver_references"]),
                    trace.waiver_references,
                )

    def test_promotion_fixture_cases_emit_expected_decisions(self) -> None:
        store = sample_store()
        for payload in load_cases()["promotion_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                trace = PolicyEngine(
                    policy_bundle_hash=payload["policy_bundle_hash"],
                    waivers=build_waivers(payload["waivers"]),
                    evaluated_at_utc=EVALUATED_AT_UTC,
                ).evaluate_promotion_decision(
                    case_id=payload["case_id"],
                    promotion_packet=build_promotion(payload["promotion"]),
                    store=store,
                    decision_record_id="decision-001",
                )
                self.assertEqual(payload["expected_decision"], trace.decision)
                self.assertEqual(
                    payload["expected_decision_reason_code"],
                    trace.decision_reason_code,
                )
                self.assertEqual(
                    payload["expected_rule_reason_codes"],
                    non_null_reason_codes(trace),
                )
                self.assertEqual(
                    tuple(payload["expected_waiver_references"]),
                    trace.waiver_references,
                )

    def test_session_trace_is_structured_and_carries_waiver_metadata(self) -> None:
        payload = load_cases()["session_cases"][1]
        trace = PolicyEngine(
            policy_bundle_hash=payload["policy_bundle_hash"],
            waivers=build_waivers(payload["waivers"]),
            evaluated_at_utc=EVALUATED_AT_UTC,
        ).evaluate_session_readiness(
            case_id=payload["case_id"],
            readiness_record=build_readiness(payload["readiness"]),
            session_packet=build_session(payload["session"]),
        )
        rendered = trace.to_dict()

        self.assertEqual("allow_with_waiver", trace.decision)
        self.assertTrue(
            {
                "decision_id",
                "category",
                "policy_bundle_hash",
                "inputs",
                "evaluated_rules",
                "waiver_references",
                "decision",
                "decision_reason_code",
                "decision_diagnostic",
                "timestamp",
            }.issubset(rendered.keys())
        )
        readiness_rule = next(
            rule for rule in rendered["evaluated_rules"] if rule["rule_id"] == "bundle_readiness_record"
        )
        self.assertTrue(readiness_rule["waived"])
        self.assertEqual(
            ["waiver_readiness_freshness"],
            readiness_rule["waiver_references"],
        )


if __name__ == "__main__":
    unittest.main()
