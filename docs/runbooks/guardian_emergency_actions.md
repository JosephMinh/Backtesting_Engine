# Guardian Emergency Actions

## When To Use

Use this runbook when the operator must validate or exercise the out-of-band cancel or flatten path independently of `opsd`.

## Preconditions

- The operator has the active readiness packet and the current broker connectivity snapshot.
- Emergency actions are authorized under the current operating posture.
- The artifact directory for guardian evidence is writable.

## Commands

1. Run the guardian drill bundle:
   `bash rust/guardian/scripts/emergency_drill.sh`
2. Run a direct authorized flatten drill if a single case is needed:
   `cargo run -p backtesting-engine-guardian -- emergency-drill authorized-flatten --artifact-dir <artifact-dir>`

## Evidence To Inspect

- `guardian_drills`
- `control_action_evidence`
- `reason_code`
- `disposition`
- `duplicate_invocation`
- `operator_summary`

## Safe Outcomes

- Guardian executes only the documented emergency actions.
- Duplicate invocations remain visible in evidence rather than being silently ignored.
- Impaired connectivity prevents the operator from confusing an unverified emergency path with a successful flatten.
