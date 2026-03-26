import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from python.research.guardrails.non_negotiable_principles import (  # noqa: E402
    build_fixture_context,
    evaluate_guardrails,
    load_charter_index,
    load_fixture_cases,
    load_policy_bundle,
)


class NonNegotiablePrinciplesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy_bundle = load_policy_bundle()
        self.charter_index = load_charter_index()
        self.fixture_cases = load_fixture_cases()

    def test_charter_index_matches_canonical_bundle(self) -> None:
        self.assertEqual(len(self.policy_bundle["principles"]), 15)
        self.assertEqual(len(self.charter_index["principles"]), 15)

        canonical_pairs = [
            (principle["principle_id"], principle["reason_code"])
            for principle in self.policy_bundle["principles"]
        ]
        charter_pairs = [
            (principle["principle_id"], principle["reason_code"])
            for principle in self.charter_index["principles"]
        ]
        self.assertEqual(canonical_pairs, charter_pairs)
        self.assertEqual(
            self.charter_index["canonical_bundle_path"],
            "shared/policy/non_negotiable_principles.json",
        )

    def test_baseline_case_passes_cleanly(self) -> None:
        baseline_context = build_fixture_context(
            self.fixture_cases["valid_case"]["name"]
        )
        result = evaluate_guardrails(baseline_context, self.policy_bundle)

        self.assertTrue(result["passed"])
        self.assertEqual(result["failed_reason_codes"], [])
        for check in result["checks"]:
            self.assertTrue(check["passed"])
            self.assertIsNone(check["violation_type"])
            self.assertEqual(check["failures"], [])

    def test_each_violation_case_emits_expected_reason_code_and_trace(self) -> None:
        for case in self.fixture_cases["violation_cases"]:
            with self.subTest(case=case["name"]):
                context = build_fixture_context(case["name"])
                result = evaluate_guardrails(context, self.policy_bundle)

                self.assertFalse(result["passed"])
                self.assertEqual(result["failed_reason_codes"], [case["expected_reason_code"]])

                failed_checks = [check for check in result["checks"] if not check["passed"]]
                self.assertEqual(len(failed_checks), 1)

                failed_check = failed_checks[0]
                self.assertEqual(failed_check["principle_id"], case["principle_id"])
                self.assertEqual(
                    failed_check["reason_code"], case["expected_reason_code"]
                )
                self.assertIsNotNone(failed_check["violation_type"])
                self.assertTrue(failed_check["diagnostic_context"])
                self.assertTrue(failed_check["failures"])


if __name__ == "__main__":
    unittest.main()
