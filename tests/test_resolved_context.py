"""Contract tests for resolved-context bundles and execution-profile releases."""

from __future__ import annotations

import unittest

from shared.policy.release_schemas import ReleaseLifecycleState
from shared.policy.resolved_context import (
    VALIDATION_ERRORS,
    ContextBindingSurface,
    ContextContractStatus,
    ContextArtifactBindingRequest,
    ExecutionProfileRelease,
    ResolvedContextBundle,
    evaluate_context_bundle_invalidation,
    validate_context_artifact_binding,
    validate_execution_profile_release,
    validate_resolved_context_bundle,
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


def make_binding(surface_name: ContextBindingSurface) -> ContextArtifactBindingRequest:
    bundle = make_bundle()
    release = make_execution_profile_release()
    return ContextArtifactBindingRequest(
        case_id=f"bind-{surface_name.value}",
        surface_name=surface_name,
        resolved_context_bundle_id=bundle.bundle_id,
        resolved_context_content_hash=bundle.content_hash,
        execution_profile_release_id=release.release_id,
        execution_profile_artifact_hash=release.artifact_root_hash,
    )


class ResolvedContextContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_serialization_preserves_bundle_release_and_binding(self) -> None:
        bundle = make_bundle()
        release = make_execution_profile_release()
        binding = make_binding(ContextBindingSurface.CANDIDATE_BUNDLE)

        self.assertEqual(bundle, ResolvedContextBundle.from_json(bundle.to_json()))
        self.assertEqual(release, ExecutionProfileRelease.from_json(release.to_json()))
        self.assertEqual(binding, ContextArtifactBindingRequest.from_json(binding.to_json()))

    def test_resolved_context_bundle_passes_when_frozen_and_content_addressed(self) -> None:
        report = validate_resolved_context_bundle("bundle-pass", make_bundle())

        self.assertEqual(ContextContractStatus.PASS.value, report.status)
        self.assertEqual("CONTEXT_BUNDLE_FROZEN_AND_PINNED", report.reason_code)
        self.assertEqual("2026-03-01T00:00:00+00:00", report.normalized_observation_cutoff_utc)
        self.assertEqual((), report.missing_fields)

    def test_context_bundle_invalidation_only_allows_plan_defined_causes(self) -> None:
        allowed = evaluate_context_bundle_invalidation(
            make_bundle(),
            "dependency_revocation",
        )
        denied = evaluate_context_bundle_invalidation(
            make_bundle(),
            "manual_override",
        )

        self.assertTrue(allowed.allowed)
        self.assertEqual("CONTEXT_BUNDLE_INVALIDATION_CAUSE_ALLOWED", allowed.reason_code)
        self.assertFalse(denied.allowed)
        self.assertEqual(
            "CONTEXT_BUNDLE_INVALIDATION_CAUSE_NOT_ALLOWED",
            denied.reason_code,
        )

    def test_execution_profile_release_requires_digest_bound_identifier(self) -> None:
        release = make_execution_profile_release()
        good_report = validate_execution_profile_release("profile-pass", release)
        bad_release = ExecutionProfileRelease(
            release_id="execution_profile_release_gold_2026q1_v1",
            data_profile_release_id=release.data_profile_release_id,
            order_type_assumptions=release.order_type_assumptions,
            slippage_surface_ids=release.slippage_surface_ids,
            fill_rules=release.fill_rules,
            latency_assumptions=release.latency_assumptions,
            adverse_selection_penalties=release.adverse_selection_penalties,
            quote_absence_policy=release.quote_absence_policy,
            spread_spike_policy=release.spread_spike_policy,
            degraded_bar_policy=release.degraded_bar_policy,
            calibration_evidence_ids=release.calibration_evidence_ids,
            artifact_root_hash=release.artifact_root_hash,
            lifecycle_state=release.lifecycle_state,
        )
        bad_report = validate_execution_profile_release("profile-bad", bad_release)

        self.assertEqual(ContextContractStatus.PASS.value, good_report.status)
        self.assertEqual("EXECUTION_PROFILE_RELEASE_VERSIONED", good_report.reason_code)
        self.assertEqual(ContextContractStatus.VIOLATION.value, bad_report.status)
        self.assertEqual(
            "EXECUTION_PROFILE_RELEASE_NOT_DIGEST_BOUND",
            bad_report.reason_code,
        )

    def test_binding_passes_for_replay_candidate_and_portability_surfaces(self) -> None:
        for surface_name in ContextBindingSurface:
            with self.subTest(surface_name=surface_name.value):
                report = validate_context_artifact_binding(make_binding(surface_name))
                self.assertEqual(ContextContractStatus.PASS.value, report.status)
                self.assertEqual("CONTEXT_BINDING_DIGEST_PINNED", report.reason_code)
                self.assertTrue(report.digest_bound)

    def test_binding_rejects_mutable_reference_and_execution_overrides(self) -> None:
        mutable_reference_report = validate_context_artifact_binding(
            ContextArtifactBindingRequest(
                case_id="binding-mutable-reference",
                surface_name=ContextBindingSurface.REPLAY_FIXTURE,
                resolved_context_bundle_id=make_bundle().bundle_id,
                resolved_context_content_hash=make_bundle().content_hash,
                execution_profile_release_id=make_execution_profile_release().release_id,
                execution_profile_artifact_hash=make_execution_profile_release().artifact_root_hash,
                mutable_reference_reads=("calendar_definition_table",),
            )
        )
        mutable_execution_report = validate_context_artifact_binding(
            ContextArtifactBindingRequest(
                case_id="binding-mutable-execution",
                surface_name=ContextBindingSurface.CANDIDATE_BUNDLE,
                resolved_context_bundle_id=make_bundle().bundle_id,
                resolved_context_content_hash=make_bundle().content_hash,
                execution_profile_release_id=make_execution_profile_release().release_id,
                execution_profile_artifact_hash=make_execution_profile_release().artifact_root_hash,
                mutable_execution_overrides=("slippage_surface_override",),
            )
        )

        self.assertEqual(
            "CONTEXT_BINDING_MUTABLE_REFERENCE_READ",
            mutable_reference_report.reason_code,
        )
        self.assertEqual(
            "CONTEXT_BINDING_MUTABLE_EXECUTION_OVERRIDE",
            mutable_execution_report.reason_code,
        )


if __name__ == "__main__":
    unittest.main()
