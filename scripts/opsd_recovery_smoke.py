from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess  # nosec B404 - smoke harness intentionally invokes local tools
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "target"
TMPDIR = TARGET_DIR / "tmp"
SMOKE_SOURCE = REPO_ROOT / "rust" / "opsd" / "src" / "bin" / "recovery_smoke.rs"
FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "opsd_recovery_cases.json"
)


def _safe_tmpdir() -> Path:
    for variable in ("TMPDIR", "TMP", "TEMP"):
        candidate = os.environ.get(variable)
        if candidate:
            return Path(candidate)
    repo_local_tmpdir = TMPDIR / "runtime"
    repo_local_tmpdir.mkdir(parents=True, exist_ok=True)
    return repo_local_tmpdir


def _parse_key_value_output(raw: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in raw.strip().splitlines():
        key, separator, value = line.partition("=")
        if separator == "=":
            parsed[key] = value
    return parsed


def _load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compile_binary(binary_path: Path) -> None:
    TMPDIR.mkdir(parents=True, exist_ok=True)
    rustc = shutil.which("rustc")
    if rustc is None:
        raise RuntimeError("rustc is required for opsd recovery smoke")

    env = os.environ.copy()
    safe_tmpdir = _safe_tmpdir()
    env["TMPDIR"] = str(safe_tmpdir)
    env["TMP"] = str(safe_tmpdir)
    env["TEMP"] = str(safe_tmpdir)
    subprocess.run(  # nosec B603 - rustc path and arguments are repo-controlled
        [
            rustc,
            "--edition",
            "2021",
            str(SMOKE_SOURCE),
            "-o",
            str(binary_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def run_scenario(binary_path: Path, *, scenario: str, artifact_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    safe_tmpdir = _safe_tmpdir()
    env["TMPDIR"] = str(safe_tmpdir)
    env["TMP"] = str(safe_tmpdir)
    env["TEMP"] = str(safe_tmpdir)
    result = subprocess.run(  # nosec B603 - executes the compiled local smoke binary
        [
            str(binary_path),
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
    return _parse_key_value_output(result.stdout)


def main() -> int:
    fixture = _load_fixture()
    artifact_root = TMPDIR / (
        "backtesting_engine_opsd_recovery_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    binary_path = TMPDIR / f"opsd_recovery_smoke_{secrets.token_hex(4)}"
    print("log_stage=compile_binary")
    print(f"log_binary_path={binary_path}")
    compile_binary(binary_path)

    scenarios: dict[str, dict[str, str]] = {}
    for case in fixture["scenario_cases"]:
        scenario = str(case["scenario"])
        print(f"log_stage=run_scenario scenario={scenario}")
        record = run_scenario(
            binary_path,
            scenario=scenario,
            artifact_dir=artifact_root / scenario,
        )
        for key, expected in case["expected"].items():
            actual = record.get(key)
            if actual != str(expected):
                raise RuntimeError(
                    f"scenario {scenario} expected {key}={expected!r}, got {actual!r}"
                )
        scenarios[scenario] = record

    print(f"log_stage=complete artifact_root={artifact_root}")
    print(
        json.dumps(
            {
                "artifact_root": str(artifact_root),
                "scenarios": scenarios,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
