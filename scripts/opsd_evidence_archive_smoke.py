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
SMOKE_SOURCE = (
    REPO_ROOT / "rust" / "opsd" / "src" / "bin" / "evidence_archive_smoke.rs"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "opsd_evidence_archive_cases.json"
)


def _load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _parse_key_value_output(raw: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in raw.strip().splitlines():
        key, separator, value = line.partition("=")
        if separator == "=":
            parsed[key] = value
    return parsed


def _safe_tmpdir() -> Path:
    for variable in ("TMPDIR", "TMP", "TEMP"):
        candidate = os.environ.get(variable)
        if candidate:
            return Path(candidate)
    repo_local_tmpdir = TMPDIR / "runtime"
    repo_local_tmpdir.mkdir(parents=True, exist_ok=True)
    return repo_local_tmpdir


def compile_binary(binary_path: Path) -> None:
    TMPDIR.mkdir(parents=True, exist_ok=True)
    rustc = shutil.which("rustc")
    if rustc is None:
        raise RuntimeError("rustc is required for opsd evidence archive smoke")

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


def _run_command(binary_path: Path, args: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    safe_tmpdir = _safe_tmpdir()
    env["TMPDIR"] = str(safe_tmpdir)
    env["TMP"] = str(safe_tmpdir)
    env["TEMP"] = str(safe_tmpdir)
    result = subprocess.run(  # nosec B603 - executes the compiled local smoke binary
        [str(binary_path), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_key_value_output(result.stdout)


def main() -> int:
    fixture = _load_fixture()
    defaults = dict(fixture["defaults"])
    artifact_root = TMPDIR / (
        "backtesting_engine_opsd_evidence_archive_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    archive_root = artifact_root / "archive"
    sources_root = artifact_root / "sources"
    binary_path = TMPDIR / f"opsd_evidence_archive_smoke_{secrets.token_hex(4)}"
    print("log_stage=compile_binary")
    print(f"log_binary_path={binary_path}")
    compile_binary(binary_path)

    sealed: list[dict[str, str]] = []
    for case in fixture["cases"]:
        print(f"log_stage=seal_case case_id={case['case_id']} evidence_id={case['evidence_id']}")
        source_root = sources_root / case["case_id"]
        source_root.mkdir(parents=True, exist_ok=True)
        for source_file in case["source_files"]:
            path = source_root / source_file["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source_file["content"], encoding="utf-8")

        result = _run_command(
            binary_path,
            [
                "seal",
                "--source-root",
                str(source_root),
                "--archive-root",
                str(archive_root),
                "--evidence-id",
                case["evidence_id"],
                "--artifact-class",
                case["artifact_class"],
                "--candidate-id",
                defaults["candidate_id"],
                "--deployment-instance-id",
                defaults["deployment_instance_id"],
                "--session-id",
                defaults["session_id"],
                "--drill-id",
                case["drill_id"],
                "--retention-class",
                defaults["retention_class"],
                "--operator-summary",
                case["operator_summary"],
            ],
        )
        if result["status"] != "pass":
            raise RuntimeError(f"seal failed: {result}")
        sealed.append(result)

    query_results: dict[str, dict[str, object]] = {}
    for query in fixture["queries"]:
        print(f"log_stage=query query_id={query['query_id']}")
        args = ["query", "--archive-root", str(archive_root)]
        for key, value in dict(query["filters"]).items():
            args.extend([f"--{key.replace('_', '-')}", value])
        result = _run_command(binary_path, args)
        matched = sorted(
            item for item in result.get("matched_evidence_ids", "").split(",") if item
        )
        expected = sorted(list(query["expected_evidence_ids"]))
        if matched != expected:
            raise RuntimeError(
                f"query {query['query_id']} mismatch: expected {expected}, got {matched}"
            )
        query_results[query["query_id"]] = {
            "matched_evidence_ids": matched,
            "match_count": int(result["match_count"]),
        }

    summary = {
        "archive_root": str(archive_root),
        "sealed_evidence_ids": [item["evidence_id"] for item in sealed],
        "query_results": query_results,
    }
    print(f"log_stage=complete archive_root={archive_root}")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
