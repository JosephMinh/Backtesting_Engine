from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "target"
TMPDIR = TARGET_DIR / "tmp"


def run_scenario(scenario: str, artifact_dir: Path) -> str:
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(TARGET_DIR)
    env["TMPDIR"] = str(TMPDIR)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "cargo",
            "run",
            "-p",
            "backtesting-engine-opsd",
            "--bin",
            "live_bar_smoke",
            "--",
            "--scenario",
            scenario,
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    TMPDIR.mkdir(parents=True, exist_ok=True)
    artifact_root = TMPDIR / (
        "backtesting_engine_opsd_live_bar_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    outputs = []
    for scenario in ("tradeable-pass", "parity-degraded", "reset-boundary-reject"):
        outputs.append(run_scenario(scenario, artifact_root / scenario))
    print("\n".join(outputs))
    print(f"artifact_root={artifact_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
