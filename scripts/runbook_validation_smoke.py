from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - validation smoke intentionally executes trusted repo-local commands
import sys
import tempfile
from pathlib import Path
from typing import TypedDict


REPO_ROOT = Path(__file__).resolve().parents[1]


class RunbookSpec(TypedDict):
    runbook_id: str
    path: str
    required_headings: list[str]
    command_refs: list[str]
    path_refs: list[str]
    artifact_markers: list[str]


def _safe_tmpdir() -> Path:
    shared_memory_tmpdir = Path(os.sep) / "dev" / "shm"  # nosec B108 - intentional local smoke tmpdir
    if shared_memory_tmpdir.exists():
        return shared_memory_tmpdir
    return Path(tempfile.gettempdir())


SAFE_TMPDIR = _safe_tmpdir()
RUNBOOK_SPECS: list[RunbookSpec] = [
    {
        "runbook_id": "runtime_startup",
        "path": "docs/runbooks/runtime_startup.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "bash scripts/runtime_stack_bringup_smoke.sh",
            "python3 scripts/opsd_runtime_smoke.py",
            "cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario startup-handoff",
        ],
        "path_refs": [
            "scripts/runtime_stack_bringup_smoke.sh",
            "scripts/opsd_runtime_smoke.py",
        ],
        "artifact_markers": [
            "startup_handoff",
            "control_intent_id",
            "control_broker_order_ids",
        ],
    },
    {
        "runbook_id": "session_readiness_review",
        "path": "docs/runbooks/session_readiness_review.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "python3 scripts/opsd_readiness_smoke.py",
            "cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario session-readiness",
            "cargo run -p backtesting-engine-watchdog -- activation-preflight blocked-clock --artifact-dir <artifact-dir>",
        ],
        "path_refs": [
            "scripts/opsd_readiness_smoke.py",
        ],
        "artifact_markers": [
            "session_readiness_packet.txt",
            "blocked_provider_count",
            "packet_digest",
        ],
    },
    {
        "runbook_id": "shadow_paper_review",
        "path": "docs/runbooks/shadow_paper_review.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "python3 scripts/opsd_route_mode_smoke.py",
            "python3 scripts/opsd_dummy_strategy_smoke.py",
            "python3 scripts/opsd_vertical_slice_smoke.py",
        ],
        "path_refs": [
            "scripts/opsd_route_mode_smoke.py",
            "scripts/opsd_dummy_strategy_smoke.py",
            "scripts/opsd_vertical_slice_smoke.py",
        ],
        "artifact_markers": [
            "route_mode",
            "shadow_live",
            "vertical_slice_report",
        ],
    },
    {
        "runbook_id": "guardian_emergency_actions",
        "path": "docs/runbooks/guardian_emergency_actions.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "bash rust/guardian/scripts/emergency_drill.sh",
            "cargo run -p backtesting-engine-guardian -- emergency-drill authorized-flatten --artifact-dir <artifact-dir>",
        ],
        "path_refs": [
            "rust/guardian/scripts/emergency_drill.sh",
        ],
        "artifact_markers": [
            "guardian_drills",
            "control_action_evidence",
            "duplicate_invocation",
        ],
    },
    {
        "runbook_id": "reconciliation_response",
        "path": "docs/runbooks/reconciliation_response.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "python3 scripts/opsd_reconciliation_smoke.py",
            "python3 scripts/opsd_ledger_smoke.py",
        ],
        "path_refs": [
            "scripts/opsd_reconciliation_smoke.py",
            "scripts/opsd_ledger_smoke.py",
        ],
        "artifact_markers": [
            "daily_close_discrepancy_ids",
            "next_session_eligibility",
            "authoritative-ledger-close-0001",
        ],
    },
    {
        "runbook_id": "restore_recovery",
        "path": "docs/runbooks/restore_recovery.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "python3 scripts/opsd_recovery_smoke.py",
            "bash rust/watchdog/scripts/restore_migration_smoke.sh",
            "cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario recovery-fence",
        ],
        "path_refs": [
            "scripts/opsd_recovery_smoke.py",
            "rust/watchdog/scripts/restore_migration_smoke.sh",
        ],
        "artifact_markers": [
            "recovery_report.txt",
            "shutdown_barrier_artifact.txt",
            "recovery_session_readiness_packet_id",
        ],
    },
    {
        "runbook_id": "migration_rehearsal",
        "path": "docs/runbooks/migration_rehearsal.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "bash rust/watchdog/scripts/restore_migration_smoke.sh",
            "cargo run -p backtesting-engine-watchdog -- execute-migration dirty-state-store --artifact-dir <artifact-dir>",
        ],
        "path_refs": [
            "rust/watchdog/scripts/restore_migration_smoke.sh",
        ],
        "artifact_markers": [
            "migration_report.txt",
            "migration_request.txt",
            "safe_halt_required",
        ],
    },
    {
        "runbook_id": "incident_escalation",
        "path": "docs/runbooks/incident_escalation.md",
        "required_headings": [
            "## When To Use",
            "## Preconditions",
            "## Commands",
            "## Evidence To Inspect",
            "## Safe Outcomes",
        ],
        "command_refs": [
            "python3 scripts/rust_runtime_failure_drill_matrix_smoke.py --case-id phase8_rust_runtime_failure_operator_qualification",
            "python3 scripts/failure_path_drills_smoke.py --case-id allow_dependency_revocation_withdraw_and_review",
            "python3 scripts/live_readiness_resilience_suite_smoke.py",
        ],
        "path_refs": [
            "scripts/rust_runtime_failure_drill_matrix_smoke.py",
            "scripts/failure_path_drills_smoke.py",
            "scripts/live_readiness_resilience_suite_smoke.py",
        ],
        "artifact_markers": [
            "incident_live_301",
            "corr-failure-drill-revocation-001",
            "RUST_RUNTIME_FAILURE_DRILL_MATRIX_QUALIFIED",
        ],
    },
    {
        "runbook_id": "restore_drill_baseline",
        "path": "docs/runbooks/restore_drill_baseline.md",
        "required_headings": [
            "## Baseline Requirements",
            "## Restore Drill Procedure",
            "## Green Criteria",
            "## Readiness Use",
        ],
        "command_refs": [
            "python3 infra/restore_drill.py --baseline infra/backup_restore_baseline.json --manifest <manifest> --restored-root <restored-root>",
        ],
        "path_refs": [
            "infra/restore_drill.py",
            "infra/backup_restore_baseline.json",
        ],
        "artifact_markers": [
            "RESTORE_DRILL_OK",
            "reason_codes",
            "data_loss_window_minutes",
            "restore_duration_minutes",
        ],
    },
]


def validate_runbooks() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for spec in RUNBOOK_SPECS:
        path = REPO_ROOT / spec["path"]
        text = path.read_text(encoding="utf-8")
        missing_headings = [heading for heading in spec["required_headings"] if heading not in text]
        missing_commands = [command for command in spec["command_refs"] if command not in text]
        missing_paths = [
            path_ref for path_ref in spec["path_refs"] if not (REPO_ROOT / path_ref).exists()
        ]
        missing_artifact_markers = [
            marker for marker in spec["artifact_markers"] if marker not in text
        ]
        status = (
            "pass"
            if not (missing_headings or missing_commands or missing_paths or missing_artifact_markers)
            else "fail"
        )
        results.append(
            {
                "runbook_id": spec["runbook_id"],
                "path": spec["path"],
                "status": status,
                "missing_headings": missing_headings,
                "missing_commands": missing_commands,
                "missing_paths": missing_paths,
                "missing_artifact_markers": missing_artifact_markers,
            }
        )
    return results


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["TMPDIR"] = str(SAFE_TMPDIR)
    env["TMP"] = str(SAFE_TMPDIR)
    env["TEMP"] = str(SAFE_TMPDIR)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CARGO_TARGET_DIR"] = str(SAFE_TMPDIR / "backtesting-engine-cargo-target")
    env["PYTHONPATH"] = str(REPO_ROOT)
    return env


def _decode_last_json_object(payload: str, *, label: str) -> dict[str, object]:
    for raw_line in reversed(payload.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = json.JSONDecoder().decode(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise RuntimeError(f"{label} did not emit a final JSON object")


def _parse_readiness_output(stdout: str) -> tuple[dict[str, dict[str, str]], Path]:
    records: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    artifact_root: Path | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "scenario":
            current = {"scenario": value}
            records[value] = current
            continue
        if key == "artifact_root":
            artifact_root = Path(value)
            continue
        if current is not None:
            current[key] = value
    if artifact_root is None:
        raise RuntimeError("readiness smoke output did not include artifact_root")
    return records, artifact_root


def run_representative_path() -> dict[str, object]:
    env = _base_env()
    runtime = subprocess.run(  # nosec B603 - trusted repo-local smoke script
        [sys.executable, str(REPO_ROOT / "scripts" / "opsd_runtime_smoke.py")],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    runtime_payload = _decode_last_json_object(runtime.stdout, label="opsd runtime smoke")

    readiness = subprocess.run(  # nosec B603 - trusted repo-local smoke script
        [sys.executable, str(REPO_ROOT / "scripts" / "opsd_readiness_smoke.py")],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    readiness_records, artifact_root = _parse_readiness_output(readiness.stdout)
    blocked = readiness_records["broker-state-blocked"]

    return {
        "status": "pass",
        "steps": [
            {
                "step_id": "runtime_startup_smoke",
                "status": "pass",
                "reason_code": runtime_payload["broker_mutation_control"]["control_reason_code"],
                "duplicate_callback_deduplicated": runtime_payload["broker_mutation_control"][
                    "duplicate_callback_deduplicated"
                ],
            },
            {
                "step_id": "session_readiness_smoke",
                "scenario": "broker-state-blocked",
                "status": blocked["status"],
                "reason_code": blocked["reason_code"],
                "artifact_root": str(artifact_root),
                "blocked_provider_count": blocked["blocked_provider_count"],
            },
        ],
    }


def main() -> int:
    output_dir: Path | None = None
    if len(sys.argv) == 3 and sys.argv[1] == "--output-dir":
        output_dir = Path(sys.argv[2])
        output_dir.mkdir(parents=True, exist_ok=True)

    print("log_stage=validate_runbooks")
    runbooks = validate_runbooks()
    if any(runbook["status"] != "pass" for runbook in runbooks):
        raise SystemExit("runbook validation failed")

    print("log_stage=run_representative_path")
    representative_path = run_representative_path()
    report = {
        "status": "pass",
        "runbooks": runbooks,
        "representative_path": representative_path,
    }

    if output_dir is not None:
        report_path = output_dir / "runbook_validation_report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"log_stage=wrote_report path={report_path}")

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
