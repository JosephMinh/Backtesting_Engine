from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load JSON from {path}") from exc


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compare_manifest_to_restored(manifest: dict[str, Any], restored_root: Path) -> dict[str, Any]:
    expected_files = manifest["files"]
    expected_paths = {entry["relative_path"] for entry in expected_files}

    comparisons: list[dict[str, Any]] = []
    missing_files: list[str] = []
    hash_mismatches: list[str] = []

    for entry in expected_files:
        restored_path = restored_root / entry["relative_path"]
        if not restored_path.exists():
            missing_files.append(entry["relative_path"])
            comparisons.append(
                {
                    "relative_path": entry["relative_path"],
                    "status": "missing",
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": None,
                }
            )
            continue

        actual_sha256 = _sha256(restored_path)
        status = "match" if actual_sha256 == entry["sha256"] else "hash_mismatch"
        if status == "hash_mismatch":
            hash_mismatches.append(entry["relative_path"])

        comparisons.append(
            {
                "relative_path": entry["relative_path"],
                "status": status,
                "expected_sha256": entry["sha256"],
                "actual_sha256": actual_sha256,
            }
        )

    actual_paths = {
        str(path.relative_to(restored_root))
        for path in restored_root.rglob("*")
        if path.is_file()
    }
    extra_files = sorted(actual_paths.difference(expected_paths))

    return {
        "comparisons": comparisons,
        "missing_files": sorted(missing_files),
        "hash_mismatches": sorted(hash_mismatches),
        "extra_files": extra_files,
        "expected_file_count": len(expected_files),
        "actual_file_count": len(actual_paths),
    }


def _recovery_reason_summary(status: str, reason_codes: list[str]) -> str:
    if status == "pass":
        return "Restore drill completed within RPO/RTO targets and verified retained evidence."
    return "Restore drill detected recovery gaps: " + ", ".join(reason_codes)


def _artifact_manifest(manifest: dict[str, Any], recorded_at: datetime) -> dict[str, Any]:
    return {
        "manifest_id": manifest["manifest_id"],
        "generated_at_utc": _isoformat_utc(recorded_at),
        "retention_class": "recovery_evidence",
        "contains_secrets": False,
        "redaction_policy": "restore_summary_only",
        "artifacts": [
            {
                "artifact_id": entry["relative_path"].replace("/", "__"),
                "artifact_role": "restored_evidence",
                "relative_path": entry["relative_path"],
                "sha256": entry["sha256"],
                "content_type": "application/octet-stream",
            }
            for entry in manifest["files"]
        ],
    }


def evaluate_restore_drill(
    baseline: dict[str, Any],
    manifest: dict[str, Any],
    restored_root: Path,
) -> dict[str, Any]:
    restored_root = restored_root.resolve()
    if not restored_root.exists():
        raise ValueError(f"Restored root does not exist: {restored_root}")

    restore_started_at = _parse_timestamp(manifest["restore_started_at"])
    restore_completed_at = _parse_timestamp(manifest["restore_completed_at"])
    backup_completed_at = _parse_timestamp(manifest["backup_completed_at"])

    rpo_target_minutes = baseline["targets"]["canonical_metadata_and_live_state_rpo_minutes"]
    rto_target_minutes = baseline["targets"]["replacement_host_rto_hours"] * 60

    file_check = _compare_manifest_to_restored(manifest, restored_root)
    data_loss_window_minutes = round(
        (restore_started_at - backup_completed_at).total_seconds() / 60, 2
    )
    restore_duration_minutes = round(
        (restore_completed_at - restore_started_at).total_seconds() / 60, 2
    )

    reason_codes: list[str] = []
    if data_loss_window_minutes > rpo_target_minutes:
        reason_codes.append("RESTORE_DRILL_RPO_EXCEEDED")
    if restore_duration_minutes > rto_target_minutes:
        reason_codes.append("RESTORE_DRILL_RTO_EXCEEDED")
    if file_check["missing_files"]:
        reason_codes.append("RESTORE_DRILL_MISSING_FILES")
    if file_check["extra_files"]:
        reason_codes.append("RESTORE_DRILL_EXTRA_FILES_PRESENT")
    if file_check["hash_mismatches"]:
        reason_codes.append("RESTORE_DRILL_HASH_MISMATCH")
    if not reason_codes:
        reason_codes.append("RESTORE_DRILL_OK")

    status = "pass" if reason_codes == ["RESTORE_DRILL_OK"] else "fail"
    recorded_at = restore_completed_at
    referenced_ids = {
        "promotion_packet_id": manifest["promotion_packet_id"],
        "session_readiness_packet_id": manifest["session_readiness_packet_id"],
        "deployment_instance_id": manifest["deployment_instance_id"],
        "order_intent_id": manifest["order_intent_id"],
    }

    return {
        "schema_version": 1,
        "event_type": "recovery.restore_drill_completed",
        "plane": "recovery",
        "event_id": f"restore_drill_{manifest['manifest_id']}",
        "recorded_at_utc": _isoformat_utc(recorded_at),
        "correlation_id": str(uuid.uuid4()),
        "decision_trace_id": f"restore_drill_trace_{manifest['manifest_id']}",
        "reason_code": reason_codes[0],
        "reason_summary": _recovery_reason_summary(status, reason_codes),
        "referenced_ids": referenced_ids,
        "redacted_fields": [],
        "omitted_fields": [],
        "artifact_manifest": _artifact_manifest(manifest, recorded_at),
        "baseline_id": baseline["baseline_id"],
        "manifest_id": manifest["manifest_id"],
        "status": status,
        "reason_codes": reason_codes,
        "recovery_point_verified": data_loss_window_minutes <= rpo_target_minutes,
        "metrics": {
            "data_loss_window_minutes": data_loss_window_minutes,
            "restore_duration_minutes": restore_duration_minutes,
            "rpo_target_minutes": rpo_target_minutes,
            "rto_target_minutes": rto_target_minutes,
            "expected_file_count": file_check["expected_file_count"],
            "actual_file_count": file_check["actual_file_count"],
        },
        "restore_manifest_binding": {
            "database_backup_label": manifest["database_backup_label"],
            "artifact_checkpoint_id": manifest["artifact_checkpoint_id"],
        },
        "comparisons": file_check["comparisons"],
        "missing_files": file_check["missing_files"],
        "extra_files": file_check["extra_files"],
        "hash_mismatches": file_check["hash_mismatches"],
        "safe_to_repeat_in_test_environment": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a restore drill against a manifest.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--restored-root", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate_restore_drill(
        baseline=load_json(args.baseline),
        manifest=load_json(args.manifest),
        restored_root=args.restored_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
