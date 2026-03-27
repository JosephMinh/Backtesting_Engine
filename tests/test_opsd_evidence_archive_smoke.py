from __future__ import annotations

import json
import subprocess  # nosec B404 - test harness intentionally invokes local scripts
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_evidence_archive_smoke.py"


class OpsdEvidenceArchiveSmokeTest(unittest.TestCase):
    def test_smoke_script_seals_and_queries_operational_evidence(self) -> None:
        result = subprocess.run(  # nosec B603 - runs the local smoke script under test
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertIn("log_stage=compile_binary", lines)
        self.assertIn("log_stage=query query_id=by_drill_id", lines)
        try:
            payload = json.JSONDecoder().decode(lines[-1])
        except json.JSONDecodeError as exc:  # pragma: no cover - assertion path
            self.fail(f"smoke output did not end in valid JSON: {exc}")
        self.assertEqual(
            [
                "paper_bundle_001",
                "shadow_bundle_001",
                "replay_bundle_001",
                "broker_session_bundle_001",
                "recovery_bundle_001",
                "parity_bundle_001",
                "drift_bundle_001",
                "post_session_bundle_001",
            ],
            payload["sealed_evidence_ids"],
        )
        self.assertEqual(
            ["drift_bundle_001"],
            payload["query_results"]["by_artifact_class_drift"]["matched_evidence_ids"],
        )
        self.assertEqual(
            ["recovery_bundle_001"],
            payload["query_results"]["by_drill_id"]["matched_evidence_ids"],
        )
        self.assertEqual(
            8,
            payload["query_results"]["by_deployment_and_session"]["match_count"],
        )
        self.assertTrue(Path(payload["archive_root"]).exists())


if __name__ == "__main__":
    unittest.main()
