from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "target"
TMPDIR = TARGET_DIR / "tmp"
SMOKE_SOURCE = (
    REPO_ROOT / "rust" / "opsd" / "src" / "bin" / "strategy_health_smoke.rs"
)
SAFE_TMPDIR = Path("/dev/shm") if Path("/dev/shm").exists() else Path("/var/tmp")


def compile_harness(binary_path: Path) -> None:
    TMPDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = str(SAFE_TMPDIR)
    env["TMP"] = str(SAFE_TMPDIR)
    env["TEMP"] = str(SAFE_TMPDIR)
    subprocess.run(
        [
            "rustc",
            "--edition",
            "2021",
            "--test",
            str(SMOKE_SOURCE),
            "-o",
            str(binary_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def run_smoke_scenarios(binary_path: Path, artifact_root: Path) -> str:
    artifact_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["STRATEGY_HEALTH_SMOKE_ARTIFACT_ROOT"] = str(artifact_root)
    env["TMPDIR"] = str(SAFE_TMPDIR)
    env["TMP"] = str(SAFE_TMPDIR)
    env["TEMP"] = str(SAFE_TMPDIR)
    result = subprocess.run(
        [
            str(binary_path),
            "--exact",
            "smoke_tests::scenario_sweep_emits_strategy_health_states",
            "--nocapture",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    rustc = shutil.which("rustc")
    if rustc is None:
        raise RuntimeError("rustc is required for opsd strategy health smoke")

    TMPDIR.mkdir(parents=True, exist_ok=True)
    artifact_root = TMPDIR / (
        "backtesting_engine_opsd_strategy_health_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    binary_path = TMPDIR / "strategy_health_smoke_tests"
    compile_harness(binary_path)

    print(run_smoke_scenarios(binary_path, artifact_root))
    print(f"artifact_root={artifact_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
