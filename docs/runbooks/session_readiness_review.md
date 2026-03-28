# Session Readiness Review

## When To Use

Use this runbook before any paper, shadow, or live activation and after resets, material reconnects, or any activation-health provider changes.

## Preconditions

- The latest compiled schedule and runtime state are available.
- Activation-health evidence for clock discipline, secret health, restore freshness, and backup freshness is current.
- The operator knows which blocked provider or suspect provider is under review.

## Commands

1. Run the readiness smoke suite:
   `python3 scripts/opsd_readiness_smoke.py`
2. Review the direct runtime scenario when needed:
   `cargo run -p backtesting-engine-opsd --bin backtesting-engine-opsd -- --scenario session-readiness`
3. Recheck activation preflight from watchdog:
   `cargo run -p backtesting-engine-watchdog -- activation-preflight blocked-clock --artifact-dir <artifact-dir>`

## Evidence To Inspect

- `session_readiness_packet.txt`
- `artifact_root`
- `reason_code`
- `blocked_provider_count`
- `missing_required_provider_count`
- `packet_digest`

## Safe Outcomes

- `READINESS_PROVIDER_BLOCKED` keeps activation blocked until the provider is repaired.
- `READINESS_PROVIDER_REVIEW_REQUIRED` keeps the operator in review mode rather than silently clearing the session.
- `READINESS_REQUIRED_PROVIDER_MISSING` invalidates the packet until the required provider is restored.
