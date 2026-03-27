from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_strategy_health_smoke.py"


class OpsdStrategyHealthSmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_strategy_health_restriction_states(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        stdout = result.stdout
        self.assertIn("scenario=behavior-drift-restrict", stdout)
        self.assertIn("reason_code=STRATEGY_HEALTH_BEHAVIOR_DRIFT_RESTRICT", stdout)
        self.assertIn("scenario=behavior-drift-exit-only", stdout)
        self.assertIn("status=exit_only", stdout)
        self.assertIn("scenario=data-quality-halt", stdout)
        self.assertIn("status=halted", stdout)
        self.assertIn("scenario=operating-envelope-fit-restrict", stdout)
        self.assertIn("scenario=operating-envelope-fit-flatten", stdout)
        self.assertIn("require_flatten=true", stdout)
        self.assertIn("scenario=recalibration-required-restrict", stdout)
        self.assertIn("artifact_root=", stdout)

        artifact_root_line = next(
            line for line in stdout.splitlines() if line.startswith("artifact_root=")
        )
        artifact_root = Path(artifact_root_line.split("=", 1)[1].strip())
        for scenario in (
            "behavior-drift-restrict",
            "behavior-drift-exit-only",
            "data-quality-halt",
            "operating-envelope-fit-restrict",
            "operating-envelope-fit-flatten",
            "recalibration-required-restrict",
        ):
            scenario_dir = artifact_root / scenario
            self.assertTrue((scenario_dir / "runtime_risk_request.txt").exists())
            self.assertTrue((scenario_dir / "runtime_risk_report.txt").exists())


if __name__ == "__main__":
    unittest.main()
