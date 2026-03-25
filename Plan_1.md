# Production Plan v3.8 for a Solo Gold Futures Research and Deployment Platform

**Research posture:** MGC-centered historical research with Databento historical data  
**Live posture:** 1OZ-first paper/shadow/live deployment on IBKR  
**Operator model:** Solo operator, one-host baseline, research honesty first

**v3.8 emphasis:** prove the 1OZ/IBKR lane early, centralize bar semantics in versioned `data_profile_release` artifacts, and require shadow-live plus per-session readiness before live canary.

---

## 1. Mission and operating posture

### 1.1 Mission

Build a production-capable platform that can make **honest promotion decisions** about gold futures strategies and then operate approved strategies safely in paper, shadow-live, and live trading.

The platform exists to answer six questions:

1. Which strategy families deserve budget?
2. Which parameter regions are stable enough to validate?
3. Which candidates survive realistic fills, null comparisons, robustness tests, omission tests, and a frozen final holdout?
4. If research is done on MGC but live execution is on 1OZ, have portability and execution-symbol tradability been explicitly certified rather than assumed?
5. Can the exact frozen candidate be replayed through the operational stack without research/live drift, including data-profile, contract-state, and signal-kernel parity?
6. Can the candidate survive paper trading, shadow-live, account-fit, session resets, broker reconciliation, and solo-operator operational risk on the actual live contract?

The system is not allowed to optimize for attractive backtests at the expense of deployability.

### 1.2 Initial product and account posture

The initial deployment posture is intentionally narrow:

- historical research is centered on **MGC**,
- paper/shadow/live execution is centered on **1OZ**,
- live market data and execution are both **IBKR** in v1,
- the initial approved live account profile is **$5,000**, **max one live 1OZ contract**,
- live-eligible strategies must be **bar-based** with decision intervals of **1 minute or slower**,
- depth-dependent, queue-dependent, and sub-minute strategies are research-only,
- the default live posture is **one active live bundle per account/product**,
- the first production deployment targets **one Linux host or VM**,
- and **overnight holding is allowed in v1 only as a stricter candidate class** with additional gates.

### 1.3 Non-negotiable principles

1. **No custom historical matching engine in v1.** Historical simulation uses NautilusTrader high-level backtesting.
2. **No ad-hoc files in promotable research.** Experiments point to certified releases and immutable artifacts.
3. **No mutable reference resolution after freeze.** Frozen candidates, replay, paper, shadow-live, and live use resolved-context bundles and approved data-profile releases by digest.
4. **No promotion on gross PnL.** Decisions use realistic costs, slippage, recurring operational costs, and both passive-gold and lower-touch cash benchmarks.
5. **No notebook-only evidence for promotion.** Notebooks may explore; they may not directly advance promotable state.
6. **No live activation without deterministic replay, paper evidence, shadow-live evidence, and broker reconciliation controls.**
7. **No operational state ambiguity.** Economically significant state is journaled, replayable, recoverable, and cross-checked against broker state intraday as well as at end of day.
8. **No hidden optimization surfaces.** Lockboxes, nulls, discovery accounting, and operational-evidence admissibility rules are enforced.
9. **No premature infrastructure.** One host, PostgreSQL, off-host object storage, and in-process mailboxes remain the baseline until measured thresholds justify upgrades.
10. **No research/live logic fork for live-eligible strategies.** Research and operations must execute the same canonical signal kernel.
11. **No broker mutation without durable intent identity.** Submit, modify, cancel, and flatten actions must be journaled and idempotent across retry, restart, and reconnect.
12. **No live-capable stack without operational recoverability.** Backup/restore, migration, clock-discipline, secret-handling, and off-host tamper-evident durability controls are required before live approval.
13. **No deep promotable budget before the intended execution lane clears the early viability gate.**
14. **No new tradeable session without a green `session_readiness_packet` and broker contract-conformance checks.**
15. **No single-path emergency control for live safety.** Emergency cancel/flatten must remain possible through a minimal out-of-band `guardian` path.

---

## 2. Scope, anti-scope, and implementation profiles

### 2.1 In scope for the first full protocol cycle

The first full protocol cycle includes:

- an early execution-lane vertical slice proving 1OZ entitlement, approved bar construction, dummy-strategy replay, paper routing, shadow-live suppression, and reconciliation before deep family investment,
- immutable historical ingestion and release certification,
- bitemporal reference data with observation cutoffs,
- versioned `data_profile_release` artifacts for research/live market-data semantics,
- normalized research catalogs and derived analytic releases,
- realistic Nautilus backtesting and regime-conditioned execution-profile calibration,
- family preregistration, `research_run` logging, `family_decision_record` governance, nulls, discovery accounting, and lockbox discipline,
- candidate freezing into immutable deployment-grade bundles,
- execution-symbol-first viability screens, MGC-to-1OZ portability certification, and native execution-symbol validation on 1OZ when enough history exists,
- deterministic replay certification before paper,
- mandatory paper trading and shadow-live on the production connectivity lane before live canary,
- a Rust operational daemon with recovery fence, session-readiness packets, guardian emergency control, kill switch, and intraday plus end-of-day reconciliation,
- authoritative end-of-day broker statement reconciliation,
- and a narrow first live lane on IBKR.

### 2.2 Explicit anti-scope rules

The following stay out of scope until after at least one candidate has completed paper and shadow-live successfully and the continuation review approves expansion:

- custom historical matching or queue simulation engine,
- sub-minute live strategies,
- depth-driven or latency-sensitive live alpha,
- a second broker on the hot path,
- a premium second live market-data feed,
- Kubernetes or multi-host orchestration,
- mandatory NATS or other external transport,
- dedicated TimescaleDB or separate telemetry cluster by default,
- a generalized feature-store product,
- multi-product portfolio optimization,
- and multiple simultaneously active live bundles per account by default.

### 2.3 Implementation profiles and capability tiers

Every subsystem and optional feature must declare one of three tiers:

- **`v1_core_required`** — required for the first promotable paper/shadow/live-capable stack.
- **`v1_conditional`** — supported in v1 but only activated when the current candidate needs it.
- **`future_only`** — explicitly deferred.

Initial classification:

- `v1_core_required`: early execution-lane vertical slice, release pipeline, `data_profile_release` pipeline, bitemporal reference model, Nautilus backtesting, regime-conditioned execution profiles, `research_run` registry, `family_decision_record` governance, candidate freeze, replay certification, paper trading, shadow-live, IBKR runtime, session-readiness packets, guardian emergency control, idempotent order-intent layer, accounting ledger, intraday and end-of-day reconciliation, backup/restore, migration controls, time discipline, policy engine, secret baseline, solo governance.
- `v1_conditional`: overnight candidate class, native 1OZ validation, screening fast path, NATS, dedicated telemetry store, heavier secret-management tooling.
- `future_only`: second broker hot path, live premium feed, sub-minute execution, depth-aware signals, multi-host live control plane, portfolio optimizer.

### 2.4 Infrastructure upgrade triggers

The one-host baseline remains in force until one of the following is true:

- more than one hot-path host is required for paper/shadow/live,
- more than one durable external consumer needs ordered event fan-out beyond the database,
- telemetry write/query load materially degrades canonical metadata latency,
- the number of operators or credential domains makes OS-native or managed secret delivery insufficient,
- or live SLOs are repeatedly missed because of the current infrastructure rather than the strategy or broker.

Upgrades must be justified by a signed continuation memo, not by architectural preference.


### 2.5 Early viability gate

Before the platform invests in deep tuning or broad family expansion, it must clear an execution-lane viability gate on the actual intended live lane.

The viability gate must prove at minimum:

- 1OZ market-data entitlement and session coverage on the intended IBKR setup,
- deterministic live bar construction from the approved `data_profile_release`,
- end-to-end dummy-strategy flow through `opsd`, paper routing, shadow-live suppression, statement ingestion, and reconciliation,
- preliminary execution-symbol tradability on 1OZ by session class,
- and that the lane is not blocked by account type, permissions, contract-definition mismatches, or operational reset behavior.

If the viability gate fails, the program must either narrow scope, revise the account/product posture, or terminate before deeper research spend.

---

## 3. System architecture

### 3.1 High-level architecture

The platform is a hybrid Python/Rust monorepo with a strict separation of concerns:

- **Python research plane** owns ingestion, release certification, feature generation, backtest orchestration, tuning, portability studies, replay certification, and reporting.
- **Rust kernel plane** owns the canonical executable implementation of every live-eligible signal kernel and other determinism-sensitive shared components; Python consumes these through bindings for promotable research.
- **Rust operational plane** owns paper/shadow/live runtime, deterministic state management, broker integration, risk enforcement, recovery, reconciliation, and session-readiness checks.
- **Shared contracts** own schemas, SQL migrations, policy bundles, compatibility matrices, and lifecycle state machines.

### 3.2 One-host baseline topology

The minimum production-capable topology is:

- one Linux host or VM,
- PostgreSQL 16 for canonical metadata and v1 telemetry,
- off-host versioned object storage for immutable artifacts, backups, and journals,
- Prometheus/Grafana/Loki for observability,
- IB Gateway or TWS on the same host under supervision,
- `opsd` as the operational daemon,
- `guardian` as a minimal out-of-band emergency control process with independent cancel/flatten capability,
- and a small watchdog/supervisor process.

The one-host physical baseline is intentionally smaller than the long-term logical architecture.

### 3.3 Canonical metadata vs dense telemetry

The platform maintains a hard distinction between:

- **canonical metadata** — `research_run` records, `family_decision_record` objects, releases, manifests, candidates, readiness records, promotion packets, `session_readiness_packet` objects, policies, incidents, ledger closes, reconciliations, and other records of truth;
- **dense telemetry** — run metrics, parity series, quality events, latency series, drift metrics, and diagnostics.

Canonical metadata must remain queryable and durable even if telemetry retention or storage strategy changes.

### 3.4 Environment and trust-zone isolation

Three trust zones are required:

- **research** — notebooks, experiments, tuning, reporting;
- **release/certification** — artifact publication and signed promotion tooling;
- **paper/shadow/live operations** — `opsd`, broker connectivity, reconciliations, live controls.

Rules:

- the operational host does not run notebooks or tuning jobs,
- research environments do not hold broker or break-glass credentials,
- `opsd` may read approved artifacts and write evidence but may not mutate raw archives or releases,
- operational secrets are injected at runtime from controlled secret paths or services rather than embedded in manifests or unit files,
- dashboards use read-only roles,
- and storage prefixes/buckets use least-privilege credentials.

### 3.5 Time discipline and clocking

Time is a first-class operational dependency.

Rules:

- canonical persisted timestamps use UTC,
- exchange-local times are derived from compiled calendars and are never produced by ad-hoc runtime timezone logic,
- intra-process ordering uses durable sequence numbers and monotonic clocks rather than wall-clock ordering,
- session boundaries, maintenance windows, roll cutovers, and event windows come only from resolved-context bundles,
- and replay and certification fixtures must include DST-boundary and skew scenarios.

Initial default thresholds for the bar-based live lane:

- warn when host clock skew exceeds **100 ms**,
- enter `restrict` when skew exceeds **500 ms**,
- and block new entries and require reviewed recovery when skew exceeds **2 s** or synchronization state is unknown.

Operational hosts must run NTP/chrony or an equivalent synchronization service and expose synchronization health to policy and observability.

### 3.6 Durability, backup, and restore baseline

One-host operation does not remove disaster-recovery requirements.

The platform must provide:

- automated PostgreSQL backups plus WAL archiving or equivalent frequent point-in-time recovery coverage for canonical metadata and operational state,
- off-host versioned or append-only object storage for releases, evidence, snapshots, journals, and raw archives,
- backup targets that do not share the same failure domain as the live host or VM,
- tamper-evident hash chaining for economically significant journals and snapshot barriers,
- restore manifests that bind database backups to artifact-store checkpoints,
- explicit RPO/RTO targets,
- and documented restore runbooks.

Initial targets for the first live lane:

- canonical metadata and live state **RPO <= 15 minutes** during paper/shadow/live operation,
- live-capable host **RTO <= 4 hours** to a replacement host or VM,
- and looser targets for raw historical re-ingestion only when deterministic vendor re-pull is documented.

A full restore drill is required before first live approval and at least quarterly after live activation. No live promotion packet may be approved unless backup freshness and last restore-drill status are green.

### 3.7 Secret management and break-glass access

Secrets are controlled operational assets.

Rules:

- credentials may not appear in source code, notebooks, manifests, candidate bundles, promotion packets, logs, shell history, or systemd unit files,
- research, release, dashboard, and operations surfaces use separate least-privilege credentials,
- the one-host baseline may use OS-native secret delivery or encrypted on-disk secrets with root-only permissions; heavier secret-management systems are `v1_conditional`,
- break-glass credentials for broker or account emergency actions are stored separately from normal runtime credentials and are not mounted into the standard trading process,
- every break-glass access creates an incident record, requires post-use credential rotation, and is reviewed before the next live session,
- and secret rotation is required before first live approval and after any host compromise, role change, or break-glass use.

---

## 4. Canonical object model

The platform is organized around a small set of first-class objects.

### 4.1 Product and account objects

#### `product_profile`

Defines the canonical behavior of a tradeable instrument or research instrument.

Minimum contents:

- symbol and exchange,
- contract specifications and tick economics,
- session calendar and maintenance windows,
- delivery fences and last-trade constraints,
- roll policy inputs,
- approved data-profile releases,
- live broker capability assumptions,
- and expected broker contract invariants for pre-open conformance checks.

Initial profiles:

- `mgc_comex_v1`
- `oneoz_comex_v1`

#### `account_risk_profile`

Defines the approved capital and risk posture for a live or paper account.

Minimum contents:

- approved starting equity,
- approved symbol set,
- approved starting size,
- maximum position size,
- margin-utilization thresholds,
- daily loss lockout threshold,
- max drawdown threshold,
- overnight eligibility rules,
- and default operating posture.

Initial profile:

- `solo_small_gold_ibkr_5000_v1`

### 4.2 Artifact validity classes

All artifacts are immutable once published, but their **admissibility** differs.

#### Integrity-bound artifacts

These remain valid until dependencies are invalidated or an integrity failure is found:

- `research_run` records,
- `family_decision_record` objects,
- dataset releases,
- analytic releases,
- `data_profile_release` objects,
- resolved-context bundles,
- candidate bundles,
- replay fixtures,
- state snapshots,
- broker-session fixtures,
- and signed manifests.

#### Freshness-bound evidence

These are immutable artifacts whose use in promotion or activation requires recency checks:

- execution-profile calibrations,
- portability studies,
- native execution-symbol validation studies,
- execution-symbol tradability studies,
- Databento-to-IBKR bar-parity studies,
- paper-pass evidence,
- shadow-pass evidence,
- `session_readiness_packet` objects,
- fee schedule snapshots,
- broker margin snapshots,
- and operating-envelope recalibration evidence.

**Key rule:** a resolved-context bundle is an integrity-bound artifact. It does **not** expire merely because time passes.

### 4.3 Release and deployment objects

#### `research_run`

The immutable record of one promotable batch research execution.

Minimum contents:

- family id and subfamily id,
- run purpose (`screening`, `validation`, `stress`, `omission`, `portability`, `native_validation`, `tradability`, `lockbox`),
- code digests and environment lock,
- dataset release and analytic release references,
- data-profile and execution-profile references,
- parameter set or search-region id,
- seed(s),
- policy bundle hash,
- compatibility matrix version,
- output artifact digests,
- admissibility class,
- and parent/child lineage to prior runs.

#### `family_decision_record`

The signed record of one continue/pause/pivot/terminate budget decision for a strategy family.

Minimum contents:

- family id,
- decision timestamp,
- decision type,
- evidence references,
- budget consumed to date,
- next budget authorized,
- reviewer self-attestations,
- and expiry or revisit date where applicable.

#### `dataset_release`

A certified, point-in-time historical dataset.

Minimum contents:

- raw input hashes,
- reference version hashes,
- observation cutoff,
- validation rules version,
- catalog version,
- protocol versions,
- vendor revision watermark / correction horizon,
- certification report hash,
- policy bundle hash,
- and lifecycle state.

#### `analytic_release`

A published set of derived features or masks built from exactly one dataset release.

Minimum contents:

- source `dataset_release_id`,
- feature version,
- analytic-series version,
- feature block manifests,
- feature-availability contracts,
- optional slice manifests,
- artifact root hash,
- and lifecycle state.

#### `data_profile_release`

A versioned, immutable specification for how research and live market data are interpreted.

Minimum contents:

- source feed(s) and venue/dataset identifiers,
- schema and field-selection rules,
- timestamp precedence rules,
- bar-construction rules and session anchors,
- trade/quote precedence and zero-volume-bar policy,
- late-print and correction policy,
- gap and forward-fill policy,
- symbology mapping rules,
- live/historical parity expectations,
- and lifecycle state.

All promotable runs, replay certification, paper activation, shadow-live activation, and live activation must reference exactly one approved `data_profile_release`.

#### `resolved_context_bundle`

A frozen compilation of all reference and schedule state needed by a candidate, replay fixture, or deployment.

Minimum contents:

- source dataset release,
- observation cutoff,
- compiled session schedules and anchors,
- resolved bitemporal reference records,
- quality and protected-zone masks,
- event windows,
- roll maps and delivery fences,
- portability-policy resolution where relevant,
- and a content hash.

Resolved-context bundles are content-addressed and dependency-pinned. They may be invalidated only by dependency revocation, incompatible compiler/protocol changes, or a reproducibility failure.

#### `execution_profile_release`

A versioned execution-assumption profile used by backtests and diagnostics.

Minimum contents:

- order-type assumptions,
- session- and liquidity-conditioned slippage surfaces,
- fill rules,
- latency assumptions,
- adverse-selection penalties where applicable,
- assumptions for quote absence, spread spikes, and degraded bars,
- calibration evidence references,
- applicable `data_profile_release`,
- and release state.

#### `candidate_bundle`

The immutable deployment-grade handoff object.

Minimum contents:

- strategy family and subfamily identifiers,
- signal-kernel digest, kernel ABI / state-serialization version, and adapter compatibility hashes,
- parameterization,
- product profile,
- research symbol and execution symbol,
- dataset release and analytic release references,
- data-profile release reference,
- resolved-context bundle digest,
- execution-profile release reference,
- dependency DAG with feature-contract hashes,
- operating-envelope profile,
- session-conditioned strategy risk envelope when applicable,
- strategy-approved hard risk bounds,
- eligible account-class constraints and minimum capital/margin assumptions,
- required broker capability profile,
- portability-policy declaration,
- required evidence references,
- compatibility matrix version,
- and signatures.

The candidate bundle is immutable and content-addressed. It is never the mutable runtime state machine, and it does not encode a concrete broker account binding.

#### `bundle_readiness_record`

The mutable qualification/admission record for a candidate bundle under a specific policy/account/data-lane context.

It binds together:

- candidate bundle digest,
- target account binding,
- policy bundle hash,
- account risk profile,
- broker capability descriptor,
- approved data-profile binding,
- current fee schedule snapshot,
- current margin snapshot,
- freshness-bound evidence references,
- status,
- and approval history.

#### `deployment_instance`

The mutable activation record for one paper, shadow-live, or live deployment of a candidate bundle.

It records:

- deployment environment,
- account,
- candidate bundle digest,
- readiness record,
- active promotion packet,
- session-readiness packet history,
- runtime sequence numbers,
- operator actions,
- start/stop/withdrawal events,
- recovery events,
- and closure status.

#### `promotion_packet`

A signed approval snapshot required for transitions into paper, shadow-live, or live.

It freezes the exact evidence set used for approval, including:

- candidate bundle digest,
- target account binding,
- account risk profile hash,
- readiness record id,
- replay certification,
- portability certification,
- native validation when required,
- execution-symbol tradability study,
- paper-pass evidence when promoting to shadow-live or live,
- shadow-pass evidence when promoting to live,
- fee and margin snapshots,
- market-data entitlement check,
- active waivers,
- incident references,
- policy bundle hash,
- compatibility matrix version,
- sign-offs,
- and any evidence expiry timestamps.

#### `session_readiness_packet`

A signed per-session pre-open or post-reset readiness artifact bound to one deployment instance.

Minimum contents:

- deployment instance id,
- session identifier and validity window,
- source promotion packet id,
- fee, margin, entitlement, and contract-conformance checks,
- backup freshness, restore-drill, clock-health, and secret-health checks,
- unresolved discrepancy status,
- operating-envelope and session-specific eligibility checks,
- resulting session status,
- and decision trace hash.

#### `accounting_ledger`

An append-only internal accounting view used alongside broker-authoritative reconciliation.

Minimum event classes:

- booked fills,
- booked fees and commissions,
- booked cash movements,
- broker EOD positions,
- broker EOD margin snapshots,
- reconciliation adjustments,
- restatements,
- and unresolved discrepancies.

Reports must distinguish **as-booked** from **as-reconciled** results whenever a discrepancy or restatement exists.

---

## 5. Data model and release pipeline

### 5.1 Storage tiers

#### Tier A — immutable raw vendor archive

Store raw vendor payloads exactly as received, with request metadata, hashes, vendor response metadata, and ingestion logs.

#### Tier B — bitemporal reference and point-in-time data

Store contract definitions, lifecycle events, calendars, macro event calendars, roll inputs, and other reference facts with both:

- **effective time** — when the fact became true in the market domain,
- **observation time** — when the platform could have known it.

#### Tier C — normalized research catalog

Store cleaned, typed, partitioned market data suitable for backtesting.

#### Tier D — derived analytics

Store derived features, masks, and supporting analytic artifacts tied to one dataset release.

#### Tier E — operational evidence archive

Store immutable paper/shadow/live evidence, replay artifacts, broker-session recordings, recovery artifacts, parity reports, drift diagnostics, and post-session review materials.

### 5.2 Point-in-time discipline

Every promotable experiment must reference:

- one dataset release,
- zero or one analytic release,
- one data-profile release,
- one observation cutoff,
- one resolved-context bundle,
- one policy bundle hash,
- and one compatibility matrix version.

No promotable run may read mutable reference tables directly at execution time.

### 5.3 Validation and sidecar masks

Historical data is validated through sidecar masks and classifications, not destructive rewriting.

The validation pipeline must classify at least:

- structural schema failures,
- session misalignment,
- gaps,
- price anomalies,
- duplicate or out-of-order events,
- suspicious zero or locked values,
- and event-window sensitivity.

Outputs:

- validation report,
- sidecar masks,
- quality tier assignment,
- and release certification status.

### 5.4 Release model and lifecycle

#### Dataset release lifecycle

States:

- `DRAFT`
- `STAGING`
- `CERTIFIED`
- `APPROVED`
- `ACTIVE`
- `SUPERSEDED`
- `QUARANTINED`
- `REVOKED`

Rules:

- only `ACTIVE` releases seed new promotable work by default,
- `SUPERSEDED` releases remain reproducible,
- `QUARANTINED` releases block new experiments immediately,
- `REVOKED` releases propagate suspect status to all dependent artifacts.

#### Analytic release lifecycle

States:

- `DRAFT`
- `CERTIFIED`
- `APPROVED`
- `ACTIVE`
- `SUPERSEDED`
- `QUARANTINED`
- `REVOKED`

Analytic releases may publish optional slice manifests for folds, contract segments, sessions, and feature blocks.

#### Data-profile release lifecycle

States:

- `DRAFT`
- `CERTIFIED`
- `APPROVED`
- `ACTIVE`
- `SUPERSEDED`
- `QUARANTINED`
- `REVOKED`

Data-profile releases govern research/live market-data semantics and may not be edited in place.

### 5.5 Feature-availability contracts

Every derived feature block published in an analytic release must include a **feature-availability contract**.

Minimum fields:

- `feature_block_id`
- source artifact ids and source fields
- `value_timestamp_rule`
- `available_at_rule`
- whether bar close or session close is required
- decision-latency class
- fallback behavior when unavailable
- `feature_contract_hash`

Experiment build, replay certification, paper activation, shadow-live activation, and live activation must reject any feature block whose availability contract is incompatible with the candidate’s decision timing or bound `data_profile_release`.

### 5.6 Contract lifecycle and roll policy

Rules:

- execution logic uses **actual contract segments**, not synthetic continuous series,
- continuous series are for analytics and visualization only,
- active-contract selection is point-in-time and delivery-aware,
- hard delivery fences are enforced from the product profile,
- roll mapping is compiled into the resolved-context bundle,
- and backtests default to segment-based evaluation.

### 5.7 Release certification

A release becomes usable only after certification that includes:

- deterministic build manifests,
- prior-release semantic diffs,
- validation summary,
- canary backtests or parity fixtures where relevant,
- and policy evaluation.

A release promotion tool must produce signed certification reports and record them in canonical metadata.

### 5.8 Vendor corrections, restatements, and delta recertification

The platform must treat vendor corrections and reference-data restatements as first-class lifecycle events.

Rules:

- every certified `dataset_release` records the vendor revision watermark used at build time,
- when upstream corrections arrive after a release is certified, the platform produces a semantic impact diff before any replacement release is activated,
- correction impact must be classified as `none`, `diagnostic_only`, `recert_required`, or `suspect`,
- dependent analytic releases, data-profile releases, portability studies, and candidate readiness records are updated by policy rather than ad-hoc judgment,
- and correction handling must preserve reproducibility of the original release while making the superseding release explicit.

Minor corrections below policy thresholds may remain reproducible without invalidating prior decisions, but the impact classification and justification must be recorded.

---

## 6. Simulation, execution assumptions, and parity

### 6.1 Historical execution kernel

Historical simulation uses NautilusTrader high-level backtesting via `BacktestNode`, `BacktestRunConfig`, and `ParquetDataCatalog`.

Shared canonical signal kernels may execute inside that framework through bindings, but the platform does not build a second historical execution engine in v1.

### 6.2 Execution profiles

Three execution-profile classes are required:

- **screening** — cheaper but still honest,
- **validation** — the default promotion-grade profile,
- **stress** — pessimistic assumptions for robustness and account-fit.

Execution profiles are versioned releases, never edited in place. Promotion-grade profiles should be conditional on at least session class, realized-volatility bucket, spread bucket, and intended order size as a fraction of recent traded size or displayed liquidity.

### 6.3 Fidelity calibration

Before a strategy class becomes promotable, the platform must perform fidelity calibration to demonstrate that the chosen bar-based assumptions are admissible for that class.

The calibration must establish:

- whether one-minute or slower bars are sufficient,
- what slippage ranges are realistic,
- where passive assumptions are or are not credible,
- which strategy classes are excluded from the live lane,
- and, for execution symbols with materially heterogeneous liquidity by session class, separate admissibility and cost surfaces by session rather than a single blended assumption set.

### 6.4 Lower-frequency live lane

Live-eligible strategies must satisfy all of the following:

- decision interval of at least 1 minute,
- bar-based or one-bar-late decision logic,
- no order-book imbalance dependence,
- no queue-position edge requirement,
- no sub-minute market-making behavior,
- and no need for premium live depth data.

### 6.5 Research symbol vs execution symbol

The platform distinguishes explicitly between:

- **research symbol** — the instrument used for most historical development,
- **execution symbol** — the instrument used in paper/shadow/live operation.

Initial posture:

- research is primarily on **MGC**,
- execution is primarily on **1OZ**.

### 6.5A Execution-symbol-first viability

Research may begin on MGC for broader history and family discovery, but promotion-grade work may not proceed far on MGC alone.

Before deep tuning budget is approved for a family with `execution_symbol = 1OZ`, the platform must run an **execution-symbol-first viability screen** using the best native 1OZ history and live/paper observations available at the time.

The screen must evaluate at minimum:

- quote/print presence by session class,
- spread and bar completeness,
- fee-and-slippage feasibility at the approved size,
- tradable-session coverage after protected windows and maintenance fences,
- and whether the family’s intended holding period is compatible with 1OZ liquidity.

MGC remains valid for thesis development, regime coverage, and additional robustness context, but it may not be the sole basis for allocating deep promotable budget once 1OZ evidence is obtainable.

### 6.6 Portability certification

If `research_symbol != execution_symbol`, the platform must run a formal portability study before paper, shadow-live, or live. Portability does not replace execution-symbol tradability or native validation.

The portability study must evaluate at least:

- directional agreement,
- event timing alignment,
- trade count drift,
- fill sensitivity,
- cost sensitivity,
- turnover drift,
- and after-cost performance degradation under the execution symbol.

A strategy may proceed only if portability is explicitly passed under policy.

### 6.7 Native execution-symbol validation

When sufficient native history exists for the execution symbol, finalists must also be directly validated on the execution symbol rather than relying solely on portability inference.

For the initial posture, this means using native **1OZ** validation windows whenever enough history exists to make the result meaningful. Families that fail the earlier execution-symbol-first viability screen should normally be terminated before finalist selection.

### 6.8 Databento-to-IBKR bar parity

Before paper, shadow-live, or live, the platform must certify deterministic parity between:

- research bars built from approved historical data under the bound `data_profile_release`,
- and live bars built from the approved IBKR feed under the same approved bar-construction semantics.

The parity harness must compare at least:

- session boundaries,
- OHLCV construction,
- anchor timing,
- event-window labeling,
- and bar availability timing.

Parity is an empirical, freshness-bound certification artifact.

### 6.9 Optional fast screening path

For simple strategy classes only, the platform may use an optional fast screening path ahead of full Nautilus screening.

Eligibility rules:

- bar-close or one-bar-late decisions,
- simple order semantics,
- no path-dependent order management beyond basic brackets,
- no passive queue dependence,
- no portability-sensitive microstructure dependence.

Rules:

- the fast path is non-promotable,
- it requires an equivalence study against full Nautilus,
- its outputs may inform continuation or abandonment only,
- and every survivor must still pass full Nautilus screening, validation, stress, and null comparisons.

---

## 7. Strategy contract, risk, and economic viability

### 7.1 Strategy interface

Every strategy must implement a stable strategy contract with:

- parameter schema,
- required inputs,
- decision cadence,
- warm-up requirements,
- risk-control hooks,
- order-intent output schema,
- dependency DAG,
- kernel ABI / state-serialization version,
- and semantic version.

### 7.2 Shared signal-kernel rule

Any strategy that can become live-eligible must expose a **shared signal kernel** used by both:

- Python research adapters,
- and the Rust operational runtime.

For any live-eligible family, there must be exactly **one canonical executable implementation** of the signal kernel. The default pattern is a Rust crate exposed to Python through bindings. Python may wrap orchestration, feature plumbing, and diagnostics, but it may not carry an independent promotable implementation of the trading logic.

Research-only families may prototype in pure Python. Once a family receives continuation approval for promotable work, the family must migrate to the canonical shared kernel before deep tuning or lockbox entry.

Before candidate freeze, the platform must run signal-kernel equivalence certification comparing bound Python execution against direct Rust execution on golden-session fixtures and randomized property cases.

### 7.3 Baseline risk controls

Every live-eligible strategy inherits baseline controls unless policy grants a signed waiver:

- max position limits,
- max concurrent order-intent limits,
- entry suppression under degraded data quality,
- hard daily loss lockout,
- hard drawdown rules,
- forced-flat rules around delivery fences,
- warm-up hold before first trade,
- margin-aware pre-trade checks,
- and explicit overnight approval if overnight carrying is allowed.

### 7.4 Operating-envelope profile

Every live-eligible candidate must carry a machine-readable **operating-envelope profile**.

It defines green/yellow/red bands and actions for at least:

- spread regime,
- stale-quote rate,
- live bar-parity degradation,
- realized volatility bucket,
- session or event class,
- freshness-watermark lag,
- broker round-trip latency,
- and signal-score drift where relevant.

Actions may include:

- size reduction,
- passive-entry suppression,
- no new overnight carry,
- lower max trades,
- entry suppression,
- exit-only mode,
- or forced flatten.

### 7.5 Session-conditioned risk profile

When risk posture differs by session class, the candidate must also carry a session-conditioned risk profile.

At minimum, this may distinguish:

- overnight,
- regular COMEX session,
- maintenance/restart-adjacent windows,
- major scheduled macro-event windows,
- and degraded-data periods.

### 7.6 Account-fit gate

Promotion to paper, shadow-live, or live requires passing account-fit on the **actual execution contract** using a **fresh broker margin snapshot** and **current fee schedule artifact**.

Initial thresholds for `solo_small_gold_ibkr_5000_v1`:

- `max_initial_margin_fraction = 0.25`
- `max_maintenance_margin_fraction = 0.35`
- `daily_loss_lockout_fraction = 0.025`
- `max_drawdown_fraction = 0.15`
- `overnight_gap_stress_fraction = 0.05`

A candidate that fails account-fit for MGC but passes for 1OZ may proceed only with `execution_symbol = 1OZ`.

### 7.7 Fully loaded economics

Every candidate must be evaluated in three layers:

1. **gross**,
2. **net-direct** after fees and slippage,
3. **net-fully-loaded** after allocated recurring operational costs.

The cost model must include, at minimum:

- broker commissions and fees,
- exchange and regulatory fees,
- explicit slippage assumptions,
- live market-data costs,
- amortized historical-data spend attributable to the candidate family,
- and always-on infrastructure costs needed to run the strategy.

When session-conditioned liquidity is materially heterogeneous, the cost model must be parameterized by the active execution profile rather than by a single blended assumption set.

### 7.8 Absolute-dollar viability gate

A candidate is not promotable merely because it is statistically positive.

Promotion memos must report at the approved live size:

- conservative expected monthly net dollars,
- conservative monthly excess dollars versus a passive-gold benchmark,
- conservative monthly excess dollars versus a cash / short-duration Treasury benchmark on idle capital,
- downside monthly net dollars under a low-turnover scenario,
- and, when available, expected net dollars per operator maintenance hour.

For leveraged futures on a small account, promotion memos must also report expected return on committed margin, worst-session loss as a fraction of free cash, and whether a lower-touch alternative dominates after operator time is considered.

A candidate that is statistically acceptable but economically de minimis at the approved live size is rejected by default.

### 7.9 Overnight candidate class

Overnight eligibility remains in scope for v1, but only as a stricter candidate class.

There is no fundamental architectural problem with allowing overnight in v1. The issue is operational and economic risk on a small account: gap risk, maintenance windows, broker restarts, reduced liquidity, and larger divergence between model and live conditions.

An overnight candidate must satisfy **all** of the following in addition to ordinary live gates:

- explicit `allow_overnight = true` declaration,
- overnight-specific account-fit and gap-stress pass,
- session-conditioned operating-envelope profile,
- paper and shadow evidence covering overnight holds and overnight exits,
- restart-while-holding recovery tests,
- stricter broker and data-degradation responses,
- and explicit rules for no-new-carry windows around maintenance, severe data degradation, or reconciliation uncertainty.

---

## 8. Research governance and evaluation protocol

### 8.1 Strategy families and preregistration

Research is organized by strategy family and subfamily. Before substantive tuning, each family must be preregistered with:

- economic thesis,
- target session class,
- intended execution style,
- intended holding period,
- research symbol and expected execution symbol,
- execution-symbol tradability hypothesis,
- failure criteria,
- preliminary parameter ranges,
- primary evaluation metrics,
- and budget limits.

### 8.2 Research budgets and economics

Every family carries explicit budgets for:

- historical data spend,
- compute,
- tuning trials,
- operator review time,
- and total continuation budget.

Family continuation decisions must reference both research-quality evidence and research economics. These decisions are recorded as `family_decision_record` objects rather than only narrative notes.

Budgets beyond the exploratory stage require both a signed continuation decision and, when applicable, a passed early viability gate / execution-symbol-first viability screen.

### 8.3 Null suite and discovery control

The platform maintains a program-wide null suite that includes at least:

- random-entry nulls,
- time-shifted anchor nulls,
- side-flipped or ablated nulls,
- permutation nulls,
- and regime-conditional nulls.

Two discovery layers are required:

- **family-level discovery accounting**,
- **program-level discovery ledger**.

No family may consume unlimited search budget without explicit continuation approval.

### 8.4 Walk-forward and robustness protocol

The evaluation hierarchy is:

1. screening,
2. validation,
3. stress,
4. omission tests,
5. lockbox,
6. candidate freeze.

Required robustness checks:

- walk-forward folds,
- parameter stability checks,
- block-bootstrap confidence intervals,
- regime omission,
- segment omission,
- anchor omission,
- event-cluster omission,
- and minimum-detectable-edge/power analysis before deep tuning.

### 8.5 Lockbox policy

A frozen final holdout is required for promotion-grade evaluation.

Rules:

- the lockbox may not become a ranking surface,
- finalist count entering the lockbox is bounded,
- lockbox access is logged and policy-controlled,
- and any lockbox contamination requires explicit incident handling and likely candidate rejection or cycle restart.

### 8.6 Notebook quarantine and admissible evidence

Notebooks are useful for exploration and explanation, but notebook output is not promotion-admissible by itself.

Promotion-admissible evidence must come from:

- reproducible batch runs,
- signed manifests,
- certified releases,
- policy-evaluated reports,
- or sealed operational evidence bundles.

### 8.7 Selection and hard gates

A candidate may advance only if it passes:

- after-cost profitability,
- null separation,
- robustness and omission tests,
- lockbox evaluation,
- portability requirements,
- execution-symbol tradability requirements,
- account-fit,
- absolute-dollar viability,
- passive-gold comparison,
- and cash / lower-touch benchmark comparison.

Selection ranking may use Pareto-style views, but promotion is always gated, never purely ranked.

### 8.8 Tuning protocol

Tuning is allowed only after a family clears the continuation bar. For live-eligible work, deep promotable tuning also requires migration to the canonical shared kernel before lockbox entry.

Stages:

1. **Local search around a real region** — no blind global search over implausible space.
2. **Robustness perturbation search** — probe local sensitivity and degradation.
3. **Candidate freeze** — choose a finalist, pin all dependencies, and seal the bundle.

Tuning must log every promotable trial, seed, objective definition, and pruning decision. Every promotable batch execution produces a `research_run` record, even when the result is rejection.

---

## 9. Candidate freeze, readiness, and promotion

### 9.1 Candidate bundle contents

Freezing a candidate produces an immutable `candidate_bundle_id` containing the strategy-side material needed for replay, paper, shadow-live, and live qualification. Concrete account binding and freshness-bound operational context are added later through readiness and promotion artifacts.

Required contents:

- strategy code digests,
- parameterization,
- product profile,
- research symbol and execution symbol,
- dataset and analytic release references,
- data-profile release reference,
- resolved-context bundle digest,
- execution-profile release,
- dependency DAG with feature-contract hashes,
- operating-envelope profile,
- session-conditioned strategy risk envelope where applicable,
- strategy hard risk bounds,
- eligible account-class constraints and minimum capital/margin assumptions,
- required broker capabilities,
- portability policy,
- required certification references,
- compatibility matrix version,
- and signatures.

The candidate bundle may declare minimum eligible account characteristics, but it may not encode a concrete broker account, current fee schedule, current margin regime, or live-data entitlement. Those bindings belong to readiness, promotion, and session-readiness artifacts.

Paper, shadow-live, and live systems may load only registered candidate bundles. They may not load ad-hoc parameter sets, mutable image tags, or “latest successful” references.

### 9.2 Readiness record state machine

A candidate bundle’s mutable qualification state lives in `bundle_readiness_record`, not in the bundle itself.

Readiness records bind the frozen strategy artifact to a concrete account context, current fee/margin regime, broker capability descriptor, and approved data-profile binding.

States:

- `FROZEN`
- `PORTABILITY_PENDING`
- `PORTABILITY_PASSED`
- `REPLAY_PENDING`
- `REPLAY_PASSED`
- `PAPER_ELIGIBLE`
- `PAPER_PASSED`
- `SHADOW_ELIGIBLE`
- `SHADOW_PASSED`
- `LIVE_ELIGIBLE`
- `RECERT_REQUIRED`
- `SUSPECT`
- `REVOKED`

Only policy-evaluated transitions are allowed.

### 9.3 Deployment instance state machine

Operational activation state lives in `deployment_instance`.

States:

- `PAPER_PENDING`
- `PAPER_RUNNING`
- `SHADOW_PENDING`
- `SHADOW_RUNNING`
- `LIVE_CANARY`
- `LIVE_ACTIVE`
- `WITHDRAWN`
- `CLOSED`

Withdrawal is a deployment event, not a property of the candidate bundle.

### 9.4 Promotion packets

Any transition into paper, shadow-live, or live for a specific target account requires a signed `promotion_packet_id`.

Activation preflight must:

- load the promotion packet,
- resolve every referenced artifact by digest,
- verify target account binding and account-risk profile hash,
- verify compatibility domains,
- verify integrity of integrity-bound artifacts,
- verify recency of freshness-bound evidence,
- verify market-data entitlement and broker capability conformance,
- verify current fee and margin snapshots,
- verify execution-symbol tradability and native validation requirements where policy demands them,
- verify backup freshness, last restore-drill status, clock-synchronization health, and secret-health preconditions for the activation lane,
- and emit a signed preflight report.

If any freshness-bound evidence in the promotion packet has expired or been superseded incompatibly, activation fails and a new promotion packet is required.

### 9.4A Session readiness packets

Activation-time preflight is not sufficient for a deployment that may span multiple sessions or hold overnight.

Before each tradeable session, and before resuming after any broker daily reset, the platform must produce a `session_readiness_packet` bound to the active deployment instance.

The packet must verify at minimum:

- the promotion packet is still valid for the current session,
- fresh fee, margin, and entitlement checks where policy requires freshness,
- broker contract details match the approved product profile and resolved-context bundle,
- clock, backup, restore-drill, and secret-health preconditions remain green,
- no unresolved reconciliation discrepancy blocks the session,
- and session-specific operating-envelope gates are satisfied.

Failure to produce a green session readiness packet blocks new entries for that session.

### 9.5 Dependency revocation propagation

When a release, data-profile, or certification artifact is quarantined, revoked, or recertified with material correction impact, dependency propagation must mark affected readiness records as `SUSPECT`, `REVOKED`, or `RECERT_REQUIRED` according to policy.

No dependent live deployment may continue without an explicit reviewed waiver.

### 9.6 Emergency withdrawal

An operator may withdraw a live deployment at any time through `opsd`, the kill-switch path, or `guardian` emergency control.

Post-withdrawal review is mandatory within 24 hours and must decide whether the related readiness record remains valid, becomes `RECERT_REQUIRED`, becomes `SUSPECT`, or is `REVOKED`.

---

## 10. Paper and live operations

### 10.1 Deterministic replay certification before paper

Before a candidate may enter paper, the platform must certify deterministic replay through the operational stack.

Replay must compare, at minimum:

- signal values and timestamps,
- order-intent sequences,
- risk actions,
- contract-state decisions,
- decision sequence numbers,
- and freshness-watermark handling.

Replay certification is required before paper. Incremental recertification is allowed only when policy determines that the dependency change is narrow enough to justify it.

### 10.2 Paper trading and shadow-live are mandatory

Every live-eligible candidate must complete a paper stage and a shadow-live stage before any live canary.

Paper trading is the first place the platform validates:

- live market-data behavior,
- live bar construction,
- operational timing,
- broker API behavior,
- real reconciliation flow,
- and operating-envelope realism.

Shadow-live is the bridge to the actual production connectivity lane. It uses real production market-data entitlements, real session resets, real contract lookup, real operator controls, and a non-economic order-mutation sink or suppression path.

### 10.3 Paper and shadow objectives

The paper stage must produce sealed evidence for:

- execution-profile realism,
- Databento-to-IBKR bar parity,
- strategy-health drift,
- data-quality behavior,
- operating-envelope fit,
- account-fit under live-like conditions,
- and broker-reconciliation cleanliness.

The shadow-live stage must additionally produce sealed evidence for:

- production-account entitlements and permissions,
- contract conformance on the actual live lane,
- session-reset and reconnect behavior,
- suppressed or diverted order-mutation flow,
- and clean reconciliation and intent logging without economic mutations.

### 10.4 Operational evidence admissibility

Paper, shadow-live, and live evidence must declare one of four admissibility classes:

- `diagnostic_only`
- `execution_calibration_admissible`
- `risk_policy_admissible`
- `incident_review_only`

Paper, shadow-live, and live evidence may recalibrate **execution assumptions**, **data-quality expectations**, and **operating-envelope thresholds** only after:

- evidence sealing,
- reconciliation,
- minimum sample checks,
- and policy approval.

Operational evidence may **not** directly retune signal logic, rank parameters, or reorder lockbox finalists.

### 10.5 Paper and shadow exit criteria

A candidate may leave paper only if all of the following are true:

- replay certification still holds,
- portability certification still holds when required,
- native 1OZ validation holds when required,
- paper evidence sufficiency is met by sample quality, not just elapsed time,
- no unresolved reconciliation discrepancy blocks the next session,
- operating-envelope behavior is acceptable,
- strategy-health drift is within policy bounds,
- and a signed promotion packet authorizes shadow-live.

A candidate may leave shadow-live only if all of the following are true:

- the exact live data and broker connectivity lane have been exercised cleanly,
- shadow reconciliation and intent logging are clean,
- no unresolved permission, entitlement, contract-conformance, or session-reset issue remains,
- and a signed promotion packet authorizes live canary.

For overnight candidates, paper and shadow evidence must include overnight holds, overnight exits when applicable, and restart-while-holding scenarios.

### 10.6 Live promotion path

The first live activation path is:

1. `SHADOW_RUNNING`
2. review of shadow-live evidence
3. `LIVE_CANARY`
4. review of canary evidence
5. `LIVE_ACTIVE`

The canary stage must run with a more conservative operating envelope than ordinary live-active posture.

### 10.7 Operational runtime (`opsd`)

`opsd` is a single daemon composed of logically distinct modules:

- `market_data`
- `strategy_runner`
- `risk`
- `broker`
- `state_store`
- `reconciliation`
- `ops_http`

Session-readiness packet production and contract-conformance checks are coordinated by `reconciliation`, `risk`, and `broker` before a session is allowed to become tradeable.

A watchdog supervises `opsd`, `guardian`, and the broker gateway process.

`guardian` is intentionally separate from `opsd`. It has a much smaller code path and one responsibility: independently verify broker connectivity and, when authorized, execute emergency cancel/flatten actions even if `opsd`, the main database session, or the primary control plane is impaired.

### 10.8 Deterministic state ownership

Economically significant state follows a single-writer rule:

- `market_data` owns the latest normalized market state,
- `strategy_runner` owns per-bundle decision state,
- `risk` owns trading eligibility and exposure state,
- `broker` owns order-intent to broker-order mappings and broker-session state,
- `reconciliation` owns intraday mismatch assessments, end-of-day ledger-close assembly, and session-readiness evidence,
- `state_store` owns snapshots and the append-only journal,
- and `guardian` owns no strategy state; it owns only independently authorized emergency cancel/flatten actions and the evidence they produce.

Cross-module communication uses bounded mailboxes with explicit backpressure metrics. Cancel, flatten, and reconciliation work must have a reserved high-priority lane.

### 10.9 Broker capability descriptor and conformance

The IBKR adapter must publish a versioned capability descriptor covering:

- supported order types and TIFs,
- modify/cancel semantics,
- partial-fill and reject behavior,
- flatten support,
- session and maintenance behavior,
- message-rate limits,
- and exchange- or broker-specific constraints.

Every candidate bundle declares its required capabilities. Paper, shadow-live, and live require conformance against the active adapter.

Before any session becomes tradeable, the adapter must also pass contract-conformance checks against the active `product_profile` and resolved-context bundle. A mismatch in multiplier, tick size, exchange mapping, expiration, currency, or session definition blocks trading until reviewed.

### 10.10 Order-intent identity, idempotency, and duplicate-order prevention

Every economically significant broker mutation must be driven by a durable `order_intent_id`.

Requirements:

- `order_intent_id` is deterministic from deployment instance, decision sequence number, leg, side, and intent purpose,
- intent records are persisted before or atomically with the first broker submission attempt,
- submit/modify/cancel/flatten paths are idempotent across retry, restart, reconnect, duplicate callbacks, and operator repeat actions,
- the broker adapter maintains a durable mapping from `order_intent_id` to broker order ids, status versions, and last known acknowledgement state,
- if recovery cannot prove whether a mutation was applied, runtime must reconcile broker state first and default to no-resend plus halt/flatten according to policy,
- and adapter tests must include submit-timeout, acknowledgement loss, duplicate fill callback, reconnect-before-ack, cancel/replace race, and operator retry race scenarios.

### 10.11 Broker session recording and replay

The broker adapter must support fixture recording at the adapter interface level.

The fixture library must include at least:

- clean fill flow,
- partial fills,
- unsolicited cancel,
- reject after acknowledgement,
- disconnect/reconnect mid-order,
- daily reset and post-reset resume,
- contract-definition mismatch detection,
- and timeout with no response.

These fixtures are stored immutably and used in deterministic adapter tests.

### 10.12 Recovery fence and warm-up

On process start, reconnect, or watchdog restart, `opsd` enters `RECOVERING`.

In `RECOVERING`:

- no new entries are allowed,
- broker positions and open orders are reconciled,
- durable order-intent mappings are repaired or declared ambiguous before any broker mutation is allowed,
- local state is restored from the latest valid snapshot plus journal replay,
- ambiguities escalate to halt or flatten according to policy,
- strategy warm-up runs before tradeable signals are allowed,
- and, after any broker daily reset or material reconnect, a fresh green `session_readiness_packet` is required before entries may resume.

Warm-up data may come from prior operational evidence or, when insufficient, from the referenced dataset release. The warm-up source is recorded in the recovery artifact.

### 10.13 Graceful shutdown and restart

`opsd` must support deterministic graceful shutdown:

- stop new entries,
- drain or cancel outstanding intents according to policy,
- persist final snapshot, journal barrier, and digest frontier,
- record shutdown reason,
- and support restart from the latest verified snapshot.

### 10.14 Market-data and health degradation handling

The runtime must track:

- freshness watermarks,
- stale-quote rate,
- bar-construction parity degradation,
- connection status,
- clock skew and synchronization state,
- broker latency,
- and policy-engine health.

The runtime must also perform intraday broker-state reconciliation on a periodic and event-driven basis. At minimum, it must compare local versus broker:

- net position by symbol,
- working orders,
- last known fill ids,
- and current trading permissions/state.

Any unexplained mismatch above tolerance must trigger `restrict`, `exit-only`, or flatten/withdrawal according to policy rather than waiting for end-of-day reconciliation.

Degradation actions must be policy-driven and may include:

- `restrict` posture,
- entry suppression,
- no-new-overnight-carry,
- exit-only mode,
- or flatten and withdrawal.

### 10.15 Authoritative broker reconciliation and ledger close

Intraday broker API state is operationally useful for risk control but not authoritative for accounting.

Periodic and event-driven intraday reconciliation must compare local versus broker positions, working orders, fill ids, and current trading permissions. Any unexplained mismatch above tolerance blocks new entries immediately and escalates to review, waiver, or flatten according to policy.

At end of day, the platform must ingest the broker’s authoritative statement set and reconcile:

- positions,
- fills and execution ids,
- commissions and fees,
- cash movements,
- realized and unrealized PnL,
- and margin figures.

Any unexplained discrepancy above tolerance blocks new entries for the next session until reviewed, waived, or resolved.

Reconciliation writes a daily ledger-close artifact containing:

- ledger close date,
- as-booked PnL,
- as-reconciled PnL,
- discrepancy summary by class,
- restatement references,
- and next-session eligibility decision.

### 10.16 Backup, restore, and disaster recovery

Backup and restore are production requirements, not housekeeping tasks.

Requirements:

- canonical database backups and object-store checkpoints run on automated schedules with monitoring and alerting,
- snapshot/journal pairs are restorable to a clean host without manual data patching,
- restore procedures can rebuild enough state to re-enter `RECOVERING`, reconcile with the broker, and either resume safely or remain halted,
- restore drills use the latest certified artifacts, recent canonical backup material, and a simulated host-loss scenario,
- no live session may continue after a restore unless reconciliation is clean or an explicit reviewed waiver exists,
- and restore outcomes are sealed as operational evidence and retained for audit.

All backup, journal, and evidence retention used for live approval must be independently recoverable off-host. A single-host filesystem or same-VM volume does not satisfy the live-capable baseline, even if versioned locally.

Economically significant journal segments must be hash-chained, and each verified snapshot must record the journal digest frontier it covers. Restore drills must verify the digest chain before a recovered instance may re-enter `RECOVERING`.

RPO/RTO compliance and last successful restore-drill timestamps must be visible on the operator dashboard and checked by live-activation preflight.

---

## 11. Governance, policy, and observability

### 11.1 Policy engine

All lifecycle transitions, session-readiness checks, waivers, freshness checks, and promotion decisions are evaluated by a shared policy engine.

The engine must emit machine-readable decision traces including:

- policy bundle hash,
- inputs,
- evaluated rules,
- resulting decision,
- and waiver references.

No UI, notebook, or service may reimplement gate logic independently.

### 11.2 Lifecycle state machines and compatibility domains

Lifecycle state machines are defined in shared, machine-readable specs and consumed by:

- Python tooling,
- Rust runtime,
- SQL checks,
- CLI tooling,
- and dashboards.

Compatibility is handled by explicit domains rather than one monolithic protocol version. At minimum:

- data protocol,
- strategy protocol,
- ops protocol,
- policy bundle hash,
- and compatibility matrix version.

### 11.3 Solo governance mode

Because the platform is solo-operated, governance uses signed, time-separated self-attestations instead of fake dual control.

Required controls:

- two attestation steps separated by a cooling-off interval,
- signed checklist artifacts,
- explicit waiver expiry,
- and incident/corrective-action tracking.

### 11.4 Incidents and waivers

Every live-impacting exception requires either:

- a signed waiver with expiry and scope,
- or an incident record with corrective-action closure.

Waivers may not silently become permanent policy.

### 11.5 Observability

The platform must expose metrics and dashboards for:

- release counts and statuses,
- research funnel counts,
- discovery-budget consumption,
- portability, tradability, and replay pass rates,
- account-fit pass rates,
- bar-parity drift,
- session-readiness status and expiry windows,
- live quality events,
- strategy-health drift,
- broker latency and disconnects,
- intraday broker-state mismatch counts,
- guardian health and last emergency drill,
- policy-engine latency and failures,
- active waivers and expiry countdowns,
- backup freshness, journal-digest verification, and restore-drill status,
- clock-synchronization health,
- secret-rotation age and break-glass events,
- and deployment status counts.

The platform must also define alert classes and operator response targets for at least:

- open live position with degraded health,
- failed or stale session-readiness packet,
- intraday broker-state mismatch,
- backup freshness breach,
- restore-drill expiry,
- clock desynchronization,
- break-glass access,
- and inability to execute emergency flatten.

### 11.6 Upgrade and migration policy

Schema, runtime, snapshot/journal, and policy changes are versioned migrations, not informal edits.

Rules:

- every migration declares the affected compatibility domains and the required replay or recertification consequences,
- runtime startup performs hard compatibility checks across binary version, database schema, snapshot/journal format, policy bundle hash, and artifact compatibility matrix,
- no migration or runtime upgrade that can affect paper/shadow/live semantics may be deployed during an active session except under incident procedure,
- changing anything that can reinterpret bars, signals, risk behavior, or broker behavior requires deterministic replay recertification and may require new promotion packets,
- forward-only migrations are allowed only when backup/restore evidence proves recoverability,
- and every live-capable upgrade must have a documented rollback or restore path.

### 11.7 Monorepo structure

The monorepo should be organized roughly as:

- `python/research/` — ingestion, releases, orchestration, backtests, tuning, reporting
- `python/bindings/` — Python bindings for canonical Rust kernels
- `rust/kernels/` — canonical signal kernels and shared deterministic compute
- `rust/opsd/` — operational daemon
- `rust/guardian/` — minimal out-of-band emergency control process
- `rust/watchdog/` — supervisor and health automation
- `shared/schemas/` — Pydantic/Serde contracts and manifest definitions
- `shared/policy/` — declarative policy bundles
- `shared/state_machines/` — lifecycle specs
- `shared/fixtures/` — golden sessions, replay fixtures, broker sessions
- `sql/` — migrations and database constraints
- `infra/` — compose/systemd, monitoring, deployment configs
- `docs/runbooks/` — operator procedures and incident playbooks
- `tests/` — integration, property, regression, and conformance suites

---

## 12. Build phases and exit gates

### Phase 0 — foundation and QA (`v1_core_required`)

Build:

- monorepo bootstrap,
- environment locks,
- schema scaffold,
- policy engine scaffold,
- lifecycle state-machine specs,
- compatibility matrix,
- backup/restore scaffold,
- secret-delivery scaffold,
- clock-health probe,
- artifact indexing,
- journal-digest scaffold,
- golden-session test harness,
- property-based invariant harness,
- and end-to-end smoke tests.

Exit gate:

- empty or toy manifests are reproducible,
- state transitions are logged and queryable,
- startup compatibility checks are enforced,
- backup metadata, digest health, and secret-health probes are visible,
- contract tests pass,
- and the local stack boots and completes a round-trip.

### Phase 1 — raw archive and bitemporal reference (`v1_core_required`)

Build:

- Databento historical client,
- immutable raw archive,
- contract definition ingestion,
- calendar and event builders,
- roll-input builders,
- bitemporal reference store,
- and resolved-context compiler.

Exit gate:

- immutable raw data and bitemporal references are queryable,
- and deterministic resolved-context bundles compile for MGC and 1OZ.

### Phase 2 — validation and release pipeline (`v1_core_required`)

Build:

- structural validation,
- gap/anomaly classifiers,
- sidecar masks,
- normalized research catalog writer,
- `data_profile_release` compiler and publisher,
- release certification,
- prior-release diffing,
- canary backtests and parity fixtures where relevant,
- analytic release publisher,
- vendor-correction impact classifier,
- and lifecycle promotion tooling.

Exit gate:

- dataset, analytic, and data-profile releases can be certified, approved, activated, quarantined, and revoked with dependency propagation.

### Phase 2.5 — execution-lane vertical slice (`v1_core_required`)

Build:

- live-data entitlement checks,
- approved IBKR bar-construction pipeline,
- dummy or sentinel strategy running through `opsd`,
- paper-route smoke workflow,
- shadow-live suppression path,
- statement ingestion and reconciliation skeleton,
- contract-conformance checks,
- and preliminary 1OZ tradability diagnostics.

Exit gate:

- the platform can run an end-to-end non-economic paper/shadow session on the actual planned execution lane,
- session resets and broker reconnects are observed and documented,
- and the program either clears the 1OZ/IBKR viability gate or explicitly pivots.

### Phase 3 — simulation semantics and execution calibration (`v1_core_required`)

Build:

- screening/validation/stress execution profiles,
- regime-conditioned cost surfaces,
- calibration studies,
- execution-symbol-first viability screens,
- lower-frequency live-lane eligibility rules,
- and parity fixtures for research/live bar semantics.

Exit gate:

- at least one simple strategy class has documented admissible fidelity assumptions and initial 1OZ cost surfaces by session,
- and excluded strategy classes are explicitly listed.

### Phase 4 — research governance and baselines (`v1_core_required`)

Build:

- family preregistration,
- `research_run` registry,
- research budgets,
- `family_decision_record` workflow,
- null suite,
- family-level discovery accounting,
- program-level discovery ledger,
- lockbox workflow,
- omission tests,
- and power-analysis tooling.

Exit gate:

- the platform can decide whether a family deserves deeper budget without ad-hoc judgment.

### Phase 5 — first promotable strategy family (`v1_core_required`)

Build and validate one narrow subfamily that fits the live lane:

- bar-based,
- lower-frequency,
- plausibly portable from MGC to 1OZ,
- execution-symbol-viable on 1OZ,
- migrated to the canonical shared kernel before lockbox entry,
- and economically realistic for the $5,000 account profile.

Exit gate:

- the family either produces a defensible candidate region or is rejected for documented reasons.

### Phase 6 — candidate freezing and certification (`v1_core_required`)

Build:

- tuning workflow,
- candidate bundle registry,
- signal-kernel equivalence certification,
- promotion packets,
- session-readiness packet templates,
- replay certification,
- portability certification,
- native execution-symbol validation when required,
- execution-symbol tradability study workflow,
- and dependency revocation / correction-impact handling.

Exit gate:

- at least one candidate bundle is either fully certified for paper and shadow-live or rejected for reproducible reasons.

### Phase 7 — paper runtime and operational evidence (`v1_core_required`)

Build:

- `opsd`, `guardian`, and watchdog,
- live schedule compiler,
- IBKR supervision and readiness checks,
- live bar builder,
- idempotent order-intent journal and broker mapping layer,
- session-readiness packet issuance,
- operating-envelope enforcement,
- strategy-health drift monitor,
- evidence archive,
- internal accounting ledger,
- intraday broker-state reconciliation,
- authoritative broker reconciliation,
- and shadow-live non-economic routing controls.

Exit gate:

- paper and shadow-live run end to end,
- evidence is sealed and queryable,
- and next-session eligibility is governed by reconciliation, session readiness, and policy.

### Phase 8 — live-readiness and resilience (`v1_core_required`)

Build:

- fault-injection scenarios,
- broker-session replay fixtures,
- idempotent submit/modify/cancel race tests,
- recovery-fence tests,
- graceful shutdown/restart tests,
- restart-while-holding tests for overnight candidates,
- contract-conformance and daily-reset tests,
- guardian emergency drills,
- clock-drift fail-safe tests,
- backup/restore drills,
- journal-digest verification drills,
- migration rehearsal tests,
- break-glass and secret-rotation drills,
- and solo-governance live-approval workflow.

Exit gate:

- degradation modes, recovery paths, duplicate-order prevention, guardian behavior, reconciliation gates, session-readiness gates, restore/migration paths, credential controls, and incident workflows have been exercised in automated tests and documented.

### Phase 9 — continuation review (`v1_core_required`)

After the first full protocol cycle, run a signed continuation review.

Allowed outcomes:

- continue as-is,
- narrow scope,
- raise the minimum capital posture,
- change assumptions,
- switch the primary execution symbol,
- remain paper-only,
- add selected `v1_conditional` capabilities,
- or terminate the program.

No scope expansion is allowed without this review.

---

## 13. Definition of done

The first stack is “done” only when all of the following are true:

1. Historical data, reference data, analytic artifacts, and `data_profile_release` objects are published only through certified releases.
2. Point-in-time behavior is enforced by observation cutoffs, approved data-profile releases, and resolved-context bundles.
3. `research_run` and `family_decision_record` objects make the research funnel and budget decisions queryable and auditable.
4. The 1OZ/IBKR early execution-lane viability gate has been cleared or has produced a documented pivot decision.
5. A strategy family can be preregistered, screened, validated, stressed, tuned, and either rejected or frozen without ad-hoc evidence.
6. Frozen candidates are immutable bundles with explicit dependencies; concrete account binding occurs only through readiness records, promotion packets, and per-session readiness packets.
7. MGC-to-1OZ portability is certified when symbols differ, and execution-symbol tradability is explicitly studied rather than assumed.
8. Native 1OZ validation is required when enough history exists.
9. Research/live parity is certified through deterministic replay and the canonical shared signal kernel.
10. Paper and shadow-live deployments can run end to end through `opsd`, `guardian`, broker integration, evidence capture, and reconciliation.
11. Each tradeable session is gated by a green `session_readiness_packet` and contract-conformance checks.
12. Intraday broker-state reconciliation, operating-envelope controls, recovery fence, kill switch, and guardian emergency workflows function correctly.
13. End-of-day broker statements gate next-session eligibility.
14. Order submission, modification, cancellation, and flattening are idempotent across retry, restart, and reconnect, and ambiguous recovery paths default safely.
15. Off-host backup/restore drills, journal-digest verification, and migration procedures have been executed successfully against the live-capable stack.
16. Clock synchronization, secret delivery, break-glass controls, alerting, and operator response targets are enforced and observable.
17. At least one candidate has either:
    - been rejected for defensible reasons by the full protocol, or
    - passed paper and shadow-live and been approved for a controlled `LIVE_CANARY` deployment.

---

## 14. Honest limitations and expansion policy

### 14.1 Residual limitations of the first live stack

The first live stack will still have real limitations:

- IBKR market data is not a premium low-latency feed and IBKR session behavior remains an operational dependency,
- 1OZ liquidity is heterogeneous by session and may materially constrain viable strategy classes,
- bar-based logic will miss microstructure-dependent opportunities,
- the $5,000 / one-1OZ posture limits absolute-dollar opportunity,
- overnight operation remains riskier and operationally stricter than intraday-flat operation,
- and single-host operation still concentrates infrastructure risk even with `guardian` and off-host durability.

These are acceptable because the initial objective is **honest validation and safe operation**, not maximum sophistication.

### 14.2 Expansion rules

The platform may expand only after measured evidence supports it.

Examples:

- add a second live broker only after the first broker lane proves to be the bottleneck,
- add a second live market-data feed only after parity and live diagnostics show the existing feed is insufficient,
- add multi-host infrastructure only after the one-host topology fails live SLOs for infrastructure reasons,
- add sub-minute or depth-aware strategies only after the live stack is deliberately redesigned for them,
- and allow multiple active live bundles only after one-bundle live operation is stable and economically justified.

The continuation review is the only place where these upgrades may be authorized.

### 14.3 Pivot and termination triggers

The platform must explicitly authorize a pivot or termination when one of the following becomes true:

- the execution-symbol tradability study shows 1OZ is not reliably tradable for the intended family/session class,
- expected net fully loaded dollars at the approved live size remain de minimis across credible assumptions,
- broker/data operational friction dominates the available edge,
- or maintaining the live lane requires more operator time or capital than the approved program posture allows.

Approved pivots may include:

- narrowing to intraday-flat only,
- raising the minimum capital profile,
- switching the primary execution symbol,
- remaining paper-only,
- or terminating the program.
