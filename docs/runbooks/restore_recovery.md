# Restore And Recovery

## When To Use

Use this runbook after watchdog-triggered restart, restore verification, ambiguous state detection, or any restart-while-holding event.

## Preconditions

- The latest snapshot, journal frontier, and restore manifest are available.
- The operator has the current recovery barrier evidence and the current session-readiness packet.
- The artifact directory for recovery reports is writable.

## Commands

1. Run the recovery smoke bundle:
   `python3 scripts/opsd_recovery_smoke.py`
2. Run the watchdog restore and migration drill bundle:
   `bash rust/watchdog/scripts/restore_migration_smoke.sh`
3. Recheck the direct runtime recovery path:
   `cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario recovery-fence`

## Evidence To Inspect

- `recovery_report.txt`
- `shutdown_barrier_artifact.txt`
- `recovery_journal_digest_frontier_id`
- `recovery_session_readiness_packet_id`
- `shutdown_status`
- `recovery_status`

## Safe Outcomes

- Restart while holding returns only in `resume_exit_only`.
- Ambiguous journal or ownership state halts instead of resuming.
- Recovery remains tied to a fresh readiness packet and the retained journal frontier.
