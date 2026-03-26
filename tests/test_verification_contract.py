import unittest

from shared.policy.verification_contract import (
    ArtifactRequirement,
    CORE_EXPLAINABILITY,
    FixtureSource,
    GATE_DECISION_ARTIFACTS,
    PHASE_GATES,
    VERIFICATION_PROFILES,
    VALIDATION_ERRORS,
    VerificationClass,
    profiles_by_phase,
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


if __name__ == "__main__":
    unittest.main()
