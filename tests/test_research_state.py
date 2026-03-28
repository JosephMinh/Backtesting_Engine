"""Contract tests for canonical research_run and family_decision_record state."""

from __future__ import annotations

import unittest

from shared.policy.research_state import (
    FamilyDecisionLifecycle,
    FamilyDecisionRecord,
    FamilyDecisionType,
    ResearchAdmissibilityClass,
    ResearchRunLifecycle,
    ResearchRunPurpose,
    ResearchRunRecord,
    ResearchStateStore,
    ReviewerAttestation,
    VALIDATION_ERRORS,
    audit_events_for_record,
    child_run_ids,
    family_decisions_for_family,
    record_family_decision,
    record_research_run,
    research_runs_for_family,
    transition_family_decision,
    transition_research_run,
    validate_decision_evidence_chain,
)


def sample_attestation(reviewer_id: str = "operator_self") -> ReviewerAttestation:
    return ReviewerAttestation(
        reviewer_id=reviewer_id,
        attested_controls=("budget_review", "evidence_review"),
        signed_at_utc="2026-03-26T15:00:00+00:00",
    )


def sample_research_run(
    research_run_id: str = "run-001",
    *,
    family_id: str = "gold_breakout",
    parent_run_ids: tuple[str, ...] = (),
    created_at_utc: str = "2026-03-26T15:00:00+00:00",
) -> ResearchRunRecord:
    return ResearchRunRecord(
        research_run_id=research_run_id,
        family_id=family_id,
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
        policy_bundle_hash="policy_bundle_v1",
        compatibility_matrix_version="compat_v1",
        output_artifact_digests=("artifact_a", "artifact_b"),
        admissibility_class=ResearchAdmissibilityClass.DIAGNOSTIC_ONLY,
        parent_run_ids=parent_run_ids,
        created_at_utc=created_at_utc,
    )


def sample_decision(
    decision_record_id: str = "decision-001",
    *,
    family_id: str = "gold_breakout",
    evidence_references: tuple[str, ...] = ("run-001",),
    decision_type: FamilyDecisionType = FamilyDecisionType.CONTINUE,
    next_budget_authorized_usd: float = 500.0,
    revisit_at_utc: str | None = None,
    decision_timestamp_utc: str = "2026-03-26T15:05:00+00:00",
    budget_consumed_usd: float = 250.0,
) -> FamilyDecisionRecord:
    return FamilyDecisionRecord(
        decision_record_id=decision_record_id,
        family_id=family_id,
        decision_timestamp_utc=decision_timestamp_utc,
        decision_type=decision_type,
        evidence_references=evidence_references,
        budget_consumed_usd=budget_consumed_usd,
        next_budget_authorized_usd=next_budget_authorized_usd,
        reviewer_self_attestations=(sample_attestation(),),
        reason_bundle=("evidence_quality_green", "budget_remaining_sufficient"),
        revisit_at_utc=revisit_at_utc,
    )


class TestResearchStateContract(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self):
        self.assertEqual([], VALIDATION_ERRORS)

    def test_round_trip_preserves_records_queries_and_audit(self):
        store = ResearchStateStore()
        self.assertEqual(
            record_research_run(store, sample_research_run()).reason_code,
            "RESEARCH_RUN_RECORDED",
        )
        self.assertEqual(
            record_family_decision(store, sample_decision()).reason_code,
            "FAMILY_DECISION_RECORDED",
        )

        restored = ResearchStateStore.from_dict(store.to_dict())
        self.assertEqual(len(research_runs_for_family(restored, "gold_breakout")), 1)
        self.assertEqual(len(family_decisions_for_family(restored, "gold_breakout")), 1)
        self.assertEqual(len(audit_events_for_record(restored, "research_run", "run-001")), 1)
        self.assertEqual(
            len(audit_events_for_record(restored, "family_decision_record", "decision-001")),
            1,
        )

    def test_research_run_lineage_is_queryable_and_parent_bound(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run("run-parent"))
        child_report = record_research_run(
            store,
            sample_research_run("run-child", parent_run_ids=("run-parent",)),
        )

        self.assertEqual(child_report.status, "pass")
        self.assertEqual(child_run_ids(store, "run-parent"), ("run-child",))

    def test_research_run_rejects_missing_parent_or_foreign_family_parent(self):
        store = ResearchStateStore()
        missing_parent = record_research_run(
            store,
            sample_research_run("run-missing-parent", parent_run_ids=("missing",)),
        )
        self.assertEqual(missing_parent.reason_code, "RESEARCH_RUN_PARENT_MISSING")

        record_research_run(store, sample_research_run("foreign-parent", family_id="other"))
        foreign_parent = record_research_run(
            store,
            sample_research_run(
                "run-foreign-parent",
                parent_run_ids=("foreign-parent",),
            ),
        )
        self.assertEqual(
            foreign_parent.reason_code,
            "RESEARCH_RUN_PARENT_FOREIGN_FAMILY",
        )

    def test_run_transition_allows_supersession_and_rejects_reactivation(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run())

        applied = transition_research_run(store, "run-001", ResearchRunLifecycle.SUPERSEDED)
        rejected = transition_research_run(store, "run-001", ResearchRunLifecycle.RECORDED)

        self.assertEqual(applied.reason_code, "RESEARCH_RUN_TRANSITION_APPLIED")
        self.assertEqual(rejected.reason_code, "RESEARCH_RUN_INVALID_TRANSITION")

    def test_decision_evidence_chain_rejects_dangling_or_orphaned_references(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run())
        record_research_run(store, sample_research_run("other-run", family_id="other"))

        dangling = record_family_decision(
            store,
            sample_decision("decision-missing", evidence_references=("missing-run",)),
        )
        self.assertEqual(
            dangling.reason_code,
            "FAMILY_DECISION_EVIDENCE_RUN_MISSING",
        )

        orphaned = record_family_decision(
            store,
            sample_decision(
                "decision-foreign",
                evidence_references=("other-run",),
            ),
        )
        self.assertEqual(
            orphaned.reason_code,
            "FAMILY_DECISION_EVIDENCE_FOREIGN_FAMILY",
        )

    def test_decision_budget_policy_and_revisit_rules_are_explicit(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run())

        pause_without_revisit = record_family_decision(
            store,
            sample_decision(
                "decision-pause",
                decision_type=FamilyDecisionType.PAUSE,
                revisit_at_utc=None,
            ),
        )
        terminate_with_budget = record_family_decision(
            store,
            sample_decision(
                "decision-terminate",
                decision_type=FamilyDecisionType.TERMINATE,
                next_budget_authorized_usd=10.0,
            ),
        )

        self.assertEqual(
            pause_without_revisit.reason_code,
            "FAMILY_DECISION_PAUSE_REQUIRES_REVISIT",
        )
        self.assertEqual(
            terminate_with_budget.reason_code,
            "FAMILY_DECISION_TERMINATE_REQUIRES_ZERO_BUDGET",
        )

    def test_decision_transition_and_evidence_chain_are_queryable(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run())
        record_family_decision(
            store,
            sample_decision(
                decision_type=FamilyDecisionType.PAUSE,
                revisit_at_utc="2026-03-27T15:05:00+00:00",
            ),
        )

        chain = validate_decision_evidence_chain(store, "decision-001")
        applied = transition_family_decision(
            store,
            "decision-001",
            FamilyDecisionLifecycle.EXPIRED,
        )
        rejected = transition_family_decision(
            store,
            "decision-001",
            FamilyDecisionLifecycle.ACTIVE,
        )

        self.assertEqual(chain.reason_code, "FAMILY_DECISION_EVIDENCE_CHAIN_VALID")
        self.assertEqual(applied.reason_code, "FAMILY_DECISION_TRANSITION_APPLIED")
        self.assertEqual(rejected.reason_code, "FAMILY_DECISION_INVALID_TRANSITION")
        self.assertEqual(
            len(audit_events_for_record(store, "family_decision_record", "decision-001")),
            3,
        )

    def test_persisted_timestamps_normalize_to_utc(self):
        run = sample_research_run(created_at_utc="2026-03-26T10:00:00-05:00")
        decision = sample_decision(
            decision_timestamp_utc="2026-03-26T11:05:00-04:00",
            revisit_at_utc="2026-03-27T11:05:00-04:00",
        )

        self.assertEqual("2026-03-26T15:00:00+00:00", run.created_at_utc)
        self.assertEqual("2026-03-26T15:05:00+00:00", decision.decision_timestamp_utc)
        self.assertEqual("2026-03-27T15:05:00+00:00", decision.revisit_at_utc)
        self.assertEqual(
            "2026-03-26T15:00:00+00:00",
            decision.reviewer_self_attestations[0].signed_at_utc,
        )

    def test_family_queries_are_sorted_by_domain_timestamp_not_insertion_order(self):
        store = ResearchStateStore()
        record_research_run(
            store,
            sample_research_run("run-late", created_at_utc="2026-03-26T16:00:00+00:00"),
        )
        record_research_run(
            store,
            sample_research_run(
                "run-early",
                created_at_utc="2026-03-26T14:00:00+00:00",
            ),
        )
        record_family_decision(
            store,
            sample_decision(
                "decision-late",
                evidence_references=("run-late",),
                decision_timestamp_utc="2026-03-26T16:05:00+00:00",
            ),
        )
        record_family_decision(
            store,
            sample_decision(
                "decision-early",
                evidence_references=("run-early",),
                decision_timestamp_utc="2026-03-26T14:05:00+00:00",
            ),
        )

        self.assertEqual(
            ("run-early", "run-late"),
            tuple(run.research_run_id for run in research_runs_for_family(store, "gold_breakout")),
        )
        self.assertEqual(
            ("decision-early", "decision-late"),
            tuple(
                decision.decision_record_id
                for decision in family_decisions_for_family(store, "gold_breakout")
            ),
        )

    def test_decision_rejects_negative_budget_values(self):
        store = ResearchStateStore()
        record_research_run(store, sample_research_run())

        with self.assertRaisesRegex(
            ValueError,
            "budget_consumed_usd must be finite and non-negative",
        ):
            sample_decision("decision-negative-consumed", budget_consumed_usd=-1.0)

        with self.assertRaisesRegex(
            ValueError,
            "next_budget_authorized_usd must be finite and non-negative",
        ):
            sample_decision("decision-negative-next", next_budget_authorized_usd=-1.0)


if __name__ == "__main__":
    unittest.main()
