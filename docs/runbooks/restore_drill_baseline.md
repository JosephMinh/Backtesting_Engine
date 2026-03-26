# Restore Drill Baseline

This runbook defines the minimum durability and restore-drill baseline for the single-host live lane.

## Baseline Requirements

- Canonical metadata and operational state use automated PostgreSQL backups with WAL archiving or equivalent point-in-time coverage.
- Releases, evidence, snapshots, journals, and raw archives are copied to off-host versioned or append-only storage outside the live host failure domain.
- Economically significant journals and snapshot barriers use tamper-evident hash chaining.
- Every restore drill binds a database backup label to an artifact-store checkpoint through a restore manifest.
- Initial targets are `RPO <= 15 minutes` and `RTO <= 4 hours` for the live-capable host or VM.
- Raw historical re-ingestion is the only surface allowed looser recovery targets, and only when deterministic vendor re-pull is documented.

## Restore Drill Procedure

1. Select the candidate PostgreSQL backup label and the matching artifact checkpoint.
2. Export a restore manifest with file paths, hashes, backup completion time, restore start time, and restore completion time.
3. Restore artifacts into an isolated test environment.
4. Run `python3 infra/restore_drill.py --baseline infra/backup_restore_baseline.json --manifest <manifest> --restored-root <restored-root>`.
5. Review the structured output for `reason_codes`, `data_loss_window_minutes`, `restore_duration_minutes`, file-count parity, and hash mismatches.
6. Record the correlation id, manifest id, and outcome as restore-drill evidence.

## Green Criteria

- `RESTORE_DRILL_OK` is the only reason code.
- The drill verifies the expected recovery point inside the configured RPO.
- The drill finishes inside the configured RTO.
- Expected and actual file counts match.
- No file is missing, extra, or hash-mismatched.

## Readiness Use

Later readiness and activation checks must treat both of the following as green requirements before live approval:

- backup freshness inside the configured RPO window
- most recent restore drill with a passing structured result
