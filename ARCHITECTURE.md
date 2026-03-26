# Planned Architecture

This document describes the intended architecture from [`Plan_1.md`](/home/ubuntu/ntm_Dev/Backtesting_Engine/Plan_1.md). It does not claim that the implementation already exists.

## Current Repository Reality

As of the current repository state:

- there is an early Python/shared package tree for charter, scope, guardrails, product/account profiles, time-discipline, topology, and verification contracts
- there is no Rust workspace
- there are no SQL migrations or runtime services checked in
- the repository is still primarily a planning and contract workspace

The implemented artifacts are currently:

- [`README.md`](/home/ubuntu/ntm_Dev/Backtesting_Engine/README.md)
- [`ARCHITECTURE.md`](/home/ubuntu/ntm_Dev/Backtesting_Engine/ARCHITECTURE.md)
- [`program_charter.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/program_charter.json)
- [`validate_program_charter.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/validate_program_charter.py)
- [`tests/test_program_charter.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_program_charter.py)
- [`shared/policy/clock_discipline.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/clock_discipline.py)
- [`shared/fixtures/policy/clock_discipline_cases.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/clock_discipline_cases.json)
- [`tests/test_clock_discipline.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_clock_discipline.py)
- [`shared/policy/product_profiles.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/product_profiles.py)
- [`shared/fixtures/policy/product_profiles.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/product_profiles.json)
- [`tests/test_product_profiles.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_product_profiles.py)
- [`shared/policy/storage_tiers.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/storage_tiers.py)
- [`shared/fixtures/policy/storage_tiers.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/storage_tiers.json)
- [`tests/test_storage_tiers.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_storage_tiers.py)
- [`shared/policy/metadata_telemetry.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/metadata_telemetry.py)
- [`tests/test_metadata_telemetry.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_metadata_telemetry.py)
- [`shared/policy/plane_boundaries.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/plane_boundaries.py)
- [`tests/test_plane_boundaries.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_plane_boundaries.py)

## Planned System Planes

The planned system is a hybrid Python/Rust monorepo with strict separation of concerns.

### Python Research Plane

Owns:

- historical ingestion
- release certification
- feature generation
- backtest orchestration
- tuning
- portability studies
- replay certification
- reporting

### Rust Kernel Plane

Owns:

- the canonical executable implementation of each live-eligible signal kernel
- determinism-sensitive shared compute
- Python bindings used by promotable research

### Rust Operational Plane

Owns:

- paper, shadow-live, and live runtime
- deterministic state management
- broker integration
- risk enforcement
- recovery
- reconciliation
- session-readiness checks

### Shared Contracts

Owns:

- schemas
- SQL migrations
- policy bundles
- compatibility matrices
- lifecycle state machines

The canonical executable ownership map for these planes lives in [`shared/policy/plane_boundaries.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/plane_boundaries.py). It is the machine-readable source of truth for allowed dependencies and boundary checks in the current repo.

## Canonical Metadata vs Dense Telemetry

The current machine-readable contract for the plan's metadata-versus-telemetry split lives in [`shared/policy/metadata_telemetry.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/metadata_telemetry.py).

It encodes two rules that must survive later implementation detail changes:

- canonical records such as research runs, manifests, candidates, readiness packets, policy records, incidents, ledger closes, and reconciliations remain queryable and durable even if telemetry retention changes;
- dense telemetry such as run metrics, parity series, latency series, drift metrics, and diagnostics may anchor back to canonical IDs but may not become the source of replay or promotion state.

The corresponding derivability and schema-level checks currently live in [`tests/test_metadata_telemetry.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_metadata_telemetry.py).

## Time Discipline and Session Clocks

The current machine-readable contract for UTC persistence, compiled session boundaries, and host-skew enforcement lives in [`shared/policy/clock_discipline.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/clock_discipline.py).

It encodes the defaults that must remain explicit as implementation expands:

- canonical persisted timestamps normalize to UTC and reject naive timestamps;
- exchange-local session boundaries come from compiled exchange calendars bound into resolved-context bundles;
- intra-process ordering uses durable sequence numbers and monotonic clocks rather than wall-clock ordering;
- and the initial bar-lane skew thresholds stay fixed at warn `100 ms`, restrict `500 ms`, and block `2 s`, with unknown synchronization state treated as a block condition.

Deterministic DST and calendar-boundary fixtures currently live in [`shared/fixtures/policy/clock_discipline_cases.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/clock_discipline_cases.json), and the corresponding contract tests live in [`tests/test_clock_discipline.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_clock_discipline.py).

## Product and Account Profiles

The current machine-readable contract for the initial product and account object model lives in [`shared/policy/product_profiles.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/product_profiles.py).

It currently encodes:

- canonical product profiles for `mgc_comex_v1` and `oneoz_comex_v1`, including contract specs, session policy references, delivery fences, roll-policy inputs, approved data-profile releases, and broker conformance invariants;
- the initial `solo_small_gold_ibkr_5000_v1` account profile, including approved equity, symbol set, size limits, margin fractions, loss and drawdown thresholds, and overnight posture rules;
- and a structured binding validator that distinguishes invalid, stale, and incompatible product/account/runtime combinations.

Deterministic binding fixtures currently live in [`shared/fixtures/policy/product_profiles.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/product_profiles.json), and the corresponding contract tests live in [`tests/test_product_profiles.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_product_profiles.py).

## Storage Tiers and Point-In-Time Binding

The current machine-readable contract for storage-tier placement and promotable experiment freezing lives in [`shared/policy/storage_tiers.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/storage_tiers.py).

It currently encodes:

- explicit Tier A through Tier E artifact placement for raw archives, bitemporal reference state, normalized research data, derived analytics, and operational evidence;
- structured placement reports that reject misplaced or unknown artifact classes with stable reason codes;
- and promotable experiment binding validation that requires exactly one dataset release, zero-or-one analytic release, one data-profile release, one observation cutoff, one resolved-context bundle, one policy bundle hash, and one compatibility matrix version, while explicitly rejecting mutable reference reads and post-freeze binding mutation.

Deterministic placement and binding fixtures currently live in [`shared/fixtures/policy/storage_tiers.json`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/fixtures/policy/storage_tiers.json), and the corresponding contract tests live in [`tests/test_storage_tiers.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_storage_tiers.py).

## Planned Monorepo Layout

The target layout in the plan is roughly:

- `python/research/`
- `python/bindings/`
- `rust/kernels/`
- `rust/opsd/`
- `rust/guardian/`
- `rust/watchdog/`
- `shared/schemas/`
- `shared/policy/`
- `shared/state_machines/`
- `shared/fixtures/`
- `sql/`
- `infra/`
- `docs/runbooks/`
- `tests/`

Those paths are not all present yet. They are architectural intent, not evidence of implementation.

## One-Host Baseline Topology

The current machine-readable topology contract for the intentionally narrow v1 deployment lives in [`shared/policy/topology.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/topology.py).

The required baseline components are:

- one Linux host or VM
- PostgreSQL 16 for canonical metadata and v1 telemetry
- off-host versioned object storage for immutable artifacts, backups, and journals
- Prometheus
- Grafana
- Loki
- IB Gateway or TWS on the same host under supervision
- `opsd`
- `guardian`
- a small watchdog or supervisor

This baseline remains sufficient until an explicit upgrade trigger fires. Startup and dependency checks are exercised in [`tests/test_topology.py`](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_topology.py).

## Initial Deployment Posture

The first approved lane is narrow on purpose:

- research centers on `MGC`
- live execution centers on `1OZ`
- v1 live data and execution use `IBKR`
- the initial live account profile is `$5,000`
- max live exposure is one `1OZ` contract
- live-eligible strategies must be bar-based and one minute or slower
- the first production deployment uses one Linux host or VM

## Critical Architectural Rules

The early plan imposes the following high-value constraints:

- no separate research and live signal logic for live-eligible strategies
- no mutable reference resolution after candidate freeze
- no live activation without replay, paper, shadow-live, and reconciliation evidence
- no broker mutation without durable intent identity and idempotency
- no live-capable stack without backup, restore, migration, clock, secret, and durability controls
- no live session without a green `session_readiness_packet`
- no single-path emergency control; a minimal `guardian` path must remain available

## Tooling Status

No language-specific package manager has been standardized in the repository yet. The current charter validator intentionally uses only the Python standard library so the repository can gain machine-readable constraints and tests without prematurely forcing a broader toolchain choice.
