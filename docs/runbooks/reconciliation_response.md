# Reconciliation Response

## When To Use

Use this runbook when intraday or daily authoritative reconciliation reports a discrepancy, blocks next-session eligibility, or restricts new entries.

## Preconditions

- The latest statement set and internal ledger close are available.
- The operator has the retained discrepancy identifiers and the current next-session eligibility state.
- Any active session is already in the safe posture required by runtime risk.

## Commands

1. Run the authoritative reconciliation smoke:
   `python3 scripts/opsd_reconciliation_smoke.py`
2. Re-run the internal ledger session-close smoke when the discrepancy source is unclear:
   `python3 scripts/opsd_ledger_smoke.py`

## Evidence To Inspect

- `intraday_reconciliation`
- `authoritative-ledger-close-0001`
- `daily_close_discrepancy_ids`
- `next_session_eligibility`
- `health_latest_authoritative_close_artifact_id`

## Safe Outcomes

- Intraday discrepancies can restrict new entries without losing the retained discrepancy set.
- Daily close discrepancies block the next session instead of silently clearing.
- The health surface reflects the same authoritative close artifact the operator is inspecting.
