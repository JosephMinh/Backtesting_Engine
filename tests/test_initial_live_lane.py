from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python" / "research"))

charter = importlib.import_module("charter")
evaluate_initial_live_lane = charter.evaluate_initial_live_lane
load_fixture_cases = charter.load_fixture_cases
load_initial_live_lane_policy = charter.load_initial_live_lane_policy


class InitialLiveLanePolicyTests(unittest.TestCase):
    def test_fixture_cases_match_expected_outcomes(self) -> None:
        policy = load_initial_live_lane_policy(REPO_ROOT)
        cases = load_fixture_cases(REPO_ROOT)["cases"]

        for case in cases:
            with self.subTest(case=case["id"]):
                result = evaluate_initial_live_lane(
                    case["candidate"],
                    policy=policy,
                    trace_id=case["id"],
                )
                failure_codes = [
                    trace["failure_reason_code"]
                    for trace in result["decision_traces"]
                    if not trace["passed"]
                ]

                self.assertEqual(result["approved"], case["expected_approved"])
                self.assertEqual(failure_codes, case["expected_failure_reason_codes"])
                self.assertEqual(result["trace_id"], case["id"])

    def test_decision_traces_are_structured_and_complete(self) -> None:
        policy = load_initial_live_lane_policy(REPO_ROOT)
        baseline = load_fixture_cases(REPO_ROOT)["cases"][0]["candidate"]
        result = evaluate_initial_live_lane(baseline, policy=policy, trace_id="trace-shape")

        self.assertTrue(result["approved"])
        self.assertEqual(result["bundle_id"], "charter.initial_live_lane.v1")
        self.assertGreater(len(result["decision_traces"]), 0)

        for trace in result["decision_traces"]:
            self.assertIn("rule_id", trace)
            self.assertIn("rule_code", trace)
            self.assertIn("field", trace)
            self.assertIn("operator", trace)
            self.assertIn("passed", trace)
            self.assertIn("failure_reason_code", trace)
            self.assertIn("condition_active", trace)


if __name__ == "__main__":
    unittest.main()
