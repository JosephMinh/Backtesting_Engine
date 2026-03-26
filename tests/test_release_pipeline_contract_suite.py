"""Integrated contract suites for the Phase 1/2 release pipeline."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.lifecycle_compatibility import (
    CompatibilityCheckRequest,
    CompatibilityDomain,
    CompatibilityVector,
    LifecycleMachine,
    evaluate_compatibility,
)
from shared.policy.release_certification import (
    CorrectionImpactClass,
    DependentPolicyUpdate,
    DependentSurfaceKind,
    DependentUpdateAction,
    ReleaseCertificationRecord,
    ReleaseCorrectionEvent,
    evaluate_release_correction,
    validate_release_certification,
)
from shared.policy.release_schemas import (
    AnalyticRelease,
    DataProfileRelease,
    DatasetRelease,
    ReleaseLifecycleState,
    validate_analytic_release,
    validate_data_profile_release,
    validate_dataset_release,
)
from shared.policy.release_validation import (
    ReleaseKind,
    ReleaseLifecycleTransitionRequest,
    ReleaseValidationRequest,
    evaluate_release_lifecycle_transition,
    evaluate_release_validation,
)
from shared.policy.resolved_context import (
    ContextArtifactBindingRequest,
    ContextBindingSurface,
    ExecutionConditioningDimension,
    ExecutionProfileClass,
    ExecutionProfileRelease,
    HistoricalExecutionKernel,
    NautilusKernelComponent,
    ResolvedContextBundle,
    evaluate_context_bundle_invalidation,
    validate_context_artifact_binding,
    validate_execution_profile_release,
    validate_resolved_context_bundle,
)
from shared.policy.verification_contract import (
    STRUCTURED_LOGGING_CONTRACT,
    TracePlane,
    validate_log_fixture,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "release_pipeline_contract_suite_cases.json"
)

CANDIDATE_BUNDLE_ID = "candidate_bundle_gold_core_candidate_bundle_sha256_001"
FAMILY_DECISION_RECORD_ID = "family_decision_record_gold_20260326_001"
PROMOTION_PACKET_ID = "promotion_packet_gold_live_v1"
SESSION_READINESS_PACKET_ID = "session_packet_gold_live_20260326"
FIXTURE_TIMESTAMP = "fixture_normalized_timestamp"


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(
            f"release pipeline suite fixture failed to load: {exc}"
        ) from exc


def make_dataset_release() -> DatasetRelease:
    return DatasetRelease(
        release_id="dataset_release_gold_2026q1_v1",
        raw_input_hashes=("raw_sha256_a", "raw_sha256_b"),
        reference_version_hashes=("calendar_sha256_v3", "contracts_sha256_v5"),
        observation_cutoff_utc="2026-03-01T00:00:00+00:00",
        validation_rules_version="validation_rules_v7",
        catalog_version="catalog_v4",
        protocol_versions={
            "ingestion_protocol": "ingest_v2",
            "normalization_protocol": "norm_v3",
        },
        vendor_revision_watermark="databento_revision_2026-03-01",
        correction_horizon="t_plus_2_business_days",
        certification_report_hash="cert_report_sha256_001",
        policy_bundle_hash="policy_bundle_sha256_001",
        lifecycle_state=ReleaseLifecycleState.APPROVED,
    )


def make_analytic_release() -> AnalyticRelease:
    return AnalyticRelease(
        release_id="analytic_release_gold_features_v1",
        dataset_release_id="dataset_release_gold_2026q1_v1",
        feature_version="feature_defs_v9",
        analytic_series_version="analytic_series_v3",
        feature_block_manifests=("manifest://feature_block/core_v9",),
        feature_availability_contracts=("availability://gold/core_v9",),
        slice_manifests=("slice://training_2026q1",),
        artifact_root_hash="artifact_root_sha256_001",
        lifecycle_state=ReleaseLifecycleState.PUBLISHED,
    )


def make_data_profile_release() -> DataProfileRelease:
    return DataProfileRelease(
        release_id="data_profile_release_ibkr_comex_1m_v1",
        source_feeds=("ibkr_historical_bars", "ibkr_live_bars"),
        venue_dataset_ids=("ibkr:comex:1oz:bars:1m",),
        schema_selection_rules=("prefer_ibkr_trade_bar_schema_v2",),
        timestamp_precedence_rule="exchange_end_timestamp_then_vendor_arrival",
        bar_construction_rules=("one_minute_session_anchored_bars",),
        session_anchor_rule="comex_metals_globex_v1",
        trade_quote_precedence_rule="trade_first_then_quote_fallback",
        zero_volume_bar_policy="emit_with_explicit_zero_volume_flag",
        late_print_policy="quarantine_for_recertification_review",
        correction_policy="apply_vendor_corrections_via_delta_release",
        gap_policy="preserve_gaps_explicitly",
        forward_fill_policy="never_forward_fill_prices",
        symbology_mapping_rules=("bind_to_resolved_context_bundle_symbology_v4",),
        live_historical_parity_expectations=("same_session_anchor_and_close_rule",),
        lifecycle_state=ReleaseLifecycleState.APPROVED,
    )


def make_bundle() -> ResolvedContextBundle:
    content_hash = "ctx_bundle_sha256_001"
    return ResolvedContextBundle(
        bundle_id=f"resolved_context_bundle_comex_{content_hash}",
        source_dataset_release_id="dataset_release_gold_2026q1_v1",
        observation_cutoff_utc="2026-03-01T00:00:00+00:00",
        compiled_session_schedule_ids=("globex_schedule_2026q1",),
        compiled_session_anchor_ids=("globex_anchor_2026q1",),
        resolved_reference_record_hashes=("reference_sha256_001", "calendar_sha256_004"),
        quality_mask_ids=("quality_mask_gold_2026q1_v1",),
        protected_zone_mask_ids=("protected_zone_gold_roll_v2",),
        event_window_ids=("event_window_fomc_v7",),
        roll_map_id="roll_map_gold_2026q1_v4",
        delivery_fence_ids=("delivery_fence_gc_h2026_v2",),
        dependency_pin_ids=(
            "dataset_release_gold_2026q1_v1",
            "data_profile_release_ibkr_comex_1m_v1",
            "product_profile_gc_v2",
        ),
        content_hash=content_hash,
        compiler_id="resolved_context_compiler_v3",
        compiler_protocol_version="ctx_protocol_v1",
        portability_policy_resolution_id="portability_policy_gold_v2",
    )


def make_execution_profile_release() -> ExecutionProfileRelease:
    artifact_root_hash = "exec_profile_sha256_001"
    return ExecutionProfileRelease(
        release_id=f"execution_profile_release_gold_2026q1_v1_{artifact_root_hash}",
        profile_class=ExecutionProfileClass.VALIDATION,
        promotion_grade=True,
        historical_execution_kernel=HistoricalExecutionKernel.NAUTILUS_HIGH_LEVEL,
        kernel_components=(
            NautilusKernelComponent.BACKTEST_NODE.value,
            NautilusKernelComponent.BACKTEST_RUN_CONFIG.value,
            NautilusKernelComponent.PARQUET_DATA_CATALOG.value,
        ),
        shared_signal_kernel_binding="canonical_signal_kernel_nautilus_binding_v1",
        conditioning_dimensions=(
            ExecutionConditioningDimension.SESSION_CLASS.value,
            ExecutionConditioningDimension.REALIZED_VOLATILITY_BUCKET.value,
            ExecutionConditioningDimension.SPREAD_BUCKET.value,
            ExecutionConditioningDimension.INTENDED_ORDER_SIZE_FRACTION_BUCKET.value,
        ),
        data_profile_release_id="data_profile_release_ibkr_comex_1m_v1",
        order_type_assumptions=("marketable_limit_orders_only",),
        slippage_surface_ids=("slippage_surface_gc_rth_v3", "slippage_surface_gc_eth_v3"),
        fill_rules=("fill_partial_on_displayed_depth_only",),
        latency_assumptions=("submit_to_ack_p50_35ms", "submit_to_ack_p95_120ms"),
        adverse_selection_penalties=("spread_cross_penalty_bp_4",),
        quote_absence_policy="defer_to_trade_only_fill_guard",
        spread_spike_policy="widen_slippage_surface_and_cap_size",
        degraded_bar_policy="block_signal_generation_on_degraded_bars",
        calibration_evidence_ids=("execution_profile_calibration_gc_2026q1_v1",),
        artifact_root_hash=artifact_root_hash,
        lifecycle_state=ReleaseLifecycleState.APPROVED,
    )


def make_binding() -> ContextArtifactBindingRequest:
    bundle = make_bundle()
    release = make_execution_profile_release()
    return ContextArtifactBindingRequest(
        case_id="bind-candidate-bundle",
        surface_name=ContextBindingSurface.CANDIDATE_BUNDLE,
        resolved_context_bundle_id=bundle.bundle_id,
        resolved_context_content_hash=bundle.content_hash,
        execution_profile_release_id=release.release_id,
        execution_profile_artifact_hash=release.artifact_root_hash,
    )


def make_certification_record() -> ReleaseCertificationRecord:
    return ReleaseCertificationRecord(
        certification_id="release_cert_gc_2026q1_v1",
        release_kind="dataset_release",
        release_id="dataset_release_gold_2026q1_v1",
        deterministic_manifest_hash="manifest_sha256_001",
        prior_release_semantic_diff_hash="semantic_diff_sha256_001",
        validation_summary_hash="validation_summary_sha256_001",
        policy_evaluation_hash="policy_eval_sha256_001",
        canary_or_parity_required=True,
        canary_or_parity_evidence_ids=("parity_fixture_gc_2026q1_v1",),
        signed_certification_report_hash="signed_cert_report_sha256_001",
        signer_ids=("ops_reviewer_a", "risk_reviewer_b"),
        certified_at_utc="2026-03-26T16:00:00+00:00",
        lifecycle_state=ReleaseLifecycleState.CERTIFIED,
    )


def make_correction_event() -> ReleaseCorrectionEvent:
    return ReleaseCorrectionEvent(
        correction_event_id="release_correction_gc_2026q1_v2",
        release_kind="dataset_release",
        release_id="dataset_release_gold_2026q1_v1",
        certified_vendor_revision_watermark="vendor_rev_2026-03-20",
        corrected_vendor_revision_watermark="vendor_rev_2026-03-25",
        semantic_impact_diff_hash="semantic_diff_sha256_002",
        impact_class=CorrectionImpactClass.SUSPECT,
        preserves_prior_reproducibility=True,
        superseding_release_id="dataset_release_gc_2026q1_v2",
        dependent_updates=(
            DependentPolicyUpdate(
                surface_kind=DependentSurfaceKind.ANALYTIC_RELEASE,
                surface_id="analytic_release_gc_features_v1",
                action=DependentUpdateAction.QUARANTINE,
                reason_bundle="Upstream correction makes the analytic release suspect.",
            ),
            DependentPolicyUpdate(
                surface_kind=DependentSurfaceKind.BUNDLE_READINESS_RECORD,
                surface_id="readiness_gc_candidate_v3",
                action=DependentUpdateAction.SUPERSEDE,
                reason_bundle="Readiness must point at the superseding dataset release.",
            ),
        ),
        justification="The corrected vendor revision changes certified rows after publication.",
        recorded_at_utc="2026-03-26T16:05:00+00:00",
    )


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "timestamp":
                normalized[key] = FIXTURE_TIMESTAMP
            else:
                normalized[key] = _normalize_payload(item)
        return normalized
    if isinstance(value, tuple):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    return value


def _payload_for(report: Any) -> dict[str, Any]:
    return _normalize_payload(report.to_dict())


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _manifest_entry(
    *,
    artifact_id: str,
    artifact_role: str,
    relative_path: str,
    payload: Any,
    content_type: str = "application/json",
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_role": artifact_role,
        "relative_path": relative_path,
        "sha256": _sha256_json(payload),
        "content_type": content_type,
    }


def _build_manifest(
    *,
    manifest_id: str,
    generated_at_utc: str,
    retention_class: str,
    redaction_policy: str,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "manifest_id": manifest_id,
        "generated_at_utc": generated_at_utc,
        "retention_class": retention_class,
        "contains_secrets": False,
        "redaction_policy": redaction_policy,
        "artifacts": artifacts,
    }


def _validate_manifest_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = STRUCTURED_LOGGING_CONTRACT.artifact_manifest
    for field_name in contract.required_fields:
        if field_name not in manifest:
            errors.append(f"manifest missing field {field_name}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest.artifacts must be a non-empty list")
        return errors
    for index, artifact in enumerate(artifacts):
        for field_name in contract.required_artifact_fields:
            if field_name not in artifact:
                errors.append(f"manifest.artifacts[{index}] missing field {field_name}")
    return errors


def _build_expected_vs_actual_diff(
    case_id: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    entries = []
    for field_name, expected_value in expected.items():
        actual_value = actual[field_name]
        entries.append(
            {
                "field": field_name,
                "expected": expected_value,
                "actual": actual_value,
                "matched": expected_value == actual_value,
            }
        )
    return {
        "case_id": case_id,
        "entries": entries,
        "mismatches": [entry["field"] for entry in entries if not entry["matched"]],
    }


def _build_log(
    *,
    plane: TracePlane,
    case_id: str,
    recorded_at_utc: str,
    correlation_id: str,
    reason_code: str,
    reason_summary: str,
    referenced_ids: dict[str, str],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": STRUCTURED_LOGGING_CONTRACT.schema_version,
        "event_type": f"{plane.value}.release_pipeline_case_recorded",
        "plane": plane.value,
        "event_id": f"{plane.value}_{case_id}",
        "recorded_at_utc": recorded_at_utc,
        "correlation_id": correlation_id,
        "decision_trace_id": f"decision_trace_{plane.value}_{case_id}",
        "reason_code": reason_code,
        "reason_summary": reason_summary,
        "redacted_fields": [],
        "omitted_fields": [],
        "referenced_ids": referenced_ids,
        "artifact_manifest": _build_manifest(
            manifest_id=f"artifact_manifest_{plane.value}_{case_id}",
            generated_at_utc=recorded_at_utc,
            retention_class="gate_decision",
            redaction_policy="verification_suite_only",
            artifacts=artifacts,
        ),
    }


def _build_case_result(case: dict[str, Any]) -> dict[str, Any]:
    dataset = make_dataset_release()
    analytic = make_analytic_release()
    data_profile = make_data_profile_release()
    bundle = make_bundle()
    execution_profile = make_execution_profile_release()
    binding = make_binding()
    certification = make_certification_record()

    dataset_report = validate_dataset_release(case["case_id"], dataset)
    analytic_report = validate_analytic_release(case["case_id"], analytic)
    data_profile_report = validate_data_profile_release(case["case_id"], data_profile)
    execution_profile_report = validate_execution_profile_release(
        case["case_id"], execution_profile
    )
    context_bundle_report = validate_resolved_context_bundle(case["case_id"], bundle)
    context_binding_report = validate_context_artifact_binding(binding)
    certification_report = validate_release_certification(certification)

    if case["scenario_kind"] == "activation":
        validation_report = evaluate_release_validation(
            ReleaseValidationRequest(
                case_id=case["case_id"],
                release_id=dataset.release_id,
                release_kind=ReleaseKind.DATASET,
            )
        )
        transition_report = evaluate_release_lifecycle_transition(
            ReleaseLifecycleTransitionRequest(
                case_id=case["case_id"],
                release_id=dataset.release_id,
                release_kind=ReleaseKind.DATASET,
                from_state="APPROVED",
                to_state="ACTIVE",
                dependent_artifact_ids=(analytic.release_id,),
                reproducibility_stamp_present=True,
            )
        )
        correction_report = None
        context_invalidation_report = None
        compatibility_report = evaluate_compatibility(
            CompatibilityCheckRequest(
                case_id=case["case_id"],
                subject_id="deployment_instance_gold_v1",
                machine_id=LifecycleMachine.DEPLOYMENT_INSTANCE.value,
                baseline=CompatibilityVector(
                    data_protocol="data/v1",
                    strategy_protocol="strategy/v1",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v1",
                ),
                candidate=CompatibilityVector(
                    data_protocol="data/v1",
                    strategy_protocol="strategy/v1",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v1",
                ),
            )
        )
    else:
        validation_report = evaluate_release_validation(
            ReleaseValidationRequest(
                case_id=case["case_id"],
                release_id=dataset.release_id,
                release_kind=ReleaseKind.DATASET,
                structural_schema_failures=2,
                session_misalignment_events=7,
                duplicate_or_out_of_order_events=5,
                failing_records_preserved=True,
                source_truth_preserved=True,
            )
        )
        transition_report = evaluate_release_lifecycle_transition(
            ReleaseLifecycleTransitionRequest(
                case_id=case["case_id"],
                release_id=dataset.release_id,
                release_kind=ReleaseKind.DATASET,
                from_state="ACTIVE",
                to_state="QUARANTINED",
                dependent_artifact_ids=(analytic.release_id,),
                reproducibility_stamp_present=True,
            )
        )
        correction_report = evaluate_release_correction(make_correction_event())
        context_invalidation_report = evaluate_context_bundle_invalidation(
            bundle,
            "dependency_revocation",
        )
        compatibility_report = evaluate_compatibility(
            CompatibilityCheckRequest(
                case_id=case["case_id"],
                subject_id="deployment_instance_gold_v1",
                machine_id=LifecycleMachine.DEPLOYMENT_INSTANCE.value,
                baseline=CompatibilityVector(
                    data_protocol="data/v1",
                    strategy_protocol="strategy/v1",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v1",
                ),
                candidate=CompatibilityVector(
                    data_protocol="data/v2",
                    strategy_protocol="strategy/v1",
                    ops_protocol="ops/v1",
                    policy_bundle_hash="policy/sha256:111",
                    compatibility_matrix_version="matrix/v2",
                ),
                declared_affected_domains=(
                    CompatibilityDomain.DATA_PROTOCOL.value,
                    CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value,
                ),
            )
        )

    certification_target = correction_report or certification_report

    actual_fields: dict[str, Any] = {
        "dataset_publication_status": dataset_report.status,
        "dataset_publication_reason_code": dataset_report.reason_code,
        "analytic_publication_status": analytic_report.status,
        "analytic_publication_reason_code": analytic_report.reason_code,
        "data_profile_publication_status": data_profile_report.status,
        "data_profile_publication_reason_code": data_profile_report.reason_code,
        "execution_profile_status": execution_profile_report.status,
        "execution_profile_reason_code": execution_profile_report.reason_code,
        "validation_status": validation_report.status,
        "validation_reason_code": validation_report.reason_code,
        "transition_status": transition_report.status,
        "transition_reason_code": transition_report.reason_code,
        "context_bundle_status": context_bundle_report.status,
        "context_bundle_reason_code": context_bundle_report.reason_code,
        "context_binding_status": context_binding_report.status,
        "context_binding_reason_code": context_binding_report.reason_code,
        "certification_status": certification_report.status,
        "certification_reason_code": certification_report.reason_code,
        "compatibility_status": compatibility_report.status,
        "compatibility_reason_code": compatibility_report.reason_code,
        "release_log_reason_code": validation_report.reason_code,
        "certification_log_reason_code": certification_target.reason_code,
    }
    if correction_report is not None:
        actual_fields["correction_status"] = correction_report.status
        actual_fields["correction_reason_code"] = correction_report.reason_code
        actual_fields["correction_actions"] = list(correction_report.dependent_actions)
    if context_invalidation_report is not None:
        actual_fields["context_invalidation_status"] = context_invalidation_report.status
        actual_fields["context_invalidation_reason_code"] = (
            context_invalidation_report.reason_code
        )
    if validation_report.sidecar_masks:
        actual_fields["expected_mask_classes"] = [
            mask.finding_class for mask in validation_report.sidecar_masks
        ]
    if compatibility_report.changed_domains:
        actual_fields["compatibility_changed_domains"] = list(
            compatibility_report.changed_domains
        )

    diff_payload = _build_expected_vs_actual_diff(case["case_id"], case["expected"], actual_fields)

    release_log = _build_log(
        plane=TracePlane.RELEASE,
        case_id=case["case_id"],
        recorded_at_utc=case["recorded_at_utc"],
        correlation_id=case["correlation_id"],
        reason_code=validation_report.reason_code,
        reason_summary=validation_report.explanation,
        referenced_ids={
            "dataset_release_id": dataset.release_id,
            "analytic_release_id": analytic.release_id,
            "data_profile_release_id": data_profile.release_id,
            "resolved_context_bundle_id": bundle.bundle_id,
            "candidate_bundle_id": CANDIDATE_BUNDLE_ID,
        },
        artifacts=[
            _manifest_entry(
                artifact_id=f"{case['case_id']}_release_validation_report",
                artifact_role="release_validation_report",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/release_validation.json"
                ),
                payload=_payload_for(validation_report),
            ),
            _manifest_entry(
                artifact_id=f"{case['case_id']}_expected_vs_actual_diff",
                artifact_role="expected_vs_actual_diff",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/expected_vs_actual_diff.json"
                ),
                payload=diff_payload,
            ),
        ],
    )
    certification_log = _build_log(
        plane=TracePlane.CERTIFICATION,
        case_id=case["case_id"],
        recorded_at_utc=case["recorded_at_utc"],
        correlation_id=case["correlation_id"],
        reason_code=certification_target.reason_code,
        reason_summary=certification_target.explanation,
        referenced_ids={
            "family_decision_record_id": FAMILY_DECISION_RECORD_ID,
            "candidate_bundle_id": CANDIDATE_BUNDLE_ID,
            "promotion_packet_id": PROMOTION_PACKET_ID,
            "session_readiness_packet_id": SESSION_READINESS_PACKET_ID,
        },
        artifacts=[
            _manifest_entry(
                artifact_id=f"{case['case_id']}_certification_report",
                artifact_role="certification_report",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/certification_report.json"
                ),
                payload=_payload_for(certification_report),
            ),
            _manifest_entry(
                artifact_id=f"{case['case_id']}_operator_reason_bundle",
                artifact_role="operator_reason_bundle",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/operator_reason_bundle.json"
                ),
                payload={
                    "case_id": case["case_id"],
                    "release_reason": validation_report.explanation,
                    "certification_reason": certification_target.explanation,
                },
            ),
        ],
    )

    suite_manifest = _build_manifest(
        manifest_id=f"suite_manifest_{case['case_id']}",
        generated_at_utc=case["recorded_at_utc"],
        retention_class="verification_suite",
        redaction_policy="verification_suite_only",
        artifacts=[
            _manifest_entry(
                artifact_id=f"{case['case_id']}_release_log",
                artifact_role="structured_log_release",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/release_log.json"
                ),
                payload=release_log,
            ),
            _manifest_entry(
                artifact_id=f"{case['case_id']}_certification_log",
                artifact_role="structured_log_certification",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/certification_log.json"
                ),
                payload=certification_log,
            ),
            _manifest_entry(
                artifact_id=f"{case['case_id']}_expected_vs_actual_diff_bundle",
                artifact_role="expected_vs_actual_diff",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/expected_vs_actual_diff_bundle.json"
                ),
                payload=diff_payload,
            ),
            _manifest_entry(
                artifact_id=f"{case['case_id']}_operator_reason_bundle_bundle",
                artifact_role="operator_reason_bundle",
                relative_path=(
                    f"verification/release_pipeline/{case['case_id']}/operator_reason_bundle_bundle.json"
                ),
                payload={
                    "case_id": case["case_id"],
                    "validation_reason_code": validation_report.reason_code,
                    "certification_reason_code": certification_target.reason_code,
                },
            ),
        ],
    )

    return {
        "actual_fields": actual_fields,
        "diff_payload": diff_payload,
        "release_log": release_log,
        "certification_log": certification_log,
        "suite_manifest": suite_manifest,
    }


class ReleasePipelineContractSuiteTest(unittest.TestCase):
    def test_fixture_cases_emit_expected_reports_and_zero_diff_mismatches(self) -> None:
        for case in load_cases()["suite_cases"]:
            with self.subTest(case_id=case["case_id"]):
                result = _build_case_result(case)
                for field_name, expected_value in case["expected"].items():
                    self.assertEqual(expected_value, result["actual_fields"][field_name])
                self.assertEqual([], result["diff_payload"]["mismatches"])

    def test_suite_logs_validate_against_shared_structured_logging_contract(self) -> None:
        for case in load_cases()["suite_cases"]:
            with self.subTest(case_id=case["case_id"]):
                result = _build_case_result(case)
                self.assertEqual([], validate_log_fixture(TracePlane.RELEASE, result["release_log"]))
                self.assertEqual(
                    [],
                    validate_log_fixture(
                        TracePlane.CERTIFICATION,
                        result["certification_log"],
                    ),
                )

    def test_suite_manifest_retains_diffs_logs_and_reason_bundles(self) -> None:
        for case in load_cases()["suite_cases"]:
            with self.subTest(case_id=case["case_id"]):
                result = _build_case_result(case)
                manifest = result["suite_manifest"]
                self.assertEqual([], _validate_manifest_shape(manifest))
                roles = {
                    artifact["artifact_role"] for artifact in manifest["artifacts"]
                }
                self.assertTrue(
                    {
                        "structured_log_release",
                        "structured_log_certification",
                        "expected_vs_actual_diff",
                        "operator_reason_bundle",
                    }.issubset(roles)
                )

    def test_suite_artifacts_are_reproducible_for_fixed_fixture_inputs(self) -> None:
        for case in load_cases()["suite_cases"]:
            with self.subTest(case_id=case["case_id"]):
                first = _build_case_result(case)
                second = _build_case_result(case)
                self.assertEqual(first["diff_payload"], second["diff_payload"])
                self.assertEqual(first["release_log"], second["release_log"])
                self.assertEqual(first["certification_log"], second["certification_log"])
                self.assertEqual(first["suite_manifest"], second["suite_manifest"])


if __name__ == "__main__":
    unittest.main()
