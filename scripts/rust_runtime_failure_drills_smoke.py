from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - trusted repo-local harness invoking repo binaries
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "target" / "rust-runtime-failure-drills"
TMPDIR = TARGET_DIR / "tmp"
CARGO_TARGET_DIR = TARGET_DIR / "cargo-target"
FIXTURE_PATH = (
    REPO_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "rust_runtime_failure_drills_cases.json"
)
SCRIPT_REFERENCE = "scripts/rust_runtime_failure_drills_smoke.py"


def _load_fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        decoded = json.load(handle)
    if not isinstance(decoded, dict):
        raise RuntimeError("rust runtime failure drills fixture must decode to an object")
    return decoded


def _parse_key_values(payload: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_command(command: list[str], *, stdout_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    TMPDIR.mkdir(parents=True, exist_ok=True)
    CARGO_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(TMPDIR)
    env["TMP"] = str(TMPDIR)
    env["TEMP"] = str(TMPDIR)
    env["CARGO_TARGET_DIR"] = str(CARGO_TARGET_DIR)
    result = subprocess.run(  # nosec B603 - fixed repo-local command paths and arguments
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    rendered = stdout + ("\n" if stdout else "")
    if stderr:
        rendered += "\n[stderr]\n" + stderr + "\n"
    _write_text(stdout_path, rendered)
    return _parse_key_values(stdout)


def _cargo_executable() -> str:
    cargo = shutil.which("cargo")
    if cargo is None:
        raise RuntimeError("cargo executable not found on PATH")
    return cargo


def _run_guardian(command: str, scenario: str, case_dir: Path) -> dict[str, str]:
    artifact_dir = case_dir / "artifacts"
    return _run_command(
        [
            _cargo_executable(),
            "run",
            "-q",
            "-p",
            "backtesting-engine-guardian",
            "--",
            command,
            scenario,
            "--artifact-dir",
            str(artifact_dir),
        ],
        stdout_path=case_dir / "stdout.txt",
    )


def _run_watchdog(command: str, scenario: str, case_dir: Path) -> dict[str, str]:
    artifact_dir = case_dir / "artifacts"
    return _run_command(
        [
            _cargo_executable(),
            "run",
            "-q",
            "-p",
            "backtesting-engine-watchdog",
            "--",
            command,
            scenario,
            "--artifact-dir",
            str(artifact_dir),
        ],
        stdout_path=case_dir / "stdout.txt",
    )


def _run_opsd(scenario: str, case_dir: Path) -> dict[str, str]:
    return _run_command(
        [
            _cargo_executable(),
            "run",
            "-q",
            "-p",
            "backtesting-engine-opsd",
            "--bin",
            "backtesting-engine-opsd",
            "--",
            "--scenario",
            scenario,
        ],
        stdout_path=case_dir / "stdout.txt",
    )


def _list_artifacts(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        str(path)
        for path in root.rglob("*")
        if path.is_file()
    )


def _retained_artifact_tokens(parsed: dict[str, str]) -> list[str]:
    values: list[str] = []
    for key, raw_value in parsed.items():
        if not raw_value:
            continue
        if not (
            "artifact" in key
            or key.endswith("manifest_id")
            or key.endswith("manifest_ids")
        ):
            continue
        if key.endswith("_id") or key.endswith("_ids"):
            parts = [item.strip() for item in raw_value.split(",") if item.strip()]
            values.extend(parts)
    return values


def _validate_expected(case_id: str, actual: dict[str, str], expected: dict[str, Any]) -> None:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != str(expected_value):
            raise RuntimeError(
                f"{case_id} expected {key}={expected_value!r}, got {actual_value!r}"
            )


def _execute_case(
    case: dict[str, Any],
    *,
    artifact_root: Path,
    run_id: str,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    runner = str(case["runner"])
    scenario = str(case["scenario"])
    case_dir = artifact_root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    if runner == "guardian":
        actual = _run_guardian(str(case["command"]), scenario, case_dir)
        command_artifact_dir = case_dir / "artifacts"
    elif runner == "watchdog":
        actual = _run_watchdog(str(case["command"]), scenario, case_dir)
        command_artifact_dir = case_dir / "artifacts"
    elif runner == "opsd":
        actual = _run_opsd(scenario, case_dir)
        command_artifact_dir = case_dir
    else:
        raise RuntimeError(f"unsupported runner for {case_id}: {runner}")

    _validate_expected(case_id, actual, case["expected"])

    retained_artifact_ids = sorted(
        {
            str(case_dir / "stdout.txt"),
            *(_list_artifacts(command_artifact_dir)),
            *(_retained_artifact_tokens(actual)),
        }
    )
    summary_key = str(case.get("summary_key", ""))
    operator_summary = (
        actual.get(summary_key)
        or actual.get("operator_summary")
        or actual.get("latest_summary")
        or actual.get("explanation")
        or str(case["explanation"])
    )
    primary_reason_key = str(case["primary_reason_key"])
    correlation_id = f"rust_runtime_failure_drills:{run_id}:{case_id}"

    return {
        "case_id": case_id,
        "phase": case["phase"],
        "runner": runner,
        "command": case.get("command"),
        "scenario": scenario,
        "status": "pass",
        "primary_reason_key": primary_reason_key,
        "primary_reason_code": actual[primary_reason_key],
        "safe_outcome_assertion": case["safe_outcome_assertion"],
        "explanation": case["explanation"],
        "operator_summary": operator_summary,
        "contract_refs": list(case["contract_refs"]),
        "correlation_id": correlation_id,
        "artifact_dir": str(command_artifact_dir),
        "stdout_path": str(case_dir / "stdout.txt"),
        "retained_artifact_ids": retained_artifact_ids,
        "output_fields": actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the 12.10 Rust-runtime failure-drill matrix across guardian, "
            "watchdog, and opsd command surfaces."
        )
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named fixture case instead of the full drill matrix.",
    )
    args = parser.parse_args()

    fixture = _load_fixture()
    cases = list(fixture["drill_cases"])
    if args.case_id is not None:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        if not cases:
            raise SystemExit(f"unknown case id: {args.case_id}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    artifact_root = TARGET_DIR / f"drill-run-{run_id}"
    artifact_root.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for case in cases:
        print(
            "log_stage=run_case "
            f"case_id={case['case_id']} runner={case['runner']} scenario={case['scenario']}"
        )
        reports.append(_execute_case(case, artifact_root=artifact_root, run_id=run_id))

    print(f"log_stage=complete artifact_root={artifact_root}")
    print(
        json.dumps(
            {
                "artifact_root": str(artifact_root),
                "script_reference": SCRIPT_REFERENCE,
                "drill_reports": reports,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
