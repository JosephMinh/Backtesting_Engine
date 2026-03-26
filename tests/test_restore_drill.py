from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from infra import restore_drill as RESTORE_DRILL
from shared.policy.verification_contract import TracePlane, validate_log_fixture

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "infra" / "backup_restore_baseline.json"
MANIFEST_PATH = ROOT / "shared" / "fixtures" / "restore_drill" / "backup_manifest.json"
FIXTURE_ROOT = ROOT / "shared" / "fixtures" / "restore_drill" / "restored_ok"


class RestoreDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = RESTORE_DRILL.load_json(BASELINE_PATH)
        self.manifest = RESTORE_DRILL.load_json(MANIFEST_PATH)

    def _evaluate(self, mutate=None, manifest_override=None):
        with tempfile.TemporaryDirectory() as tempdir:
            restored_root = Path(tempdir) / "restored"
            shutil.copytree(FIXTURE_ROOT, restored_root)
            if mutate is not None:
                mutate(restored_root)
            manifest = dict(self.manifest)
            if manifest_override:
                manifest.update(manifest_override)
            return RESTORE_DRILL.evaluate_restore_drill(self.baseline, manifest, restored_root)

    def test_matching_restore_passes_and_reports_metrics(self) -> None:
        result = self._evaluate()

        self.assertEqual("pass", result["status"])
        self.assertEqual(["RESTORE_DRILL_OK"], result["reason_codes"])
        self.assertTrue(result["recovery_point_verified"])
        self.assertEqual(2, result["metrics"]["expected_file_count"])
        self.assertEqual(2, result["metrics"]["actual_file_count"])
        self.assertEqual("recovery", result["plane"])
        self.assertEqual("RESTORE_DRILL_OK", result["reason_code"])
        self.assertEqual(
            "promotion_packet_gold_live_v1",
            result["referenced_ids"]["promotion_packet_id"],
        )
        self.assertEqual(self.manifest["manifest_id"], result["artifact_manifest"]["manifest_id"])
        self.assertEqual([], validate_log_fixture(TracePlane.RECOVERY, result))

    def test_hash_mismatch_is_reported(self) -> None:
        def mutate(restored_root: Path) -> None:
            (restored_root / "evidence" / "run-001.json").write_text(
                "{\"run_id\":\"run-001\",\"status\":\"tampered\"}\n",
                encoding="utf-8",
            )

        result = self._evaluate(mutate=mutate)

        self.assertEqual("fail", result["status"])
        self.assertIn("RESTORE_DRILL_HASH_MISMATCH", result["reason_codes"])
        self.assertIn("evidence/run-001.json", result["hash_mismatches"])

    def test_extra_file_is_reported(self) -> None:
        def mutate(restored_root: Path) -> None:
            extra = restored_root / "evidence" / "unexpected.txt"
            extra.write_text("unexpected\n", encoding="utf-8")

        result = self._evaluate(mutate=mutate)

        self.assertEqual("fail", result["status"])
        self.assertIn("RESTORE_DRILL_EXTRA_FILES_PRESENT", result["reason_codes"])
        self.assertIn("evidence/unexpected.txt", result["extra_files"])

    def test_rpo_violation_is_reported(self) -> None:
        result = self._evaluate(
            manifest_override={
                "backup_completed_at": "2026-03-26T09:00:00Z",
                "restore_started_at": "2026-03-26T12:10:00Z",
                "restore_completed_at": "2026-03-26T12:25:00Z",
            }
        )

        self.assertEqual("fail", result["status"])
        self.assertIn("RESTORE_DRILL_RPO_EXCEEDED", result["reason_codes"])
        self.assertFalse(result["recovery_point_verified"])


if __name__ == "__main__":
    unittest.main()
