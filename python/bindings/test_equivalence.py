from __future__ import annotations

import json
import unittest

from python.bindings._kernels import BINDING_TARGET_ROOT, KernelBindingError, run_gold_momentum
from python.bindings.certification import (
    DEFAULT_FIXTURE_PATH,
    _load_fixture_cases,
    _run_direct_fixture_case,
    run_equivalence_certification,
)


TEST_OUTPUT_ROOT = BINDING_TARGET_ROOT / "test-output"


class KernelBindingTests(unittest.TestCase):
    def test_run_gold_momentum_matches_fixture_expectations(self) -> None:
        case = next(
            item
            for item in _load_fixture_cases(DEFAULT_FIXTURE_PATH)
            if item.case_id == "gold_momentum_promotable"
        )
        report = run_gold_momentum(
            list(case.closes),
            lookback_bars=case.lookback_bars,
            threshold_ticks=case.threshold_ticks,
        )
        self.assertEqual("python.bindings._kernels.gold_momentum", report.entry_path)
        self.assertEqual("abi_v2", report.identity.kernel_abi_version)
        actual = [
            (decision.sequence_number, decision.disposition, decision.score_ticks)
            for decision in report.decisions
        ]
        self.assertEqual(
            [
                (4, "long", 12),
                (5, "flat", 5),
                (6, "long", 8),
                (7, "short", -7),
            ],
            actual,
        )

    def test_binding_rejects_version_mismatch(self) -> None:
        with self.assertRaises(KernelBindingError):
            run_gold_momentum(
                [100, 104, 108, 112],
                lookback_bars=3,
                threshold_ticks=6,
                expected_abi_version="abi_v999",
            )

    def test_direct_fixture_runner_emits_identity_digest(self) -> None:
        output_dir = TEST_OUTPUT_ROOT / "fixture-test"
        report = _run_direct_fixture_case(
            "gold_momentum_promotable",
            DEFAULT_FIXTURE_PATH,
            output_dir,
        )
        self.assertTrue(report.identity.canonical_digest)
        self.assertEqual("rust.bin.gold_momentum_smoke", report.entry_path)

    def test_equivalence_certification_passes_fixture_and_randomized_cases(self) -> None:
        output_dir = TEST_OUTPUT_ROOT / "certification"
        report = run_equivalence_certification(
            "gold_momentum_promotable",
            output_dir=output_dir,
            property_case_count=3,
            random_seed=23,
        )
        self.assertFalse(report.mismatches)
        self.assertIsNone(report.mismatch_bundle_path)

    def test_certification_json_report_is_serializable(self) -> None:
        output_dir = TEST_OUTPUT_ROOT / "json"
        report = run_equivalence_certification(
            "gold_momentum_research_replay",
            output_dir=output_dir,
            property_case_count=2,
            random_seed=29,
        )
        payload = report.to_dict()
        encoded = json.dumps(payload)
        self.assertIn("gold_momentum_research_replay", encoded)


if __name__ == "__main__":
    unittest.main()
