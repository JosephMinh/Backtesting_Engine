# Verification Contract

This document encodes the shared verification taxonomy requested by `backtesting_engine-ltc.11.1`. It is intentionally machine-aligned with [shared/policy/verification_contract.py](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/verification_contract.py) so downstream beads can point to named evidence classes instead of vague "tested enough" language.

It also carries the shared lifecycle/compatibility contract for `backtesting_engine-ltc.8.2` and the cross-plane structured logging and artifact-capture contract for `backtesting_engine-ltc.11.6`, so startup, migration, promotion, runtime, and recovery gates all retain the same reconstruction primitives.

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
| `phase_0` | mission/posture, guardrails, Phase 0 foundation gate, plane boundaries, lifecycle state machines and compatibility domains |
| `phase_1` | data/reference pipeline, Phase 1 raw archive/reference gate |
| `phase_2` | data/reference pipeline, Phase 2 validation/release-pipeline gate, lifecycle state machines and compatibility domains |
| `phase_2_5` | execution-lane vertical slice, operational runtime supervision and deterministic state ownership |
| `phase_3` | simulation/execution profiles, fast-screening governance |
| `phase_4` | research governance and selection |
| `phase_5` | research governance and selection, strategy contracts and canonical signal kernels, baseline risk controls and waiver defaults, operating-envelope and session-conditioned risk profiles, fully loaded economics |
| `phase_6` | candidate freeze and certification, strategy contracts and canonical signal kernels, lifecycle state machines and compatibility domains |
| `phase_7` | paper runtime and operational evidence, operational runtime supervision and deterministic state ownership, baseline risk controls and waiver defaults, operating-envelope and session-conditioned risk profiles, lifecycle state machines and compatibility domains |
| `phase_8` | live-readiness and resilience, lifecycle state machines and compatibility domains |
| `phase_9` | Phase 9 continuation-review and scope-governance gate, program closure and continuation |

## Critical Surface Matrix

| Surface | Related beads | Local checks | Golden path | Failure path |
| --- | --- | --- | --- | --- |
| Mission and live-lane posture | `backtesting_engine-ltc.1.1` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Program guardrails | `backtesting_engine-ltc.1.2` | `unit`, `contract`, `property` | `golden_path` | `failure_path`, `operational_rehearsal` |
| Phase 0 foundation and QA gate | `backtesting_engine-ltc.9.1` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Plane boundaries and shared contracts | `backtesting_engine-ltc.2.1` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Phase 1 raw archive and bitemporal reference gate | `backtesting_engine-ltc.9.2` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Phase 2 validation and release-pipeline gate | `backtesting_engine-ltc.9.3` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Phase 9 continuation-review and scope-governance gate | `backtesting_engine-ltc.9.11` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Data/reference and release pipeline | `backtesting_engine-ltc.3.1`, `3.4`, `3.8`, `3.9`, `3.10`, `3.11` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Execution-lane vertical slice | `backtesting_engine-ltc.1.5`, `4.3`, `11.9` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Operational runtime supervision and deterministic state ownership | `backtesting_engine-ltc.7.9` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Simulation and execution profiles | `backtesting_engine-ltc.4.1`, `4.2`, `4.4`, `4.5`, `11.9` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Fast-screening governance | `backtesting_engine-ltc.4.6` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Strategy contracts and canonical signal kernels | `backtesting_engine-ltc.5.1` | `unit`, `contract`, `property` | `golden_path`, `parity_certification` | `failure_path` |
| Baseline risk controls and waiver defaults | `backtesting_engine-ltc.5.2` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Operating-envelope and session-conditioned risk profiles | `backtesting_engine-ltc.5.3` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Account-fit gate on the actual execution contract | `backtesting_engine-ltc.5.4` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Fully loaded economics and recurring cost model | `backtesting_engine-ltc.5.5` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Absolute-dollar viability and benchmark gate | `backtesting_engine-ltc.5.6` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Strict overnight candidate class | `backtesting_engine-ltc.5.7` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Lifecycle state machines and compatibility domains | `backtesting_engine-ltc.8.2` | `unit`, `contract`, `property` | `golden_path` | `failure_path`, `operational_rehearsal` |
| Structured logging and artifact capture | `backtesting_engine-ltc.11.6` | `unit`, `contract`, `property` | `golden_path`, `replay_certification`, `operational_rehearsal` | `failure_path` |
| Domain contract suites for policy, schemas, execution profiles, and broker semantics | `backtesting_engine-ltc.11.3` | `unit`, `contract`, `property` | `golden_path` | `failure_path`, `operational_rehearsal` |
| Research governance and selection | `backtesting_engine-ltc.6.1`, `6.2`, `6.3`, `6.4`, `6.5`, `6.6`, `6.7` | `unit`, `contract`, `property` | `golden_path` | `failure_path` |
| Candidate freeze and certification | `backtesting_engine-ltc.7.1`, `7.3`, `7.6` | `unit`, `contract`, `property` | `golden_path`, `replay_certification`, `parity_certification` | `failure_path` |
| Paper runtime and operational evidence | `backtesting_engine-ltc.7.7`, `7.8`, `7.10`, `backtesting_engine-tox` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path`, `replay_certification` |
| Operator observability and response targets | `backtesting_engine-ltc.8.4` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |
| Live-readiness and resilience | `backtesting_engine-ltc.8.1`, `8.3`, `8.5`, `backtesting_engine-w81` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path`, `replay_certification` |
| Program closure and continuation | `backtesting_engine-ltc.10.1`, `10.2`, `10.3`, `10.4` | `unit`, `contract`, `property` | `golden_path`, `operational_rehearsal` | `failure_path` |

## Required Retained Artifacts

- Structured logs
- Correlation IDs
- Expected-vs-actual diffs
- Artifact manifests
- Operator-readable reason bundles
- Decision traces
- Fixture manifests
- Reproducibility stamps

## Lifecycle Compatibility Contract

The shared lifecycle catalog in [shared/policy/lifecycle_specs.py](/home/ubuntu/ntm_Dev/Backtesting_Engine/shared/policy/lifecycle_specs.py) publishes canonical machine-readable specs for:

- `release_dataset_lifecycle`
- `release_derived_lifecycle`
- `bundle_readiness_lifecycle`
- `deployment_instance_lifecycle`
- `research_run_lifecycle`
- `family_decision_lifecycle`

Compatibility is checked across explicit domains rather than a single opaque version:

- `data_protocol`
- `strategy_protocol`
- `ops_protocol`
- `policy_bundle_hash`
- `compatibility_matrix_version`

Tests load fixture cases that cover both:

- allowed and blocked lifecycle transitions with expected machine-readable transition logs
- compatibility checks that distinguish missing domains, unknown domains, and blank values

This contract gives later startup checks, migration policy, and promotion logic one shared vocabulary for state transitions and compatibility bindings.

## Structured Logging Contract

Every retained cross-plane log record must carry the same envelope fields:

- `schema_version`
- `event_type`
- `plane`
- `event_id`
- `recorded_at_utc`
- `correlation_id`
- `decision_trace_id`
- `reason_code`
- `reason_summary`
- `referenced_ids`
- `redacted_fields`
- `omitted_fields`
- `artifact_manifest`

The retained artifact manifest inside that envelope must carry:

- `manifest_id`
- `generated_at_utc`
- `retention_class`
- `contains_secrets`
- `redaction_policy`
- `artifacts`

Every artifact entry must carry:

- `artifact_id`
- `artifact_role`
- `relative_path`
- `sha256`
- `content_type`

## Cross-Plane Correlation IDs

| Plane | Required identifiers |
| --- | --- |
| `research` | `research_run_id`, `dataset_release_id`, `analytic_release_id`, `data_profile_release_id`, `resolved_context_bundle_id` |
| `release` | `dataset_release_id`, `analytic_release_id`, `data_profile_release_id`, `resolved_context_bundle_id`, `candidate_bundle_id` |
| `policy` | `research_run_id`, `resolved_context_bundle_id`, `family_decision_record_id`, `candidate_bundle_id` |
| `certification` | `family_decision_record_id`, `candidate_bundle_id`, `promotion_packet_id`, `session_readiness_packet_id` |
| `runtime` | `candidate_bundle_id`, `promotion_packet_id`, `session_readiness_packet_id`, `deployment_instance_id`, `order_intent_id` |
| `recovery` | `promotion_packet_id`, `session_readiness_packet_id`, `deployment_instance_id`, `order_intent_id` |

These identifiers are chosen so a failure or drill can be reconstructed without reading unrelated logs. Release lineage, policy decisions, runtime state, and recovery evidence all keep at least one bridge identifier into the adjacent plane.

## Secret Boundaries

Structured logs must preserve debugging value without leaking credentials or account-sensitive payloads. Every artifact manifest therefore records:

- whether the retained bundle still contains secrets via `contains_secrets`
- which redaction policy was applied via `redaction_policy`

Every retained envelope also declares:

- `redacted_fields`: sensitive fields that were transformed but still left a diagnostic breadcrumb
- `omitted_fields`: sensitive fields that were dropped entirely from the retained log payload

The contract currently requires the golden fixtures to exercise redaction coverage for:

- `broker_account_id`
- `credential_ref`
- `api_token`
- `session_cookie`

## Cross-Plane Reconstruction Story

The golden fixtures are not just per-plane schema samples. Together they form one reconstructable workflow:

1. research emits release lineage and the canonical `research_run_id`
2. release freezes the candidate bundle and retains the release lineage bridge
3. policy records the `family_decision_record_id` against the same candidate bundle
4. certification binds the candidate into `promotion_packet_id` and `session_readiness_packet_id`
5. runtime emits `deployment_instance_id` and `order_intent_id`
6. recovery proves it can reconstruct the runtime state from those retained identifiers without reading unrelated logs

Tests assert the expected identifier coverage for each bridge so later tooling cannot silently drift the cross-plane story apart.

## Golden Fixture Enforcement

The machine contract defines golden log fixtures for each plane and validates them in [tests/test_verification_contract.py](/home/ubuntu/ntm_Dev/Backtesting_Engine/tests/test_verification_contract.py). That keeps log envelope fields, correlation identifiers, artifact-manifest fields, and redaction markers from drifting silently as later beads add runtime or recovery tooling.
