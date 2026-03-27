from __future__ import annotations

import json
import subprocess  # nosec B404 - trusted repo-local smoke script
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_recovery_smoke.py"


class OpsdRecoverySmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_recovery_and_shutdown_paths(self) -> None:
        result = subprocess.run(  # nosec B603 - runs the local smoke script under test
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertIn("log_stage=compile_binary", lines)
        self.assertIn("log_stage=run_scenario scenario=ambiguous-journal-halt", lines)
        try:
            payload = json.JSONDecoder().decode(lines[-1])
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
            self.fail(f"opsd recovery smoke did not end in valid JSON: {exc}")

        artifact_root = Path(payload["artifact_root"])
        self.assertTrue(artifact_root.exists())

        green = payload["scenarios"]["green-verified-restart"]
        self.assertEqual("restart_ready", green["shutdown_status"])
        self.assertEqual("resume_tradeable", green["recovery_status"])
        self.assertEqual("true", green["allow_new_entries"])
        self.assertEqual("snapshot_seed", green["warmup_source"])

        holding = payload["scenarios"]["restart-while-holding-exit-only"]
        self.assertEqual("resume_exit_only", holding["recovery_status"])
        self.assertEqual("true", holding["exit_only"])

        ambiguous = payload["scenarios"]["ambiguous-journal-halt"]
        self.assertEqual("halted", ambiguous["recovery_status"])
        self.assertEqual("RECOVERY_AMBIGUITY_JOURNAL_GAP", ambiguous["recovery_reason_code"])

        report_path = artifact_root / "green-verified-restart" / "recovery_report.txt"
        barrier_path = (
            artifact_root / "green-verified-restart" / "shutdown_barrier_artifact.txt"
        )
        self.assertTrue(report_path.exists())
        self.assertTrue(barrier_path.exists())
        self.assertIn("status=resume_tradeable", report_path.read_text(encoding="utf-8"))
        self.assertIn("status=restart_ready", barrier_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
