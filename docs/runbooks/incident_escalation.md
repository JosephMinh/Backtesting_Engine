# Incident Escalation

## When To Use

Use this runbook when a runtime failure must be escalated beyond a single subsystem and the operator needs one place to re-run the integrated drills and inspect the retained evidence bundle.

## Preconditions

- The operator has the failing deployment instance id or correlation id.
- Guardian, watchdog, readiness, reconciliation, and failure-path evidence are available.
- The operator can write a new smoke-report artifact or incident report artifact.

## Commands

1. Run the integrated Rust runtime failure matrix:
   `python3 scripts/rust_runtime_failure_drill_matrix_smoke.py --case-id phase8_rust_runtime_failure_operator_qualification`
2. Re-run the dependency-revocation incident drill when the incident path is under review:
   `python3 scripts/failure_path_drills_smoke.py --case-id allow_dependency_revocation_withdraw_and_review`
3. Re-run the resilience suite when the issue spans multiple gates:
   `python3 scripts/live_readiness_resilience_suite_smoke.py`

## Evidence To Inspect

- `incident_live_301`
- `corr-failure-drill-revocation-001`
- `corr-failure-drill-reconnect-001`
- `RUST_RUNTIME_FAILURE_DRILL_MATRIX_QUALIFIED`
- `FAILURE_DRILL_SAFE_OUTCOME_OBSERVED`

## Safe Outcomes

- Incident escalation keeps the operator on the documented drill matrix rather than ad hoc commands.
- Dependency withdrawal evidence includes the post-withdrawal review path.
- The integrated matrix preserves reason codes and safe-outcome assertions across guardian, watchdog, readiness, reconciliation, and recovery surfaces.
