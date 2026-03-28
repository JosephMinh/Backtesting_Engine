# Shadow And Paper Review

## When To Use

Use this runbook when confirming that non-economic rehearsals still route correctly through paper and shadow modes before the runtime is trusted for live activation.

## Preconditions

- The candidate bundle is already replay-certified and vertically qualified.
- The operator has the current route-mode policy and the retained paper or shadow evidence directory for the session.

## Commands

1. Validate route-mode suppression and routing:
   `python3 scripts/opsd_route_mode_smoke.py`
2. Rehearse the dummy strategy lane:
   `python3 scripts/opsd_dummy_strategy_smoke.py`
3. Re-run the vertical slice:
   `python3 scripts/opsd_vertical_slice_smoke.py`

## Evidence To Inspect

- `route_mode`
- `paper`
- `shadow_live`
- `vertical_slice_report`
- `artifact_root`
- `reason_code`

## Safe Outcomes

- Shadow-live suppression prevents unintended economic routing during rehearsal.
- Paper-routing leaves retained evidence that the route mode was explicit.
- Vertical-slice evidence stays bound to the same execution-lane assumptions used by the operator.
