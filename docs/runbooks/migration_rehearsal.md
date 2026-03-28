# Migration Rehearsal

## When To Use

Use this runbook before schema or state-layout changes that need a rehearsed watchdog migration path and a documented safe-halt response when prerequisites are missing.

## Preconditions

- Verified backup evidence is current.
- The operator has a clean state-store frontier or has already decided to stop and remediate.
- The migration artifact directory is writable.

## Commands

1. Exercise the full restore and migration smoke:
   `bash rust/watchdog/scripts/restore_migration_smoke.sh`
2. Exercise the direct migration safe-halt path:
   `cargo run -p backtesting-engine-watchdog -- execute-migration dirty-state-store --artifact-dir <artifact-dir>`

## Evidence To Inspect

- `migration_report.txt`
- `migration_request.txt`
- `reason_code`
- `safe_halt_required`
- `applied_steps`

## Safe Outcomes

- Missing prerequisites force `MIGRATION_PREREQUISITES_NOT_MET` and `safe_halt_required=true`.
- Applied migration steps remain zero when the runtime is not safe to advance.
- Migration evidence stays separated from ordinary runtime health evidence.
