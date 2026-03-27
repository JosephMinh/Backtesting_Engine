import unittest

from shared.policy.verification_contract import (
    ArtifactRequirement,
    CORE_EXPLAINABILITY,
    EXPECTED_CROSS_PLANE_IDENTIFIER_COVERAGE,
    FixtureSource,
    GATE_DECISION_ARTIFACTS,
    GOLDEN_LOG_FIXTURES,
    PHASE_GATES,
    REQUIRED_REDACTION_FIELDS,
    REQUIRED_CROSS_PLANE_IDENTIFIERS,
    STRUCTURED_LOGGING_CONTRACT,
    VERIFICATION_PROFILES,
    VALIDATION_ERRORS,
    TracePlane,
    VerificationClass,
    cross_plane_identifier_coverage,
    profiles_by_phase,
    validate_log_fixture,
)


class VerificationContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_every_phase_gate_has_coverage(self) -> None:
        grouped = profiles_by_phase()
        for phase_id, phase_name in PHASE_GATES.items():
            with self.subTest(phase_id=phase_id, phase_name=phase_name):
                self.assertTrue(grouped[phase_id], "phase gate is missing verification coverage")

    def test_every_profile_declares_all_three_verification_lanes(self) -> None:
        for profile in VERIFICATION_PROFILES:
            with self.subTest(surface_id=profile.surface_id):
                self.assertTrue(profile.local_checks, "local checks are required")
                self.assertTrue(profile.golden_path, "golden-path checks are required")
                self.assertTrue(profile.failure_path, "failure-path checks are required")

    def test_every_profile_requires_core_gate_artifacts(self) -> None:
        for profile in VERIFICATION_PROFILES:
            with self.subTest(surface_id=profile.surface_id):
                self.assertTrue(
                    set(GATE_DECISION_ARTIFACTS).issubset(profile.retained_artifacts),
                    "missing retained artifacts for gate decisions",
                )
                self.assertTrue(
                    set(CORE_EXPLAINABILITY).issubset(profile.explainability),
                    "missing explainability requirements",
                )

    def test_fixture_contracts_require_reproducibility_controls(self) -> None:
        for profile in VERIFICATION_PROFILES:
            fixture_contract = profile.fixture_contract
            with self.subTest(surface_id=profile.surface_id):
                self.assertTrue(fixture_contract.sources, "fixture sources must be declared")
                self.assertTrue(fixture_contract.provenance_required)
                self.assertTrue(fixture_contract.deterministic_seed_required)
                self.assertTrue(fixture_contract.deterministic_clock_required)

    def test_bead_23_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.2.3" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("canonical_metadata_and_dense_telemetry", matching[0].surface_id)
        self.assertIn("phase_1", matching[0].phase_gates)

    def test_bead_23_profile_declares_required_workflow_and_artifact_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "canonical_metadata_and_dense_telemetry"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.REPRODUCIBILITY_STAMPS, profile.retained_artifacts)

    def test_bead_25_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.2.5" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("time_discipline_and_session_clocks", matching[0].surface_id)
        self.assertIn("phase_0", matching[0].phase_gates)

    def test_bead_25_profile_declares_clock_specific_workflow_and_fixture_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "time_discipline_and_session_clocks"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.REPLAY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.REPRODUCIBILITY_STAMPS, profile.retained_artifacts)

    def test_bead_31_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.1" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertIn("phase_1", matching[0].phase_gates)

    def test_bead_31_profile_declares_reference_pipeline_workflow_and_fixture_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "data_reference_and_release_pipeline"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.REPRODUCIBILITY_STAMPS, profile.retained_artifacts)

    def test_bead_34_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.4" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertEqual(("phase_1", "phase_2"), matching[0].phase_gates)

    def test_bead_38_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.8" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertEqual(("phase_1", "phase_2"), matching[0].phase_gates)

    def test_bead_39_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.9" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertEqual(("phase_1", "phase_2"), matching[0].phase_gates)

    def test_bead_39_profile_preserves_failure_and_release_pipeline_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "data_reference_and_release_pipeline"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(VerificationClass.FAILURE_PATH, profile.failure_path)
        self.assertIn(ArtifactRequirement.OPERATOR_REASON_BUNDLES, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS, profile.retained_artifacts)

    def test_bead_36_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.6" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("candidate_and_activation_packets", matching[0].surface_id)
        self.assertEqual(("phase_6", "phase_7"), matching[0].phase_gates)

    def test_bead_36_profile_declares_packet_specific_workflow_and_fixture_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "candidate_and_activation_packets"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.REPLAY_CERTIFICATION,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.DECISION_TRACES, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)

    def test_bead_310_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.10" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertEqual(("phase_1", "phase_2"), matching[0].phase_gates)

    def test_bead_310_profile_keeps_fixture_and_explainability_requirements(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "data_reference_and_release_pipeline"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(VerificationClass.PARITY_CERTIFICATION, profile.golden_path)
        self.assertIn(ArtifactRequirement.DECISION_TRACES, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)

    def test_bead_311_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.3.11" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("data_reference_and_release_pipeline", matching[0].surface_id)
        self.assertEqual(("phase_1", "phase_2"), matching[0].phase_gates)

    def test_bead_93_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.9.3" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "phase_2_validation_and_release_pipeline_gate",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_2",), matching[0].phase_gates)

    def test_bead_93_profile_declares_phase_2_release_gate_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "phase_2_validation_and_release_pipeline_gate"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_phase_2_gate_supports_release_and_lifecycle_surfaces(self) -> None:
        phase_two_surface_ids = {
            profile.surface_id for profile in profiles_by_phase()["phase_2"]
        }
        self.assertTrue(
            {
                "phase_2_validation_and_release_pipeline_gate",
                "data_reference_and_release_pipeline",
                "lifecycle_state_machines_and_compatibility_domains",
            }.issubset(phase_two_surface_ids)
        )

    def test_bead_79_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.7.9" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "operational_runtime_supervision_and_state_ownership",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_2_5", "phase_7"), matching[0].phase_gates)

    def test_bead_79_profile_declares_runtime_supervision_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id
            == "operational_runtime_supervision_and_state_ownership"
        )
        self.assertEqual(
            (
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.CORRELATION_IDS, profile.retained_artifacts)

    def test_phase_25_gate_supports_vertical_slice_and_runtime_boundaries(self) -> None:
        phase_two_five_surface_ids = {
            profile.surface_id for profile in profiles_by_phase()["phase_2_5"]
        }
        self.assertTrue(
            {
                "execution_lane_vertical_slice",
                "operational_runtime_supervision_and_state_ownership",
            }.issubset(phase_two_five_surface_ids)
        )

    def test_bead_41_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.4.1" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("simulation_and_execution_profiles", matching[0].surface_id)
        self.assertEqual(("phase_3",), matching[0].phase_gates)

    def test_bead_41_profile_requires_certified_and_session_fixture_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "simulation_and_execution_profiles"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.CORRELATION_IDS, profile.retained_artifacts)

    def test_bead_42_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.4.2" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("simulation_and_execution_profiles", matching[0].surface_id)
        self.assertEqual(("phase_3",), matching[0].phase_gates)

    def test_bead_44_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.4.4" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("simulation_and_execution_profiles", matching[0].surface_id)
        self.assertEqual(("phase_3",), matching[0].phase_gates)

    def test_bead_91_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.9.1" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("phase_0_foundation_and_qa_gate", matching[0].surface_id)
        self.assertEqual(("phase_0",), matching[0].phase_gates)

    def test_bead_91_profile_declares_foundation_gate_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "phase_0_foundation_and_qa_gate"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.ARTIFACT_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_92_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.9.2" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("phase_1_raw_archive_and_reference_gate", matching[0].surface_id)
        self.assertEqual(("phase_1",), matching[0].phase_gates)

    def test_bead_92_profile_declares_phase_1_gate_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "phase_1_raw_archive_and_reference_gate"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.ARTIFACT_MANIFESTS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS, profile.retained_artifacts)

    def test_bead_46_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.4.6" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("fast_screening_governance", matching[0].surface_id)
        self.assertEqual(("phase_3",), matching[0].phase_gates)

    def test_bead_46_profile_declares_fast_screening_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "fast_screening_governance"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.ARTIFACT_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_51_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.1" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "strategy_contracts_and_canonical_signal_kernel",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_5", "phase_6"), matching[0].phase_gates)

    def test_bead_51_profile_declares_contract_and_equivalence_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "strategy_contracts_and_canonical_signal_kernel"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.PARITY_CERTIFICATION,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.REPRODUCIBILITY_STAMPS,
            profile.retained_artifacts,
        )

    def test_bead_52_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.2" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "baseline_risk_controls_and_waiver_defaults",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_5", "phase_7"), matching[0].phase_gates)

    def test_bead_52_profile_declares_risk_control_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "baseline_risk_controls_and_waiver_defaults"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.REPRODUCIBILITY_STAMPS,
            profile.retained_artifacts,
        )

    def test_bead_53_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.3" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "operating_envelope_and_session_conditioned_risk_profiles",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_5", "phase_7"), matching[0].phase_gates)

    def test_bead_53_profile_declares_runtime_ready_operating_envelope_workflow(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "operating_envelope_and_session_conditioned_risk_profiles"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.REPRODUCIBILITY_STAMPS,
            profile.retained_artifacts,
        )

    def test_bead_54_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.4" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "actual_execution_contract_account_fit",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_5", "phase_7"), matching[0].phase_gates)

    def test_bead_54_profile_declares_account_fit_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "actual_execution_contract_account_fit"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.REPRODUCIBILITY_STAMPS,
            profile.retained_artifacts,
        )

    def test_bead_55_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.5" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("fully_loaded_economics", matching[0].surface_id)
        self.assertEqual(("phase_5",), matching[0].phase_gates)

    def test_bead_55_profile_declares_layered_cost_coverage(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "fully_loaded_economics"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_56_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.6" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "absolute_dollar_viability_and_benchmark_gate",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_5",), matching[0].phase_gates)

    def test_bead_56_profile_declares_economic_gate_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "absolute_dollar_viability_and_benchmark_gate"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_65_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.6.5" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("research_governance_and_selection", matching[0].surface_id)
        self.assertEqual(("phase_4", "phase_5"), matching[0].phase_gates)

    def test_bead_65_uses_research_governance_verification_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "research_governance_and_selection"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(
            ArtifactRequirement.STRUCTURED_LOGS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_57_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.5.7" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("strict_overnight_candidate_class", matching[0].surface_id)
        self.assertEqual(("phase_5", "phase_7"), matching[0].phase_gates)

    def test_bead_57_profile_declares_overnight_operational_rehearsal_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "strict_overnight_candidate_class"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(
            ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
            profile.retained_artifacts,
        )
        self.assertIn(
            ArtifactRequirement.OPERATOR_REASON_BUNDLES,
            profile.retained_artifacts,
        )

    def test_bead_82_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.8.2" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "lifecycle_state_machines_and_compatibility_domains",
            matching[0].surface_id,
        )
        self.assertEqual(
            ("phase_0", "phase_2", "phase_6", "phase_7", "phase_8"),
            matching[0].phase_gates,
        )

    def test_bead_82_profile_declares_lifecycle_and_compatibility_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "lifecycle_state_machines_and_compatibility_domains"
        )
        self.assertEqual(
            (
                FixtureSource.PLAN_SEEDED_FIXTURE,
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual((VerificationClass.GOLDEN_PATH,), profile.golden_path)
        self.assertEqual(
            (
                VerificationClass.FAILURE_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.failure_path,
        )
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.CORRELATION_IDS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.FIXTURE_MANIFESTS, profile.retained_artifacts)

    def test_bead_116_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.11.6" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("structured_logging_and_artifact_capture", matching[0].surface_id)
        self.assertEqual(
            ("phase_1", "phase_3", "phase_4", "phase_6", "phase_7", "phase_8"),
            matching[0].phase_gates,
        )

    def test_bead_116_profile_declares_cross_plane_logging_lanes(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "structured_logging_and_artifact_capture"
        )
        self.assertEqual(
            (
                FixtureSource.CERTIFIED_RELEASE,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.REPLAY_CERTIFICATION,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertIn(ArtifactRequirement.STRUCTURED_LOGS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.CORRELATION_IDS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.ARTIFACT_MANIFESTS, profile.retained_artifacts)

    def test_logging_contract_covers_all_required_cross_plane_identifiers(self) -> None:
        covered = {
            identifier
            for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts
            for identifier in contract.required_identifiers
        }
        self.assertEqual(set(REQUIRED_CROSS_PLANE_IDENTIFIERS), covered)

    def test_logging_contract_declares_all_planes(self) -> None:
        self.assertEqual(
            {
                TracePlane.RESEARCH,
                TracePlane.RELEASE,
                TracePlane.POLICY,
                TracePlane.CERTIFICATION,
                TracePlane.RUNTIME,
                TracePlane.RECOVERY,
            },
            {contract.plane for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts},
        )

    def test_logging_contract_manifest_requires_hashes_and_redaction_fields(self) -> None:
        manifest = STRUCTURED_LOGGING_CONTRACT.artifact_manifest
        self.assertIn("redaction_policy", manifest.required_fields)
        self.assertIn("contains_secrets", manifest.required_fields)
        self.assertIn("sha256", manifest.required_artifact_fields)
        self.assertIn("relative_path", manifest.required_artifact_fields)

    def test_golden_log_fixtures_validate_against_the_contract(self) -> None:
        for plane, payload in GOLDEN_LOG_FIXTURES.items():
            with self.subTest(plane=plane.value):
                self.assertEqual([], validate_log_fixture(plane, payload))

    def test_cross_plane_story_preserves_expected_identifier_coverage(self) -> None:
        self.assertEqual(
            EXPECTED_CROSS_PLANE_IDENTIFIER_COVERAGE,
            cross_plane_identifier_coverage(),
        )

    def test_cross_plane_story_covers_secret_boundary_fields(self) -> None:
        observed_redactions = {
            field_name
            for payload in GOLDEN_LOG_FIXTURES.values()
            for collection_name in ("redacted_fields", "omitted_fields")
            for field_name in payload[collection_name]
        }
        self.assertTrue(set(REQUIRED_REDACTION_FIELDS).issubset(observed_redactions))

    def test_runtime_and_recovery_fixtures_share_reconstruction_ids(self) -> None:
        runtime_references = GOLDEN_LOG_FIXTURES[TracePlane.RUNTIME]["referenced_ids"]
        recovery_references = GOLDEN_LOG_FIXTURES[TracePlane.RECOVERY]["referenced_ids"]
        for identifier in (
            "promotion_packet_id",
            "session_readiness_packet_id",
            "deployment_instance_id",
            "order_intent_id",
        ):
            with self.subTest(identifier=identifier):
                self.assertEqual(
                    runtime_references[identifier],
                    recovery_references[identifier],
                )

    def test_bead_84_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.8.4" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual(
            "operator_observability_and_response_targets",
            matching[0].surface_id,
        )
        self.assertEqual(("phase_7", "phase_8"), matching[0].phase_gates)

    def test_bead_84_profile_declares_observability_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "operator_observability_and_response_targets"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual((VerificationClass.FAILURE_PATH,), profile.failure_path)
        self.assertEqual(
            (
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.OPERATOR_REASON_BUNDLES, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.ARTIFACT_MANIFESTS, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS, profile.retained_artifacts)

    def test_bead_81_is_mapped_into_the_shared_verification_plan(self) -> None:
        matching = [
            profile
            for profile in VERIFICATION_PROFILES
            if "backtesting_engine-ltc.8.1" in profile.related_beads
        ]
        self.assertEqual(1, len(matching))
        self.assertEqual("live_readiness_and_resilience", matching[0].surface_id)
        self.assertEqual(("phase_8",), matching[0].phase_gates)

    def test_bead_81_profile_declares_live_readiness_workflow_and_fixtures(self) -> None:
        profile = next(
            profile
            for profile in VERIFICATION_PROFILES
            if profile.surface_id == "live_readiness_and_resilience"
        )
        self.assertEqual(
            (
                VerificationClass.UNIT,
                VerificationClass.CONTRACT,
                VerificationClass.PROPERTY,
            ),
            profile.local_checks,
        )
        self.assertEqual(
            (
                VerificationClass.GOLDEN_PATH,
                VerificationClass.OPERATIONAL_REHEARSAL,
            ),
            profile.golden_path,
        )
        self.assertEqual(
            (
                VerificationClass.FAILURE_PATH,
                VerificationClass.REPLAY_CERTIFICATION,
            ),
            profile.failure_path,
        )
        self.assertEqual(
            (
                FixtureSource.BROKER_SESSION_RECORDING,
                FixtureSource.GOLDEN_SESSION,
                FixtureSource.SYNTHETIC_FAILURE_CASE,
            ),
            profile.fixture_contract.sources,
        )
        self.assertIn(ArtifactRequirement.DECISION_TRACES, profile.retained_artifacts)
        self.assertIn(ArtifactRequirement.OPERATOR_REASON_BUNDLES, profile.retained_artifacts)


if __name__ == "__main__":
    unittest.main()
