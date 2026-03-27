from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_live_bar_smoke.py"


class OpsdLiveBarSmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_accept_degrade_and_reject_paths(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        stdout = result.stdout
        self.assertIn("scenario=tradeable-pass", stdout)
        self.assertIn("status=accepted", stdout)
        self.assertIn("scenario=parity-degraded", stdout)
        self.assertIn("status=degraded", stdout)
        self.assertIn("scenario=reset-boundary-reject", stdout)
        self.assertIn("status=rejected", stdout)
        self.assertIn("artifact_root=", stdout)


if __name__ == "__main__":
    unittest.main()
