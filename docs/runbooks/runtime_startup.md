# Runtime Startup

## When To Use

Use this runbook when bringing up the single-host Rust runtime stack or when verifying that a fresh boot still respects mailbox ownership, broker control ordering, and startup reconciliation routing.

## Preconditions

- `cargo` and `python3` are available on the host.
- `TMPDIR` and `CARGO_TARGET_DIR` should point at writable storage with enough space for transient build output.
- The operator has a current candidate bundle, compiled schedule, and the latest session-readiness packet available for review.

## Commands

1. Run the stack bring-up smoke:
   `bash scripts/runtime_stack_bringup_smoke.sh`
2. Run the startup and broker-runtime smoke:
   `python3 scripts/opsd_runtime_smoke.py`
3. If a narrower direct runtime check is needed, run:
   `cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario startup-handoff`

## Evidence To Inspect

- `startup_handoff`
- `mailbox_backpressure`
- `broker_mutation_control`
- `control_intent_id`
- `control_broker_order_ids`
- `duplicate_callback_deduplicated`

## Safe Outcomes

- Startup drains broker control messages in the documented order before ordinary traffic.
- Mailbox pressure retains high-priority flatten control instead of silently dropping it.
- Broker mutation control remains idempotent and preserves retained broker order identifiers.
