from __future__ import annotations

import json
import subprocess  # nosec B404 - trusted repo-local smoke harness
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "rust_runtime_failure_drills_cases.json"
)
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "rust_runtime_failure_drills_smoke.py"


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class RustRuntimeFailureDrillsSmokeTest(unittest.TestCase):
    def test_fixture_case_ids_are_unique_and_mapped(self) -> None:
        fixture = load_fixture()
        cases = fixture["drill_cases"]
        case_ids = [case["case_id"] for case in cases]

        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertTrue(all(case["contract_refs"] for case in cases))
        self.assertTrue(all(case["primary_reason_key"] for case in cases))
        self.assertTrue(all(case["safe_outcome_assertion"] for case in cases))

    def test_smoke_script_runs_full_failure_drill_matrix(self) -> None:
        result = subprocess.run(  # nosec B603 - runs the trusted repo-local smoke harness
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertIn(
            "log_stage=run_case case_id=guardian_authorized_flatten_executes_with_independent_verification "
            "runner=guardian scenario=authorized-flatten",
            lines,
        )
        self.assertIn(
            "log_stage=run_case case_id=opsd_authoritative_reconciliation_blocks_next_session "
            "runner=opsd scenario=authoritative-reconciliation",
            lines,
        )

        try:
            payload = json.JSONDecoder().decode(lines[-1])
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
            self.fail(f"rust runtime failure drills smoke did not end in valid JSON: {exc}")

        artifact_root = Path(payload["artifact_root"])
        self.assertTrue(artifact_root.exists())
        self.assertEqual(
            "scripts/rust_runtime_failure_drills_smoke.py",
            payload["script_reference"],
        )

        reports = payload["drill_reports"]
        self.assertEqual(
            {case["case_id"] for case in load_fixture()["drill_cases"]},
            {report["case_id"] for report in reports},
        )
        self.assertTrue(all(report["status"] == "pass" for report in reports))
        self.assertTrue(all(Path(report["stdout_path"]).exists() for report in reports))
        self.assertTrue(all(report["retained_artifact_ids"] for report in reports))

        report_map = {report["case_id"]: report for report in reports}

        guardian_reject = report_map[
            "guardian_impaired_connectivity_rejects_and_escalates"
        ]
        self.assertEqual(
            "GUARDIAN_CONNECTIVITY_PROOF_REQUIRED",
            guardian_reject["primary_reason_code"],
        )
        self.assertEqual(
            "reject_emergency_action_until_connectivity_is_proved",
            guardian_reject["safe_outcome_assertion"],
        )

        readiness_block = report_map["opsd_session_readiness_rejects_stale_provider"]
        self.assertEqual(
            "READINESS_PROVIDER_STALE",
            readiness_block["primary_reason_code"],
        )
        self.assertEqual(
            "blocked",
            readiness_block["output_fields"]["blocked_status"],
        )
        self.assertNotIn("clock-check-001", readiness_block["retained_artifact_ids"])

        duplicate_control = report_map["opsd_duplicate_order_control_dedupes_and_withdraws"]
        self.assertEqual(
            "WITHDRAW_LIVE_OPERATOR_REQUEST",
            duplicate_control["primary_reason_code"],
        )
        self.assertEqual(
            "true",
            duplicate_control["output_fields"]["duplicate_callback_deduplicated"],
        )
        self.assertNotIn(
            "paper-gold-1:120:broker:flat:cancel_open_orders",
            duplicate_control["retained_artifact_ids"],
        )

        reconciliation_block = report_map[
            "opsd_authoritative_reconciliation_blocks_next_session"
        ]
        self.assertEqual("blocked", reconciliation_block["output_fields"]["next_session_eligibility"])
        self.assertIn(
            "authoritative-ledger-close-0001",
            reconciliation_block["retained_artifact_ids"],
        )
        self.assertNotIn(
            "statement-set-2026-03-18",
            reconciliation_block["retained_artifact_ids"],
        )


if __name__ == "__main__":
    unittest.main()
