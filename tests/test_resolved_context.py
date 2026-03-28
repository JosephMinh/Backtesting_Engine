"""Contract tests for resolved-context bundles and execution-profile releases."""

from __future__ import annotations

import unittest

from shared.policy.release_schemas import ReleaseLifecycleState
from shared.policy.resolved_context import (
    VALIDATION_ERRORS,
    ContextBindingSurface,
    ContextContractStatus,
    ContextArtifactBindingRequest,
    ExecutionConditioningDimension,
    ExecutionProfileClass,
    ExecutionProfileRelease,
    HistoricalExecutionKernel,
    HistoricalSimulationHarness,
    NautilusKernelComponent,
    ResolvedContextBundle,
    evaluate_context_bundle_invalidation,
    validate_context_artifact_binding,
    validate_execution_profile_release,
    validate_historical_simulation_harness,
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


def make_execution_profile_release(
    profile_class: ExecutionProfileClass = ExecutionProfileClass.VALIDATION,
) -> ExecutionProfileRelease:
    artifact_root_hash = "exec_profile_sha256_001"
    promotion_grade = profile_class != ExecutionProfileClass.SCREENING
    return ExecutionProfileRelease(
        release_id=f"execution_profile_release_gold_2026q1_v1_{artifact_root_hash}",
        profile_class=profile_class,
        promotion_grade=promotion_grade,
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


def make_simulation_harness() -> HistoricalSimulationHarness:
    release = make_execution_profile_release()
    return HistoricalSimulationHarness(
        case_id="nautilus-validation-harness",
        historical_execution_kernel=HistoricalExecutionKernel.NAUTILUS_HIGH_LEVEL,
        execution_profile_release_id=release.release_id,
        profile_class=release.profile_class,
        release_reference_ids=(
            "dataset_release_gold_2026q1_v1",
            release.data_profile_release_id,
            make_bundle().bundle_id,
        ),
        random_seeds=(11, 29),
        retained_run_log_ids=(
            "nautilus_validation_seed_11_log_sha256_001",
            "nautilus_validation_seed_29_log_sha256_002",
        ),
        shared_signal_kernel_binding=release.shared_signal_kernel_binding,
        uses_high_level_backtest_api=True,
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
        harness = make_simulation_harness()

        self.assertEqual(bundle, ResolvedContextBundle.from_json(bundle.to_json()))
        self.assertEqual(release, ExecutionProfileRelease.from_json(release.to_json()))
        self.assertEqual(binding, ContextArtifactBindingRequest.from_json(binding.to_json()))
        self.assertEqual(harness, HistoricalSimulationHarness.from_json(harness.to_json()))

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
            profile_class=release.profile_class,
            promotion_grade=release.promotion_grade,
            historical_execution_kernel=release.historical_execution_kernel,
            kernel_components=release.kernel_components,
            shared_signal_kernel_binding=release.shared_signal_kernel_binding,
            conditioning_dimensions=release.conditioning_dimensions,
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

    def test_execution_profile_release_accepts_screening_validation_and_stress_classes(self) -> None:
        for profile_class in ExecutionProfileClass:
            with self.subTest(profile_class=profile_class.value):
                report = validate_execution_profile_release(
                    f"profile-{profile_class.value}",
                    make_execution_profile_release(profile_class),
                )
                self.assertEqual(ContextContractStatus.PASS.value, report.status)
                self.assertEqual("EXECUTION_PROFILE_RELEASE_VERSIONED", report.reason_code)

    def test_execution_profile_release_rejects_unapproved_kernel_or_incomplete_promotion_dims(self):
        release = make_execution_profile_release()
        bad_kernel = ExecutionProfileRelease(
            release_id=release.release_id,
            profile_class=release.profile_class,
            promotion_grade=release.promotion_grade,
            historical_execution_kernel=HistoricalExecutionKernel.UNAPPROVED_ENGINE,
            kernel_components=release.kernel_components,
            shared_signal_kernel_binding=release.shared_signal_kernel_binding,
            conditioning_dimensions=release.conditioning_dimensions,
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
        bad_dimensions = ExecutionProfileRelease(
            release_id=release.release_id,
            profile_class=ExecutionProfileClass.STRESS,
            promotion_grade=True,
            historical_execution_kernel=release.historical_execution_kernel,
            kernel_components=release.kernel_components,
            shared_signal_kernel_binding=release.shared_signal_kernel_binding,
            conditioning_dimensions=(ExecutionConditioningDimension.SESSION_CLASS.value,),
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
        screening_as_promotion_grade = ExecutionProfileRelease(
            release_id=release.release_id,
            profile_class=ExecutionProfileClass.SCREENING,
            promotion_grade=True,
            historical_execution_kernel=release.historical_execution_kernel,
            kernel_components=release.kernel_components,
            shared_signal_kernel_binding=release.shared_signal_kernel_binding,
            conditioning_dimensions=release.conditioning_dimensions,
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

        bad_kernel_report = validate_execution_profile_release("profile-bad-kernel", bad_kernel)
        bad_dims_report = validate_execution_profile_release(
            "profile-bad-dimensions", bad_dimensions
        )
        screening_report = validate_execution_profile_release(
            "profile-screening-promotion", screening_as_promotion_grade
        )

        self.assertEqual(
            "EXECUTION_PROFILE_RELEASE_KERNEL_NOT_APPROVED",
            bad_kernel_report.reason_code,
        )
        self.assertEqual(
            "EXECUTION_PROFILE_RELEASE_PROMOTION_DIMENSIONS_INCOMPLETE",
            bad_dims_report.reason_code,
        )
        self.assertEqual(
            "EXECUTION_PROFILE_RELEASE_SCREENING_NOT_PROMOTION_GRADE",
            screening_report.reason_code,
        )

    def test_simulation_harness_requires_nautilus_and_retained_logs(self) -> None:
        harness = make_simulation_harness()
        passing = validate_historical_simulation_harness(harness)
        custom_engine = HistoricalSimulationHarness(
            case_id=harness.case_id,
            historical_execution_kernel=HistoricalExecutionKernel.NAUTILUS_HIGH_LEVEL,
            execution_profile_release_id=harness.execution_profile_release_id,
            profile_class=harness.profile_class,
            release_reference_ids=harness.release_reference_ids,
            random_seeds=harness.random_seeds,
            retained_run_log_ids=harness.retained_run_log_ids,
            shared_signal_kernel_binding=harness.shared_signal_kernel_binding,
            uses_high_level_backtest_api=False,
            uses_custom_historical_engine=True,
        )
        incomplete_logs = HistoricalSimulationHarness(
            case_id=harness.case_id,
            historical_execution_kernel=harness.historical_execution_kernel,
            execution_profile_release_id=harness.execution_profile_release_id,
            profile_class=harness.profile_class,
            release_reference_ids=harness.release_reference_ids,
            random_seeds=harness.random_seeds,
            retained_run_log_ids=(harness.retained_run_log_ids[0],),
            shared_signal_kernel_binding=harness.shared_signal_kernel_binding,
            uses_high_level_backtest_api=True,
        )

        custom_engine_report = validate_historical_simulation_harness(custom_engine)
        incomplete_logs_report = validate_historical_simulation_harness(incomplete_logs)

        self.assertEqual(ContextContractStatus.PASS.value, passing.status)
        self.assertEqual("SIMULATION_HARNESS_NAUTILUS_RETAINED", passing.reason_code)
        self.assertEqual(
            "SIMULATION_HARNESS_CUSTOM_ENGINE_FORBIDDEN",
            custom_engine_report.reason_code,
        )
        self.assertEqual(
            "SIMULATION_HARNESS_RUN_LOGS_INCOMPLETE",
            incomplete_logs_report.reason_code,
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

    def test_bundle_loader_requires_explicit_integer_schema_version(self) -> None:
        payload = make_bundle().to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "resolved_context_bundle: missing required field 'schema_version'",
        ):
            ResolvedContextBundle.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(
            ValueError,
            "resolved_context_bundle: schema_version must be an integer",
        ):
            ResolvedContextBundle.from_dict(payload_with_bool_schema)

        payload_with_unsupported_schema = dict(payload)
        payload_with_unsupported_schema["schema_version"] = 2
        with self.assertRaisesRegex(
            ValueError,
            "resolved_context_bundle: schema_version must be 1",
        ):
            ResolvedContextBundle.from_dict(payload_with_unsupported_schema)

    def test_bundle_loader_rejects_non_object_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "resolved_context_bundle: payload must be an object",
        ):
            ResolvedContextBundle.from_dict([])  # type: ignore[arg-type]

    def test_bundle_loader_requires_serialized_nullable_field_presence(self) -> None:
        payload = make_bundle().to_dict()
        payload.pop("portability_policy_resolution_id")

        with self.assertRaisesRegex(
            ValueError,
            "resolved_context_bundle: missing required field 'portability_policy_resolution_id'",
        ):
            ResolvedContextBundle.from_dict(payload)

    def test_bundle_loader_rejects_noncanonical_observation_cutoff(self) -> None:
        payload = make_bundle().to_dict()

        payload_with_bool_cutoff = dict(payload)
        payload_with_bool_cutoff["observation_cutoff_utc"] = True
        with self.assertRaisesRegex(
            ValueError,
            "observation_cutoff_utc must be a timezone-aware ISO-8601 timestamp",
        ):
            ResolvedContextBundle.from_dict(payload_with_bool_cutoff)

        payload_with_naive_cutoff = dict(payload)
        payload_with_naive_cutoff["observation_cutoff_utc"] = "2026-03-01T00:00:00"
        with self.assertRaisesRegex(
            ValueError,
            "observation_cutoff_utc must be a timezone-aware ISO-8601 timestamp",
        ):
            ResolvedContextBundle.from_dict(payload_with_naive_cutoff)

    def test_execution_profile_loader_rejects_truthy_boolean_coercions(self) -> None:
        payload = make_execution_profile_release().to_dict()

        payload["promotion_grade"] = "true"
        with self.assertRaisesRegex(ValueError, "promotion_grade must be a boolean"):
            ExecutionProfileRelease.from_dict(payload)

    def test_execution_profile_loader_requires_explicit_integer_schema_version(self) -> None:
        payload = make_execution_profile_release().to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_release: missing required field 'schema_version'",
        ):
            ExecutionProfileRelease.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = False
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_release: schema_version must be an integer",
        ):
            ExecutionProfileRelease.from_dict(payload_with_bool_schema)

        payload_with_unsupported_schema = dict(payload)
        payload_with_unsupported_schema["schema_version"] = 2
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_release: schema_version must be 1",
        ):
            ExecutionProfileRelease.from_dict(payload_with_unsupported_schema)

    def test_execution_profile_loader_rejects_non_object_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_release: payload must be an object",
        ):
            ExecutionProfileRelease.from_dict([])  # type: ignore[arg-type]

    def test_execution_profile_loader_requires_serialized_sequence_presence(self) -> None:
        payload = make_execution_profile_release().to_dict()
        payload.pop("adverse_selection_penalties")

        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_release: missing required field 'adverse_selection_penalties'",
        ):
            ExecutionProfileRelease.from_dict(payload)

    def test_harness_loader_rejects_bool_seed_and_truthy_flags(self) -> None:
        payload = make_simulation_harness().to_dict()

        payload_with_bool_seed = dict(payload)
        payload_with_bool_seed["random_seeds"] = [True, 29]
        with self.assertRaisesRegex(ValueError, "random_seeds\\[\\] must be an integer"):
            HistoricalSimulationHarness.from_dict(payload_with_bool_seed)

        payload_with_truthy_flag = dict(payload)
        payload_with_truthy_flag["uses_high_level_backtest_api"] = "false"
        with self.assertRaisesRegex(
            ValueError,
            "uses_high_level_backtest_api must be a boolean",
        ):
            HistoricalSimulationHarness.from_dict(payload_with_truthy_flag)

        payload_with_truthy_custom = dict(payload)
        payload_with_truthy_custom["uses_custom_historical_engine"] = 1
        with self.assertRaisesRegex(
            ValueError,
            "uses_custom_historical_engine must be a boolean",
        ):
            HistoricalSimulationHarness.from_dict(payload_with_truthy_custom)

    def test_harness_loader_requires_explicit_integer_schema_version(self) -> None:
        payload = make_simulation_harness().to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "historical_simulation_harness: missing required field 'schema_version'",
        ):
            HistoricalSimulationHarness.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(
            ValueError,
            "historical_simulation_harness: schema_version must be an integer",
        ):
            HistoricalSimulationHarness.from_dict(payload_with_bool_schema)

        payload_with_unsupported_schema = dict(payload)
        payload_with_unsupported_schema["schema_version"] = 2
        with self.assertRaisesRegex(
            ValueError,
            "historical_simulation_harness: schema_version must be 1",
        ):
            HistoricalSimulationHarness.from_dict(payload_with_unsupported_schema)

    def test_harness_loader_rejects_non_object_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "historical_simulation_harness: payload must be an object",
        ):
            HistoricalSimulationHarness.from_dict([])  # type: ignore[arg-type]

    def test_harness_loader_requires_serialized_default_field_presence(self) -> None:
        payload = make_simulation_harness().to_dict()
        payload.pop("uses_custom_historical_engine")

        with self.assertRaisesRegex(
            ValueError,
            "historical_simulation_harness: missing required field 'uses_custom_historical_engine'",
        ):
            HistoricalSimulationHarness.from_dict(payload)

    def test_binding_loader_requires_serialized_default_field_presence(self) -> None:
        payload = make_binding(ContextBindingSurface.REPLAY_FIXTURE).to_dict()
        payload.pop("mutable_reference_reads")

        with self.assertRaisesRegex(
            ValueError,
            "context_artifact_binding: missing required field 'mutable_reference_reads'",
        ):
            ContextArtifactBindingRequest.from_dict(payload)

        payload = make_binding(ContextBindingSurface.REPLAY_FIXTURE).to_dict()
        payload.pop("mutable_execution_overrides")

        with self.assertRaisesRegex(
            ValueError,
            "context_artifact_binding: missing required field 'mutable_execution_overrides'",
        ):
            ContextArtifactBindingRequest.from_dict(payload)

    def test_binding_loader_rejects_non_object_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "context_artifact_binding: payload must be an object",
        ):
            ContextArtifactBindingRequest.from_dict([])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
