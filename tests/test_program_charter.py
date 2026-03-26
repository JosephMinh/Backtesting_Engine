import unittest

from validate_program_charter import evaluate_all, evaluate_posture, evaluate_principles, load_charter


def valid_candidate():
    return {
        "research_symbol": "MGC",
        "execution_symbol": "1OZ",
        "broker": "IBKR",
        "approved_live_account_usd": 5000,
        "live_contract_count": 1,
        "active_live_bundles_per_account_product": 1,
        "host_topology": "single_linux_host_or_vm",
        "bar_based": True,
        "decision_interval_seconds": 60,
        "uses_depth_signals": False,
        "uses_queue_signals": False,
        "uses_subminute_signals": False,
        "overnight_holding": False,
        "overnight_candidate_class": None,
        "historical_simulation_engine": "nautilus_high_level_backtesting",
        "promotion_inputs_certified": True,
        "freeze_references_pinned": True,
        "promotion_uses_net_benchmarks": True,
        "promotion_evidence_source": "certified_report",
        "replay_certified": True,
        "paper_trading_evidence": True,
        "shadow_live_evidence": True,
        "broker_reconciliation_controls": True,
        "state_journaled": True,
        "state_replayable": True,
        "state_recoverable": True,
        "intraday_broker_crosscheck": True,
        "eod_broker_crosscheck": True,
        "lockbox_enforced": True,
        "null_suite_enforced": True,
        "discovery_accounting_enforced": True,
        "operational_evidence_admissibility_enforced": True,
        "host_count": 1,
        "metadata_store": "postgresql",
        "artifact_store": "off_host_object_storage",
        "mailbox_mode": "in_process",
        "has_shared_signal_kernel": True,
        "broker_mutations_journaled": True,
        "broker_mutations_idempotent": True,
        "backup_restore_ready": True,
        "migration_controls_ready": True,
        "clock_discipline_ready": True,
        "secret_handling_ready": True,  # nosec B105 - policy flag, not a credential
        "tamper_evident_durability_ready": True,
        "deep_promotable_budget_requested": False,
        "early_viability_gate_passed": False,
        "session_readiness_green": True,
        "broker_contract_conformance_green": True,
        "guardian_path_enabled": True,
    }


def reason_codes(result):
    return [check["reason_code"] for check in result["checks"] if check["reason_code"]]


class ProgramCharterTests(unittest.TestCase):
    def setUp(self):
        self.charter = load_charter()

    def test_valid_candidate_passes_all_checks(self):
        result = evaluate_all(valid_candidate(), self.charter, evaluation_id="valid-all")

        self.assertTrue(result["allowed"])
        self.assertTrue(result["posture"]["allowed"])
        self.assertTrue(result["principles"]["allowed"])

    def test_posture_rejects_wrong_execution_symbol(self):
        candidate = valid_candidate()
        candidate["execution_symbol"] = "MGC"

        result = evaluate_posture(candidate, self.charter, evaluation_id="bad-symbol")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_POSTURE_EXECUTION_SYMBOL_NOT_APPROVED", reason_codes(result))

    def test_posture_rejects_too_many_live_contracts(self):
        candidate = valid_candidate()
        candidate["live_contract_count"] = 2

        result = evaluate_posture(candidate, self.charter, evaluation_id="too-many-contracts")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_POSTURE_LIVE_CONTRACT_LIMIT_EXCEEDED", reason_codes(result))

    def test_posture_rejects_subminute_lane(self):
        candidate = valid_candidate()
        candidate["decision_interval_seconds"] = 30
        candidate["uses_subminute_signals"] = True

        result = evaluate_posture(candidate, self.charter, evaluation_id="subminute")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_POSTURE_DECISION_INTERVAL_TOO_FAST", reason_codes(result))
        self.assertIn("CHARTER_POSTURE_SUBMINUTE_STRATEGY_NOT_LIVE_ELIGIBLE", reason_codes(result))

    def test_principles_reject_mutable_freeze_context(self):
        candidate = valid_candidate()
        candidate["freeze_references_pinned"] = False

        result = evaluate_principles(candidate, self.charter, evaluation_id="mutable-freeze")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_03_MUTABLE_FREEZE_CONTEXT", reason_codes(result))

    def test_principles_reject_notebook_only_promotion_evidence(self):
        candidate = valid_candidate()
        candidate["promotion_evidence_source"] = "notebook_only"

        result = evaluate_principles(candidate, self.charter, evaluation_id="notebook-only")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_05_NOTEBOOK_ONLY_PROMOTION_EVIDENCE", reason_codes(result))

    def test_principles_reject_missing_shared_kernel(self):
        candidate = valid_candidate()
        candidate["has_shared_signal_kernel"] = False

        result = evaluate_principles(candidate, self.charter, evaluation_id="missing-kernel")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_10_SHARED_KERNEL_REQUIRED", reason_codes(result))

    def test_principles_reject_non_idempotent_broker_mutation(self):
        candidate = valid_candidate()
        candidate["broker_mutations_idempotent"] = False

        result = evaluate_principles(candidate, self.charter, evaluation_id="non-idempotent")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_11_INTENT_IDENTITY_REQUIRED", reason_codes(result))

    def test_principles_reject_missing_recoverability_controls(self):
        candidate = valid_candidate()
        candidate["backup_restore_ready"] = False

        result = evaluate_principles(candidate, self.charter, evaluation_id="recoverability")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_12_RECOVERABILITY_CONTROLS_MISSING", reason_codes(result))

    def test_principles_reject_missing_guardian_path(self):
        candidate = valid_candidate()
        candidate["guardian_path_enabled"] = False

        result = evaluate_principles(candidate, self.charter, evaluation_id="guardian")

        self.assertFalse(result["allowed"])
        self.assertIn("CHARTER_NGP_15_GUARDIAN_PATH_REQUIRED", reason_codes(result))


if __name__ == "__main__":
    unittest.main()
