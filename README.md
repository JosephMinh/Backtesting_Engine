# Backtesting_Engine

Backtesting_Engine is an early-stage research and operations program for making honest promotion decisions about gold futures strategies and then operating approved strategies safely in paper, shadow-live, and live trading.

The repository is currently a planning-and-contract scaffold. The detailed program design lives in [Plan_1.md](/home/ubuntu/ntm_Dev/Backtesting_Engine/Plan_1.md), and beads in `.beads/issues.jsonl` are the task system of record.

## Mission

The program exists to answer six questions before capital is trusted:

1. Which strategy families deserve budget?
2. Which parameter regions are stable enough to validate?
3. Which candidates survive realistic fills, null comparisons, robustness tests, omission tests, and a frozen final holdout?
4. If research is done on MGC but live execution is on 1OZ, has portability and execution-symbol tradability been explicitly certified rather than assumed?
5. Can the exact frozen candidate be replayed through the operational stack without research/live drift, including data-profile, contract-state, and signal-kernel parity?
6. Can the candidate survive paper trading, shadow-live, account-fit, session resets, broker reconciliation, and solo-operator operational risk on the live contract?

The platform is not allowed to optimize for attractive backtests at the expense of deployability.

## Initial Live-Lane Posture

The first approved lane is intentionally narrow:

- Historical research is centered on `MGC`.
- Paper, shadow-live, and live execution are centered on `1OZ`.
- Live market data and execution are both `IBKR` in v1.
- The approved live account posture is capped at `$5,000` with a maximum of one live `1OZ` contract.
- Live-eligible strategies must be bar-based with decision intervals of one minute or slower.
- Depth-dependent, queue-dependent, and sub-minute strategies are research-only.
- The default live posture is one active live bundle per account/product.
- The first production deployment targets one Linux host or VM.
- Overnight holding is permitted only as a stricter candidate class with additional gates.

## Planned Architecture

The target architecture is a hybrid Python/Rust monorepo with strict plane separation:

- Python research plane for ingestion, releases, backtests, tuning, replay certification, and reporting.
- Rust kernel plane for canonical live-eligible signal kernels and deterministic shared compute.
- Rust operational plane for `opsd`, broker integration, risk enforcement, recovery, and reconciliation.
- Shared contracts for schemas, policy bundles, state machines, fixtures, and compatibility rules.

The first scaffolded contract for this repo lives at:

- `shared/policy/charter/initial_live_lane.json`
- `shared/fixtures/charter/initial_live_lane_cases.json`
- `python/research/charter/posture.py`
- `tests/test_initial_live_lane.py`

These artifacts encode the initial live-lane posture as machine-readable assertions with executable checks and structured decision traces.
