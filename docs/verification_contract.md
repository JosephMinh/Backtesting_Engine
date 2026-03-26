# Verification Contract

This document encodes the shared verification taxonomy requested by `backtesting_engine-ltc.11.1`. It is intentionally machine-aligned with [shared/policy/verification_contract.py](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/verification_contract.py) so downstream beads can point to named evidence classes instead of vague "tested enough" language.

## Core Rules

- Every critical surface must declare all three verification lanes: local checks, golden-path scenarios, and failure-path drills.
- Every phase gate must retain structured logs, correlation IDs, expected-vs-actual diffs, artifact manifests, operator-readable reason bundles, and decision traces.
- Fixture provenance is mandatory. Tests must identify whether they rely on certified releases, golden sessions, broker session recordings, synthetic failure cases, or plan-seeded fixtures.
- Deterministic seeds and deterministic clocks are required for any verification surface that can affect promotion, readiness, or continuation decisions.

## Verification Taxonomy

- `unit`: focused invariant and rule checks.
- `contract`: schema, interface, and compatibility checks.
- `property`: higher-volume invariant checks over generated inputs.
- `golden_path`: representative end-to-end scenarios proving the intended happy path.
- `failure_path`: negative-path drills that prove the system rejects, halts, or pivots safely.
- `parity_certification`: explicit equivalence certification between research/live or historical/live semantics.
- `replay_certification`: deterministic replay and recovery certification.
- `operational_rehearsal`: operator-grade rehearsal of runtime workflows, readiness, and emergency control paths.

## Phase-Gate Matrix

| Phase gate | Covered surfaces |
| --- | --- |
| `phase_0` | mission/posture, guardrails, plane boundaries |
| `phase_1` | data/reference pipeline |
| `phase_2` | data/reference pipeline |
| `phase_2_5` | execution-lane vertical slice |
| `phase_3` | simulation/execution profiles |
| `phase_4` | research governance and selection |
| `phase_5` | research governance and selection |
| `phase_6` | candidate freeze and certification |
| `phase_7` | paper runtime and operational evidence |
| `phase_8` | live-readiness and resilience |
| `phase_9` | program closure and continuation |

## Critical Surface Matrix

| Surface | Related beads | Local checks | Golden path | Failure path |
| --- | --- | --- | --- | --- |
| Mission and live-lane posture | `backtesting_engine-ltc.1.1` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Program guardrails | `backtesting_engine-ltc.1.2` | `unit`, `contract`, `property` | `golden_path` | `failure_path`, `operational_rehearsal` |
| Plane boundaries and shared contracts | `backtesting_engine-ltc.2.1` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Data/reference and release pipeline | `backtesting_engine-ltc.3.1`, `3.4`, `3.8`, `3.9` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Execution-lane vertical slice | `backtesting_engine-ltc.1.5`, `4.3` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Simulation and execution profiles | `backtesting_engine-ltc.4.1`, `4.5` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Research governance and selection | `backtesting_engine-ltc.6.1`, `6.2`, `6.6`, `6.7` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Candidate freeze and certification | `backtesting_engine-ltc.7.1`, `7.3`, `7.6` | `unit`, `contract`, `property` | `golden_path`, `replay_certification`, `parity_certification` | `failure_path` |
| Paper runtime and operational evidence | `backtesting_engine-ltc.7.7`, `7.8`, `7.10`, `backtesting_engine-tox` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path`, `replay_certification` |
| Live-readiness and resilience | `backtesting_engine-ltc.8.1`, `8.3`, `8.5`, `backtesting_engine-w81` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path`, `replay_certification` |
| Program closure and continuation | `backtesting_engine-ltc.10.1`, `10.4` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |

## Required Retained Artifacts

- Structured logs
- Correlation IDs
- Expected-vs-actual diffs
- Artifact manifests
- Operator-readable reason bundles
- Decision traces
- Fixture manifests
- Reproducibility stamps

