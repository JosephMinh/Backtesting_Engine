from __future__ import annotations

import unittest

from python.research.policy.guardrails import (
    evaluate_guardrails,
    load_non_negotiable_principles_bundle,
    violation_traces,
)


VALID_CONTEXT = {
    "historical_execution_kernel": "nautilus_high_level_backtesting",
    "promotable_research_uses_certified_releases": True,
    "promotable_research_uses_immutable_artifacts": True,
    "freeze_uses_resolved_context_bundle": True,
    "data_profile_release_pinned_by_digest": True,
    "promotion_uses_realistic_costs": True,
    "promotion_uses_passive_gold_benchmark": True,
    "promotion_uses_lower_touch_cash_benchmark": True,
    "promotion_has_non_notebook_evidence": True,
    "live_activation_has_deterministic_replay": True,
    "live_activation_has_paper_evidence": True,
    "live_activation_has_shadow_live_evidence": True,
    "broker_reconciliation_controls_present": True,
    "operational_state_journaled": True,
    "operational_state_replayable": True,
    "operational_state_recoverable": True,
    "intraday_broker_cross_check_enabled": True,
    "end_of_day_broker_cross_check_enabled": True,
    "lockbox_policy_enforced": True,
    "null_suite_enforced": True,
    "discovery_accounting_enforced": True,
    "operational_evidence_admissibility_enforced": True,
    "deployment_topology": "one_linux_host_or_vm",
    "canonical_metadata_store": "postgresql16",
    "immutable_artifact_store": "off_host_versioned_object_storage",
    "operational_mailboxes": "in_process",
    "canonical_shared_signal_kernel": True,
    "broker_mutation_has_durable_intent_identity": True,
    "broker_mutation_idempotent": True,
    "backup_restore_controls_present": True,
    "migration_controls_present": True,
    "clock_discipline_controls_present": True,
    "sensitive_material_controls_present": True,
    "tamper_evident_off_host_durability_present": True,
    "viability_gate_cleared_before_deep_promotable_budget": True,
    "session_readiness_packet_green": True,
    "broker_contract_conformance_green": True,
    "guardian_emergency_path_available": True,
}


def violations_for(**overrides: object) -> list[dict[str, object]]:
    context = dict(VALID_CONTEXT)
    context.update(overrides)
    return violation_traces(context)


class NonNegotiablePrinciplesContractTests(unittest.TestCase):
    def test_bundle_encodes_all_plan_principles_with_unique_reason_codes(self) -> None:
        bundle = load_non_negotiable_principles_bundle()
        principle_ids = [principle["principle_id"] for principle in bundle["principles"]]
        reason_codes = [principle["reason_code"] for principle in bundle["principles"]]

        self.assertEqual(len(bundle["principles"]), 15)
        self.assertEqual(len(principle_ids), len(set(principle_ids)))
        self.assertEqual(len(reason_codes), len(set(reason_codes)))

    def test_valid_context_passes_all_guardrails(self) -> None:
        decisions = evaluate_guardrails(VALID_CONTEXT)

        self.assertEqual(len(decisions), 15)
        self.assertFalse([decision for decision in decisions if decision["status"] == "violation"])

    def test_mutable_freeze_time_state_emits_stable_reason_code(self) -> None:
        violations = violations_for(freeze_uses_resolved_context_bundle=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-03")
        self.assertEqual(violations[0]["reason_code"], "NGP03_MUTABLE_REFERENCE_RESOLUTION_AFTER_FREEZE")
        self.assertEqual(violations[0]["violation_type"], "mutable_freeze_time_state")
        self.assertEqual(
            violations[0]["diagnostic_context"]["freeze_uses_resolved_context_bundle"],
            False,
        )

    def test_notebook_only_evidence_emits_stable_reason_code(self) -> None:
        violations = violations_for(promotion_has_non_notebook_evidence=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-05")
        self.assertEqual(violations[0]["reason_code"], "NGP05_NOTEBOOK_ONLY_PROMOTION_EVIDENCE_FORBIDDEN")
        self.assertEqual(violations[0]["violation_type"], "notebook_only_evidence")
        self.assertEqual(violations[0]["diagnostic_context"]["promotion_has_non_notebook_evidence"], False)

    def test_missing_shared_kernel_emits_stable_reason_code(self) -> None:
        violations = violations_for(canonical_shared_signal_kernel=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-10")
        self.assertEqual(violations[0]["reason_code"], "NGP10_SHARED_SIGNAL_KERNEL_REQUIRED")
        self.assertEqual(violations[0]["violation_type"], "missing_shared_signal_kernel")
        self.assertEqual(violations[0]["diagnostic_context"]["canonical_shared_signal_kernel"], False)

    def test_non_idempotent_broker_mutation_emits_stable_reason_code(self) -> None:
        violations = violations_for(broker_mutation_idempotent=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-11")
        self.assertEqual(violations[0]["reason_code"], "NGP11_BROKER_MUTATION_IDEMPOTENT_INTENT_REQUIRED")
        self.assertEqual(violations[0]["violation_type"], "non_idempotent_broker_mutation")
        self.assertEqual(violations[0]["diagnostic_context"]["broker_mutation_idempotent"], False)

    def test_unrecoverable_state_emits_stable_reason_code(self) -> None:
        violations = violations_for(operational_state_recoverable=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-07")
        self.assertEqual(violations[0]["reason_code"], "NGP07_OPERATIONAL_STATE_RECOVERABILITY_REQUIRED")
        self.assertEqual(violations[0]["violation_type"], "unrecoverable_operational_state")
        self.assertEqual(violations[0]["diagnostic_context"]["operational_state_recoverable"], False)

    def test_guardian_bypass_attempt_emits_stable_reason_code(self) -> None:
        violations = violations_for(guardian_emergency_path_available=False)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["principle_id"], "NGP-15")
        self.assertEqual(violations[0]["reason_code"], "NGP15_GUARDIAN_PATH_REQUIRED")
        self.assertEqual(violations[0]["violation_type"], "guardian_bypass_attempt")
        self.assertEqual(violations[0]["diagnostic_context"]["guardian_emergency_path_available"], False)


if __name__ == "__main__":
    unittest.main()
