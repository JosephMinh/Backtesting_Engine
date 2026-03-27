"""Contract tests for promotable tuning and mandatory research_run logging."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.promotable_tuning import (
    PROMOTABLE_TUNING_STAGE_ORDER,
    VALIDATION_ERRORS,
    PromotableTuningReport,
    PromotableTuningRequest,
    TuningStage,
    evaluate_promotable_tuning,
)
from shared.policy.research_state import (
    ResearchRunRecord,
    ResearchStateStore,
    audit_events_for_record,
    record_research_run,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "promotable_tuning_cases.json"
)


def load_cases() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def build_store(case: dict[str, Any]) -> ResearchStateStore:
    store = ResearchStateStore()
    for record_payload in case.get("preexisting_runs", []):
        mutation = record_research_run(
            store,
            ResearchRunRecord.from_dict(record_payload),
        )
        if mutation.status != "pass":
            raise AssertionError(
                f"failed to preload research_run {record_payload['research_run_id']}: {mutation.reason_code}"
            )
    return store


class TestPromotableTuningContract(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_stage_order_matches_plan_protocol(self) -> None:
        self.assertEqual(
            (
                TuningStage.LOCAL_SEARCH,
                TuningStage.ROBUSTNESS_PERTURBATION,
                TuningStage.CANDIDATE_FREEZE,
            ),
            PROMOTABLE_TUNING_STAGE_ORDER,
        )

    def test_fixture_cases(self) -> None:
        payload = load_cases()
        for case in payload["cases"]:
            with self.subTest(case_id=case["case_id"]):
                store = build_store(case)
                request = PromotableTuningRequest.from_dict(case["request"])
                report = evaluate_promotable_tuning(store, request)

                self.assertEqual(case["expected"]["status"], report.status.value)
                self.assertEqual(
                    case["expected"]["continuation_approved"],
                    report.continuation_approved,
                )
                self.assertEqual(
                    case["expected"]["shared_kernel_gate_required"],
                    report.shared_kernel_gate_required,
                )
                self.assertEqual(
                    case["expected"]["shared_kernel_gate_passed"],
                    report.shared_kernel_gate_passed,
                )
                self.assertEqual(
                    case["expected"]["research_run_recorded"],
                    report.research_run_recorded,
                )
                self.assertEqual(case["expected"]["replayable"], report.replayable)
                self.assertEqual(
                    tuple(case["expected"]["pruned_trial_ids"]),
                    report.pruned_trial_ids,
                )
                self.assertEqual(
                    case["expected"]["finalist_trial_id"],
                    report.finalist_trial_id,
                )
                self.assertEqual(
                    tuple(case["expected"]["stored_run_ids"]),
                    tuple(store.research_runs),
                )
                self.assertEqual(
                    tuple(case["expected"]["failing_reason_codes"]),
                    tuple(
                        result.reason_code
                        for result in report.check_results
                        if not result.passed
                    ),
                )

    def test_rejected_batch_still_records_research_run_and_audit(self) -> None:
        case = load_cases()["cases"][0]
        store = build_store(case)
        request = PromotableTuningRequest.from_dict(case["request"])

        report = evaluate_promotable_tuning(store, request)

        self.assertEqual("pass", report.status.value)
        self.assertEqual("reject", report.batch_outcome.value)
        self.assertTrue(report.research_run_recorded)
        self.assertIn(request.research_run.research_run_id, store.research_runs)
        self.assertEqual(
            "RESEARCH_RUN_RECORDED",
            report.research_run_report.reason_code,
        )
        self.assertEqual(
            1,
            len(
                audit_events_for_record(
                    store,
                    "research_run",
                    request.research_run.research_run_id,
                )
            ),
        )

    def test_report_round_trip_preserves_mutation_report(self) -> None:
        case = load_cases()["cases"][-1]
        store = build_store(case)
        report = evaluate_promotable_tuning(
            store,
            PromotableTuningRequest.from_dict(case["request"]),
        )

        restored = PromotableTuningReport.from_json(report.to_json())

        self.assertEqual("candidate_freeze", restored.stage.value)
        self.assertEqual("trial-004-a", restored.finalist_trial_id)
        self.assertEqual("RESEARCH_RUN_RECORDED", restored.research_run_report.reason_code)
        self.assertEqual(9, len(restored.check_results))


if __name__ == "__main__":
    unittest.main()
