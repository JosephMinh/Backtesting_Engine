from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_risk_smoke.py"


class OpsdRiskSmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_all_runtime_eligibility_states(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        stdout = result.stdout
        self.assertIn("scenario=green-tradeable-pass", stdout)
        self.assertIn("status=eligible", stdout)
        self.assertIn("scenario=degraded-data-restrict", stdout)
        self.assertIn("status=restricted", stdout)
        self.assertIn("scenario=daily-loss-exit-only", stdout)
        self.assertIn("status=exit_only", stdout)
        self.assertIn("scenario=drawdown-flatten", stdout)
        self.assertIn("status=flatten", stdout)
        self.assertIn("scenario=margin-halt", stdout)
        self.assertIn("status=halted", stdout)
        self.assertIn("artifact_root=", stdout)

        artifact_root_line = next(
            line for line in stdout.splitlines() if line.startswith("artifact_root=")
        )
        artifact_root = Path(artifact_root_line.split("=", 1)[1].strip())
        for scenario in (
            "green-tradeable-pass",
            "degraded-data-restrict",
            "daily-loss-exit-only",
            "drawdown-flatten",
            "margin-halt",
        ):
            scenario_dir = artifact_root / scenario
            self.assertTrue((scenario_dir / "runtime_risk_request.txt").exists())
            self.assertTrue((scenario_dir / "runtime_risk_report.txt").exists())


if __name__ == "__main__":
    unittest.main()
