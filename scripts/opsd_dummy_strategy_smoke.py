from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - deterministic repo-local cargo execution
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "opsd_dummy_strategy_cases.json"
)
TARGET_DIR = REPO_ROOT / "target"
TMPDIR = TARGET_DIR / "tmp"
SAFE_TMPDIR = Path("/dev/shm") if Path("/dev/shm").exists() else Path("/var/tmp")  # nosec B108
SAFE_CARGO_TARGET = SAFE_TMPDIR / "backtesting_engine_opsd_dummy_strategy_target"


def load_cases() -> list[str]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [str(case["scenario"]) for case in payload["scenario_cases"]]


def run_scenario(cargo_binary: str, scenario: str, artifact_dir: Path) -> str:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = str(SAFE_TMPDIR)
    env["TMP"] = str(SAFE_TMPDIR)
    env["TEMP"] = str(SAFE_TMPDIR)
    env["CARGO_TARGET_DIR"] = str(SAFE_CARGO_TARGET)
    try:
        result = subprocess.run(  # nosec B603 - fixed executable path and fixed argument vector
            [
                cargo_binary,
                "run",
                "--quiet",
                "-p",
                "backtesting-engine-opsd",
                "--bin",
                "dummy_strategy_smoke",
                "--",
                "--scenario",
                scenario,
                "--artifact-dir",
                str(artifact_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - surfaced in failure output
        raise RuntimeError(exc.stderr.strip() or exc.stdout.strip()) from exc
    return result.stdout.strip()


def main() -> int:
    cargo_binary = shutil.which("cargo")
    if cargo_binary is None:
        raise RuntimeError("cargo executable not found on PATH")

    TMPDIR.mkdir(parents=True, exist_ok=True)
    artifact_root = TMPDIR / (
        "backtesting_engine_opsd_dummy_strategy_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    SAFE_CARGO_TARGET.mkdir(parents=True, exist_ok=True)

    for scenario in load_cases():
        stdout = run_scenario(cargo_binary, scenario, artifact_root / scenario)
        if stdout:
            print(stdout)
    print(f"artifact_root={artifact_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
