---
title: "Production Plan for an MGC Backtesting, Tuning, and Validation Platform"
subtitle: "Revised full-system plan"
date: "March 22, 2026"
fontsize: 11pt
geometry: margin=0.85in
toc: true
toc-depth: 3
colorlinks: true
linkcolor: blue
urlcolor: blue
header-includes:
  - \usepackage{longtable}
  - \usepackage{booktabs}
  - \usepackage{array}
  - \usepackage{enumitem}
  - \setlist{itemsep=0.25em, topsep=0.35em}
  - \setlength{\parskip}{0.45em}
  - \setlength{\parindent}{0pt}
---

# Executive summary

This document replaces the earlier outline with a production-grade plan for an MGC research and backtesting platform. The system's job is not simply to run historical simulations. Its job is to make honest promotion decisions about MGC strategy families under realistic execution, point-in-time data, and tightly controlled research governance.

The platform answers three questions:

1. Which strategy families deserve further attention?
2. For candidates that survive initial screening, which parameter region is stable enough to justify deeper work?
3. After all filtering, does any candidate remain credible under realistic fills, stress assumptions, and a frozen final holdout?

This plan deliberately avoids building a custom backtesting kernel. The simulation core remains NautilusTrader's high-level `BacktestNode` plus `BacktestRunConfig` and `ParquetDataCatalog`. Everything else around it exists to prevent self-deception: raw data lineage, point-in-time contract handling, quality masks, fidelity calibration, walk-forward discipline, null baselines, promotion rules, lockbox evaluation, and paper-trading gates.

The result is a full finished product plan, not a prototype. It includes architecture, governance, data release workflow, validation rules, execution profiles, research controls, tuning rules, reporting requirements, project structure, milestone gates, and operational acceptance criteria.

\newpage

# 1. System purpose, scope, and non-negotiable principles

## 1.1 Purpose

The system is a production research platform for MGC (Micro Gold futures) strategies. It is optimized for identifying a small number of robust intraday or event-aware candidates, not for generating thousands of pretty equity curves.

The platform must support:

- large-scale family screening,
- higher-fidelity validation,
- staged parameter tuning,
- holdout protection,
- paper-trading readiness,
- and reproducible audit trails for every decision.

## 1.2 Scope

Initial scope is MGC on CME/COMEX with Databento historical data and NautilusTrader as the execution kernel. The design leaves room for related products such as GC as a reference or proxy signal source, but all order simulation for MGC strategies must map to real MGC contracts.

## 1.3 Non-negotiable principles

1. **Real contracts for execution.** Orders are never simulated on a fake tradable continuous series.
2. **Point-in-time everywhere.** Contract selection, roll maps, calendars, sessions, and reference data must be valid as of the simulated timestamp.
3. **Raw data is immutable.** Vendor responses are stored unchanged with manifests and hashes.
4. **Validation never edits history in place.** Suspicious data is classified with masks and eligibility rules, not overwritten after the fact.
5. **Screening is only acceptable if fidelity has been calibrated.** Families whose edge depends on intraminute microstructure must not be trusted on coarse bars without explicit evidence.
6. **Research degrees of freedom are counted.** Structural switches, anchor subsets, and subfamilies are tracked honestly.
7. **Test and lockbox results are not fed back into tuning.** Once touched, they are contaminated.
8. **No custom fill model without calibration evidence.** Complexity is not realism by default.
9. **Promotion requires degradation tolerance.** Candidates must survive worse assumptions, not just one optimistic profile.
10. **Paper trading is part of the finished product.** Historical backtests alone are not enough.

# 2. Hard architecture decisions

## 2.1 Core simulation kernel

The simulation kernel is NautilusTrader high-level backtesting:

- one `BacktestNode`,
- many `BacktestRunConfig` objects,
- one node per process,
- `ParquetDataCatalog` as the normalized research store.

The platform does not build a new execution engine unless a later audit proves that Nautilus cannot represent a required behavior.

## 2.2 Layered architecture

The finished platform has seven layers:

1. **Raw vendor archive**
2. **Point-in-time reference and calendar builders**
3. **Validation and classification**
4. **Normalized catalog releases**
5. **Analytic series and feature cache**
6. **Experiment orchestration and tuning**
7. **Reporting, governance, and deployment gates**

Each layer has explicit inputs, outputs, versions, and ownership.

## 2.3 Two data series by design

The platform formally separates:

- **Execution series**: real MGC contracts used by the matching engine and all simulated orders.
- **Analytic series**: explicitly versioned, point-in-time continuous or adjusted series used only for indicators or research features that need continuity across rolls.

An analytic series may influence signals. It may never be the instrument on which fills occur.

## 2.4 Delivery-aware contract policy

Because MGC is physically delivered, the platform enforces contract lifecycle rules. It never assumes a strategy may casually hold into notice or delivery windows. The default posture is intraday-flat. Overnight or multi-session holding must be explicitly enabled and is treated as a separate research regime with additional controls.

# 3. Architecture graph

The diagram below summarizes the production architecture and control flow.

![Production architecture graph](mgc_backtesting_architecture.png){ width=95% }

**Interpretation of the graph**

- The left side handles immutable inputs: raw Databento files, request manifests, and point-in-time reference data.
- The middle layers validate, classify, and publish dataset releases into a normalized research catalog.
- The research layer splits into an execution path (real contracts) and an analytic path (continuous research features).
- The orchestration layer builds experiments, drives NautilusTrader, and stores manifests, results, and diagnostics.
- Governance sits on the output side: hard gates, null comparisons, lockbox protection, and paper/shadow deployment.

\newpage

# 4. Market, contract, and platform assumptions

## 4.1 Instrument assumptions

The platform treats MGC as a physically delivered COMEX futures product with real contract months, real trading termination, and real session structure. That matters because:

- contract eligibility changes over time,
- front-month liquidity transitions matter,
- first-notice and delivery windows matter,
- and session behavior differs materially between overnight trade, London hours, 8:30 ET macro windows, and the U.S. cash-equity open.

## 4.2 Platform assumptions

The build assumes current official behavior of the following components:

- NautilusTrader `BacktestNode` high-level API and one-node-per-process constraint.
- Databento DEFINITION files must be loaded before market data is written to the Nautilus catalog.
- Bar execution in Nautilus expects `ts_init` at bar close for correct chronology.
- Queue-position and liquidity-consumption realism must be enabled deliberately when appropriate.
- SQLite is acceptable only for local, single-process Optuna studies and not for parallel or distributed optimization.

These assumptions are frozen into the engineering design until the next annual protocol review.

# 5. Data layer design

## 5.1 Storage tiers

The platform uses four storage tiers, not one.

### 5.1.1 Tier A - immutable raw vendor archive

This is the source-of-truth archive. It stores the exact Databento downloads as received.

Suggested layout:

```text
project/
  raw/
    databento/
      GLBX.MDP3/
        definition/
        trades/
        mbp1/
        mbo/
        ohlcv_1m/
    manifests/
      requests/
      releases/
```

Every request is accompanied by a manifest recording:

- dataset,
- schema,
- symbols and symbology mode,
- start/end UTC,
- request timestamp,
- quoted cost,
- file hashes,
- client/library versions,
- and storage path.

No file in the raw archive is edited in place.

### 5.1.2 Tier B - reference and point-in-time data

This tier contains reference material needed to interpret or constrain the market data:

- contract definitions,
- contract lifecycle table,
- CME holiday and shortened-session calendars,
- session templates,
- macro event calendar normalized to UTC,
- daily cleared volume,
- daily open interest if used,
- roll-rule inputs,
- and any exchange status or session-status reference streams if available.

### 5.1.3 Tier C - normalized research catalog

This is the Nautilus `ParquetDataCatalog`. It stores normalized Nautilus objects for real contracts only:

- instruments,
- bars,
- quote ticks,
- trade ticks,
- depth data if available.

This tier exists for high-throughput simulation, not as the immutable raw layer.

### 5.1.4 Tier D - derived analytics

This tier stores items derived from released catalog data:

- point-in-time continuous analytic series,
- feature cache,
- precomputed session masks,
- anchor schedules,
- validation sidecars,
- and walk-forward fold definitions.

Derived data is versioned and can always be rebuilt from lower tiers.

## 5.2 Release model

Data becomes usable only through a formal **dataset release**.

Each release has:

- `dataset_release_id`
- `raw_input_hashes`
- `reference_version`
- `validation_rules_version`
- `catalog_version`
- `feature_version`
- `created_at_utc`
- `approved_by`
- `notes`

Backtests never point to ad-hoc files. They point to a dataset release.

## 5.3 Point-in-time requirement

Any reference item that could vary over time must be modeled point-in-time, including:

- active-contract map,
- contract lifecycle status,
- event calendar revisions if applicable,
- session masks,
- quality eligibility masks,
- and any volume/open-interest-based roll rule.

# 6. Ingestion pipeline and release workflow

## 6.1 Workflow summary

The production ingestion pipeline is:

1. Quote request cost and build request manifest.
2. Download raw DBN files and DEFINITION files.
3. Compute file hashes and store immutable raw assets.
4. Decode raw files to Nautilus objects in staging.
5. Run validation and classification.
6. Write sidecar masks and validation reports.
7. Write validated objects to a staging catalog.
8. Build derived reference outputs and feature prerequisites.
9. Promote the staging dataset to a formal release if all release gates pass.
10. Publish the `dataset_release_id`.

## 6.2 Required manifests

At minimum, every ingestion batch stores:

- request manifest,
- raw file checksum manifest,
- staging validation report,
- release approval record,
- and a machine-readable summary of exclusions or restricted periods.

## 6.3 Instrument definitions first

Instrument definitions are loaded before any market data is written to the Nautilus catalog. If the corresponding DEFINITION data is missing, the batch fails.

## 6.4 Vendor correction handling

If the vendor corrects history:

- the corrected raw files are stored as a new raw asset set,
- the validation pipeline is rerun,
- a new dataset release is created,
- and old releases remain reproducible and queryable.

No prior release is silently rewritten.

# 7. Validation and classification framework

## 7.1 Philosophy

Validation exists to classify data honestly, not to sanitize it until the backtest looks better.

The validator must distinguish at least four broad categories:

1. **Valid tradable history**
2. **Valid but hazardous history** (for example wide spread or stale quotes)
3. **Valid but strategy-ineligible history** (for example shortened session if a strategy opts out)
4. **Invalid history** (for example broken ordering, malformed timestamps, missing required definitions)

The output is a set of sidecar masks, reports, and release gates.

## 7.2 Structural checks

Structural checks include:

- file readability,
- schema consistency,
- symbol/instrument mapping integrity,
- monotonic timestamp checks where applicable,
- duplicate or overlapping chunks,
- incomplete DEFINITION coverage,
- and catalog write/read round-trip checks.

Any structural failure is a release blocker.

## 7.3 Session modeling checks

The validator must know the expected session status for every trading day:

- full session,
- shortened session,
- exchange closed,
- normal daily maintenance break,
- emergency close or irregular session.

This session status becomes part of the eligibility mask consumed by strategies.

## 7.4 Gap classification

Gap detection must be event-aware and data-type-aware.

For bars, quotes, and trades, the validator classifies gaps as:

- scheduled closed period,
- scheduled maintenance break,
- shortened session gap,
- true no-trade interval,
- vendor acquisition gap,
- transport or decoding gap,
- contract not listed or not eligible yet.

A missing one-minute bar is not automatically bad data. For trade-derived bars, the validator must distinguish "no trade occurred" from "data is missing."

## 7.5 Price anomaly classification

The validator flags suspicious observations using time-of-day and event-aware baselines. Examples include:

- extreme high-low range relative to a robust rolling baseline,
- close or last trade far from prior close without corroborating quotes or related instruments,
- impossible or negative spread states,
- out-of-order quote timestamps,
- repeated stale quote periods,
- crossed or locked quotes persisting beyond tolerance,
- and order book integrity breaks if L2 or MBO is present.

A suspicious observation is **classified**, not deleted.

Recommended status labels:

- `valid`
- `valid_event_spike`
- `hazard_wide_spread`
- `hazard_stale_quote`
- `suspect_bad_print`
- `invalid_timestamp_order`
- `invalid_schema_or_mapping`

## 7.6 Event-aware thresholds

Thresholds around known macro windows and session opens must differ from quiet overnight thresholds. A 50-tick jump may be absurd at one time of day and entirely real at another.

Therefore the validator uses:

- a time-of-day baseline,
- an event-window multiplier,
- and optional cross-checks against GC or the quote stream.

## 7.7 Sidecar masks, not in-place rewrites

The normalized catalog stores the original normalized data. Validation outputs live beside it:

- bar validity mask,
- quote hazard mask,
- session eligibility mask,
- event-window hazard mask,
- contract eligibility mask.

Strategies and experiment configs decide how to consume those masks. They do not alter history after the fact.

## 7.8 Interpolation policy

Interpolation is allowed only for explicitly marked **indicator warm-up channels** when a strategy is not yet tradable and only if the warm-up logic uses a separate non-execution feed. Interpolated values may never drive simulated order generation or fill logic.

## 7.9 Session quality tiers

Each session receives a quality tier:

- **Tier A**: full confidence
- **Tier B**: tradable but flagged hazards exist
- **Tier C**: usable only for analytics or excluded entirely
- **Tier X**: invalid

Strategies declare which tiers they accept.

## 7.10 Manual review protocol

Manual review is allowed only at the **dataset release** level, never at the "this one backtest looks great" level.

Rules:

- reviewer sees the data issue and supporting evidence,
- reviewer does not see strategy PnL or rank,
- reviewer records one of a small set of allowed reason codes,
- any systematic issue should become a rule change in the next validation-rules version,
- and the exception ledger is stored with the release.

# 8. Time, sessions, and calendar handling

## 8.1 UTC as source of truth

All stored timestamps, manifests, and schedule objects are UTC. ET exists only in:

- human-readable configuration,
- labels in reports,
- and the source event definitions before they are compiled.

## 8.2 Anchor compilation

Strategies may think in ET anchors such as:

- London-open proxy anchor,
- 8:30 ET macro release,
- 9:30 ET U.S. cash-equity open.

These anchors are not implemented with ad-hoc clock math inside strategies. They are compiled ahead of each run into UTC schedule objects that already account for daylight saving changes and irregular sessions.

## 8.3 Session identifier

The platform defines a session identifier consistent with the exchange trading day, not the wall-clock date at midnight. This avoids common errors around Globex sessions that begin on one calendar day and end on the next.

## 8.4 DST tests

A permanent regression suite must cover:

- spring DST transition,
- fall DST transition,
- the week before and after both,
- and ET-anchored timers spanning those transitions.

## 8.5 Bar timestamp correctness

When bars are used for execution, the platform enforces the rule that `ts_init` must represent the bar close. If the source timestamps bars at the open, the ingestion path shifts them or sets the appropriate `ts_init_delta`. A dataset release fails if bar timestamp convention is unknown.

# 9. Contract lifecycle, active-contract mapping, and roll policy

## 9.1 Default posture

The default posture for MGC research is:

- intraday-flat,
- no position carried across the session close,
- no carry through notice or delivery risk windows,
- and no trade entry in forced-flat blackout periods.

This default reduces unnecessary complexity while remaining honest about a physically delivered contract.

## 9.2 Contract eligibility model

Every contract has a timestamped eligibility state:

- `not_listed`
- `listed_not_primary`
- `trade_allowed`
- `close_only`
- `forced_flat`
- `expired`

Strategies may only submit new orders when the state is `trade_allowed`.

## 9.3 Point-in-time active-contract selection

The active-contract map is built from lagged information. It may use:

- previous-session cleared volume,
- previous-session open interest if publication lag is respected,
- and fixed calendar fallback rules.

It may **not** use same-day full-session volume or open interest that would not have been known at the decision time.

## 9.4 Hysteresis rule

To avoid constant flipping between nearby contracts, the active-contract selection uses a deterministic hysteresis rule. A suggested first version is:

- remain on the current contract until the candidate next contract has exceeded the current contract on the chosen liquidity metric for a configurable number of consecutive eligible sessions,
- then switch at a predetermined handoff time before the next session opens.

The exact rule is frozen per research protocol version.

## 9.5 Hard delivery fences

Liquidity rules never override hard lifecycle fences. If the contract has reached the platform's delivery-blackout threshold, the system forces flat and blocks new entries regardless of measured liquidity.

## 9.6 Segment-based backtesting

A multi-month experiment is executed as a set of contract segments:

- each segment maps to a real contract,
- flatten or switch happens at the segment boundary,
- and all segment-level reports roll up to one experiment result.

## 9.7 Analytic continuous series

For longer-horizon indicators or context features, the platform may build a point-in-time continuous analytic series. This series is versioned and traceable to the contract segments from which it was built. It may never be treated as the tradable instrument.

# 10. Reproducibility, provenance, and software governance

## 10.1 Environment pinning

The finished product includes a fully pinned environment:

- Python version,
- NautilusTrader version,
- Databento client version,
- Optuna version,
- timezone database version,
- OS/container image,
- and any custom package versions.

## 10.2 Deterministic run manifest

Every backtest run writes a manifest containing:

- `run_id`
- `dataset_release_id`
- `family_id`
- `subfamily_id`
- `config_hash`
- `execution_profile_id`
- `fold_set_id`
- `random_seed`
- `code_commit`
- `environment_fingerprint`

## 10.3 Golden-session regression suite

The system ships with a regression suite of hand-audited sessions covering:

- quiet overnight trade,
- London hours,
- 8:30 ET event windows,
- 9:30 ET open,
- roll boundaries,
- shortened sessions,
- DST transitions,
- and forced-flat lifecycle windows.

Any engine, validation, or calendar change must pass this suite before release.

## 10.4 Artifact retention

The platform keeps:

- machine summaries for every run,
- full fills/positions/account artifacts for promoted runs,
- and failure diagnostics for batches that crash or fail eligibility checks.

## 10.5 Resume and replay

A batch can be resumed from its manifest without recomputing successful runs. Any run can be replayed exactly from its manifest and dataset release.

# 11. Simulation kernel and execution profiles

## 11.1 Kernel usage model

The batch runner builds many `BacktestRunConfig` objects and executes them through NautilusTrader. One node runs per process. For parallelism, the orchestrator uses multiple subprocesses or workers, each with its own node and isolated artifact path.

## 11.2 Fidelity calibration profile

Before trusting bar-based screening for any new family, the platform runs a **fidelity calibration study**.

This profile compares the same strategy logic on:

- screening bars,
- a finer-grained series,
- quotes or trades,
- and, where available, depth.

The output measures:

- signal timing drift,
- trade-count drift,
- fill-quality drift,
- and PnL drift.

A family is allowed to use coarse screening only if the drift is below a predefined tolerance.

## 11.3 Execution profiles

| Profile | Purpose | Minimum data | Key assumptions |
|---|---|---|---|
| `mgc_screening_profile` | Broad family screening | 1-minute bars or higher, only after fidelity approval | realistic fees, conservative bar ordering, no uncalibrated passive-fill optimism |
| `mgc_validation_profile` | Higher-fidelity candidate validation | quotes/trades; depth if available | stricter slippage, explicit latency, queue realism where supported |
| `mgc_stress_profile` | Adversarial but plausible sanity check | same as validation or best available | worse fills, wider spread/slippage, higher fees, latency bump, stricter entry timing |
| `mgc_fidelity_profile` | Compare coarse vs higher-fidelity representations | paired datasets | diagnostic only, not for ranking |
| `mgc_paper_shadow_profile` | Pre-live shadow verification | live or replayed production feed | same logic and risk envelope intended for paper or live |

## 11.4 Screening profile rules

The screening profile is allowed to be cheaper, but not dishonest. It must:

- use realistic exchange fee assumptions,
- use `bar_adaptive_high_low_ordering=True` when bars drive execution,
- explicitly document order-type restrictions,
- avoid claiming queue realism on data that cannot support it,
- and refuse families whose fidelity calibration says one-minute bars are too coarse.

## 11.5 Validation profile rules

The validation profile adds realism:

- quote/trade or depth inputs,
- latency model,
- stricter slippage,
- liquidity consumption enabled when supported,
- queue-position tracking enabled when the data and execution mode can support it,
- and stronger protection against passive-fill optimism.

## 11.6 Stress profile rules

The stress profile is not an optimization target. It is a falsification layer. Typical perturbations include:

- one to two ticks worse execution,
- higher fees,
- stricter latency,
- more conservative passive-fill outcomes,
- and minor roll-handoff variation.

## 11.7 Custom fill model policy

No custom MGC fill model is shipped in v1 unless calibrated using evidence from paper or live fill logs. Until then, the platform relies on NautilusTrader's native mechanisms plus documented, conservative parameterization.

# 12. Strategy interface and base risk envelope

## 12.1 Strategy contract

Every strategy is a normal Nautilus `Strategy` subclass plus a registry record with explicit metadata. The metadata must declare:

- family and subfamily,
- economic hypothesis,
- required data types,
- minimum data fidelity,
- accepted session-quality tiers,
- order types used,
- risk envelope,
- and failure criteria.

## 12.2 Base algorithm configuration

Minimum required configuration fields:

```text
instrument_selector_name
trade_size
max_position
warmup_bars
anchor_calendar_name
session_filter_name
quality_mask_policy_name
roll_policy_name
risk_limits_name
allow_overnight
forced_flat_time
signal_source_name
```

## 12.3 Required risk controls

Every strategy must inherit the same baseline controls unless explicitly waived:

- maximum position size,
- maximum entries per anchor,
- maximum daily trades,
- cooldown after stop-out,
- session flatten cutoff,
- emergency kill switch,
- and order-type whitelist.

## 12.4 Execution versus analytics inputs

Strategies may consume both:

- execution series inputs from the real active contract,
- and analytic features from the continuous research series.

Any feature that comes from the analytic series must be logged in the run manifest so later audits can see exactly what influenced the signal.

# 13. Strategy families, subfamilies, and research governance

## 13.1 Family decomposition rule

A broad family is not treated as one hypothesis if it contains materially different structure. Structural choices become separate subfamilies.

Examples:

- 8:30 ET opening-range breakout is a different subfamily from 9:30 ET opening-range breakout.
- Macro continuation is a different subfamily from macro fade.
- Session-open VWAP reversion is a different subfamily from macro-anchor VWAP reversion.
- Changing anchor subset or bar size is a new model specification, not merely a robustness perturbation.

## 13.2 Required pre-registration fields

Before testing a new subfamily, the researcher writes:

- what behavior is being exploited,
- why MGC or GC should plausibly exhibit it,
- what data fidelity is required to test it honestly,
- what would disconfirm it,
- and how many structural variants are being counted against the research budget.

## 13.3 Research budget

Each family and subfamily receives a budget:

- maximum number of structural variants,
- maximum number of coarse parameter configurations before abandonment,
- and maximum tuning budget before promotion or shutdown.

This keeps "keep searching until something works" from masquerading as rigor.

## 13.4 Null suite

The finished platform includes a null suite, not just one random strategy.

Required nulls:

- random entry with many seeds and the same risk envelope,
- time-shifted anchor null,
- side-flipped or entry-ablated null,
- and an exit-only null where appropriate.

A real candidate must separate from the null distribution under the same execution assumptions.

## 13.5 Initial family groups

The first production family groups are:

### Group A - opening-range breakout

Separate subfamilies:

- `eorb_london_v1`
- `eorb_0830_v1`
- `eorb_0930_v1`

Each subfamily may vary opening-range length, confirmation mode, stop mode, exit mode, and re-entry rules, but those structural modes are counted and budgeted honestly.

### Group B - anchored VWAP mean reversion

Separate subfamilies:

- `vwap_session_open_v1`
- `vwap_macro_anchor_v1`

### Group C - macro impulse

Separate subfamilies:

- `macro_continuation_0830_v1`
- `macro_fade_0830_v1`

This group is not eligible for coarse one-minute screening unless fidelity calibration approves it.

## 13.6 Failure criteria

Each subfamily must publish explicit failure criteria before testing. Examples include:

- insufficient trade count,
- no parameter neighborhood with positive out-of-sample expectancy after costs,
- inability to separate from null strategies,
- or collapse under the validation or stress profile.

# 14. Walk-forward protocol and evaluation hierarchy

## 14.1 Clean hierarchy

The finished platform uses four evaluation zones:

1. **Development train**
2. **Inner validation**
3. **Outer test for model selection**
4. **Project lockbox**

After a candidate survives all four, it enters paper/shadow trading.

## 14.2 Default fold structure

Initial default, frozen at the protocol level:

- train window: 12 months
- inner validation: 4 months
- outer test: 4 months
- step size: 4 months
- warm-up: 30 trading days
- embargo: 1 full session at each boundary for state cleanup and no cross-boundary carry

These defaults are changed only in scheduled protocol reviews, not because one family happened to look better under another split.

## 14.3 Regime diagnostics

The platform computes regime diagnostics independent of strategy performance:

- realized volatility by time-of-day bucket,
- median spread,
- book depth where available,
- trade count,
- bar range distribution,
- session volume,
- stale-quote frequency,
- event-window jump statistics.

These diagnostics warn about regime drift. They do not automatically retune the protocol mid-study.

## 14.4 Parameter stability requirement

A candidate cannot be promoted based on one isolated parameter point. It must show a stable local region. The minimum requirement is that adjacent configurations in the chosen neighborhood remain acceptable on the outer tests.

## 14.5 Block-bootstrap confidence intervals

The reporting layer computes block-bootstrap intervals for key out-of-sample metrics. These are diagnostic, not proof, but they help distinguish broad stability from one lucky path.

## 14.6 Lockbox policy

The lockbox is a recent, untouched window reserved for the final selected candidate set. It is opened exactly once for each selected candidate after all family selection and tuning are complete. Results from the lockbox are never used to retune the candidate.

# 15. Screening, promotion, and selection logic

## 15.1 Tier 1 screening

Tier 1 performs broad subfamily screening using approved coarse fidelity. It answers one question: is this subfamily worth spending more realism and tuning budget on?

## 15.2 Hard promotion gates

A candidate must pass all hard gates before promotion:

- minimum total out-of-sample trades,
- positive median outer-test expectancy after costs,
- minimum profit factor after costs,
- maximum drawdown within limit,
- no unacceptable concentration in one month or one fold,
- positive result under stress profile,
- and statistically meaningful separation from the null suite.

Thresholds are parameterized at the protocol level and versioned.

## 15.3 Selection ranking

The first production version uses **hard gates plus Pareto ranking**, not an arbitrary weighted composite score.

Primary axes:

- median outer-test expectancy per trade,
- drawdown,
- cost sensitivity,
- parameter stability,
- trade-count sufficiency,
- and degradation from screening to validation.

A weighted composite may be introduced later only if it is frozen before future studies and calibrated without peeking at protected evaluation sets.

## 15.4 Manual audit checklist

Manual inspection is allowed only for:

- bug detection,
- pathological trade patterns,
- suspicious concentration,
- roll-boundary errors,
- obvious calendar mistakes,
- or implausible fill sequences.

It is not allowed to rescue or reject a strategy because the equity curve "looks nice" or "feels wrong."

# 16. Tuning architecture

## 16.1 Preconditions

The tuner is built only after a subfamily survives:

- screening,
- validation,
- stress,
- null comparison,
- and manual audit.

If nothing survives, the correct action is to abandon or replace the subfamily rather than to build a more complicated tuner.

## 16.2 Tuning stages

### Stage 1 - local search around a real region

Define a bounded local search around the promoted region. Structural switches remain fixed unless a new subfamily is being created.

### Stage 2 - robustness perturbation search

Retest top trials under environmental perturbations such as:

- worse fills,
- higher fees,
- latency increase,
- alternate point-in-time roll handoff,
- slightly different stop/entry protection assumptions.

Changing anchor subset or bar size is not a perturbation. It is a new model specification.

### Stage 3 - candidate freeze and lockbox

Freeze the candidate and evaluate it once on the project lockbox.

## 16.3 Pruning design

Since backtests do not emit natural epochs like ML training, each Optuna trial is staged:

1. short representative subset of folds,
2. intermediate score,
3. prune weak trials,
4. expand survivors to larger fold sets,
5. only strong survivors reach the full development set.

## 16.4 Storage policy

Storage rules:

- SQLite is allowed for local, single-process development studies.
- PostgreSQL is required for serious parallel or distributed tuning.
- Full artifacts live outside the study database in a run-artifact store.
- Each trial stores enough metadata to reproduce the exact run.

## 16.5 Randomness control

Any probabilistic fill or sampling process must use explicit seeds. The tuner records those seeds. If a trial depends heavily on stochastic fill outcomes, the platform may require repeated seeded replicas before promotion.

# 17. Reporting and custom metrics

## 17.1 Standard reports

Every promoted run receives:

- fills report,
- positions report,
- account report,
- trade list,
- outer-fold summary,
- month-by-month attribution,
- and a research tearsheet.

## 17.2 MGC-specific metrics

The platform computes and stores:

- PnL in ticks per contract,
- slippage in ticks versus intended price,
- passive-entry fill rate,
- expectancy by anchor type,
- expectancy by weekday,
- expectancy by post-anchor time bucket,
- MAE and MFE in ticks,
- performance around contract-roll blackout days,
- degradation from screening to validation,
- degradation from validation to stress,
- and quality-mask overlap for each trade.

## 17.3 Concentration diagnostics

The platform explicitly checks whether a result is dominated by:

- one fold,
- one month,
- one anchor type,
- one contract segment,
- or a handful of outlier sessions.

## 17.4 Null comparison diagnostics

Every promoted candidate is plotted against the null distribution:

- percentile rank versus null expectancy,
- percentile rank versus null drawdown-adjusted returns,
- and sensitivity to transaction-cost perturbations.

## 17.5 Paper-versus-backtest diagnostics

Once a candidate reaches shadow or paper trading, the system compares:

- signal timing drift,
- missed fill rate,
- live spread and slippage versus assumed spread and slippage,
- and session eligibility differences.

# 18. Batch runner and orchestration layer

## 18.1 Responsibilities

The orchestration layer owns:

- experiment manifests,
- fold generation,
- contract segmentation,
- profile selection,
- batch chunking,
- subprocess scheduling,
- resume and retry,
- and artifact collection.

## 18.2 Manifest-first design

No run starts until its manifest exists. The manifest defines exactly:

- which dataset release is used,
- which strategy spec is used,
- which folds are used,
- which contract segments are used,
- which profile is used,
- which seed is used,
- and where artifacts will be stored.

## 18.3 Chunking and process model

Large batches are chunked. Each worker process owns:

- one `BacktestNode`,
- one temporary working area,
- one artifact namespace.

This avoids singleton-state conflicts and simplifies memory cleanup.

## 18.4 Failure handling

Batch failure behavior:

- a failed run is marked with an error code,
- completed runs remain durable,
- and reruns only re-execute failed or invalidated items.

## 18.5 Feature caching

Any expensive derived feature that is invariant across many parameter sets may be cached by dataset release, contract segment, session filter, and feature version. Cache usage is recorded in the manifest.

# 19. Paper-trading and deployment gate

## 19.1 Paper stage is mandatory

No candidate is considered production-ready until it passes a paper or shadow stage.

## 19.2 Paper-stage objectives

The paper stage validates:

- session schedule correctness,
- timer correctness,
- live contract selection,
- live event-calendar alignment,
- slippage and spread assumptions,
- and operational runbook quality.

## 19.3 Paper-stage exit criteria

A candidate exits paper only if:

- there are no critical scheduling or lifecycle errors,
- live-versus-backtest slippage is within tolerance,
- no unacceptable fill-model optimism is observed,
- and the strategy obeys the same risk envelope used in research.

## 19.4 Live readiness review

A separate live-readiness review signs off:

- runbooks,
- emergency controls,
- operational alerts,
- daily health checks,
- and a reconciliation checklist.

# 20. Project structure

```text
project/
  raw/
    databento/
    manifests/
      requests/
      releases/
  reference/
    calendars/
    contract_lifecycle/
    roll_inputs/
    roll_rules/
  catalog/
    releases/
    staging/
  analytic/
    continuous_series/
    feature_cache/
    masks/
    folds/
  data_ingest/
    ingest_databento.py
    build_reference_data.py
    build_roll_map.py
    validate_data.py
    publish_release.py
  strategies/
    base.py
    mgc_session_base.py
    group_a/
    group_b/
    group_c/
    nulls/
  experiments/
    registry.py
    family_tracker.py
    fold_builder.py
    batch_builder.py
    execution_profiles.py
    promotion_rules.py
    manifest_io.py
    subprocess_runner.py
  tuning/
    search_spaces.py
    objective.py
    optuna_runner.py
    robustness_checks.py
  reports/
    postprocess.py
    custom_stats.py
    null_comparison.py
    walk_forward_diagnostics.py
    paper_vs_backtest.py
  deployment/
    paper/
    runbooks/
    alerts/
  tests/
    golden_sessions/
    regression/
    integration/
  results/
    manifests/
    runs/
    summaries/
    studies/
    paper_logs/
  docs/
    protocol_versions/
    decision_logs/
```

# 21. Milestone-based build order for the finished product

## Phase 0 - foundation and QA

Build:

- environment lock and container,
- manifest schema,
- golden-session test scaffold,
- config hashing,
- and artifact retention layout.

**Exit gate:** reproducible empty or toy run manifests and regression harness exist.

## Phase 1 - raw archive and reference builders

Build:

- Databento request client,
- raw DBN archive,
- DEFINITION ingestion,
- contract lifecycle builder,
- CME session/holiday reference,
- macro event calendar builder,
- roll-input data builder.

**Exit gate:** immutable raw archive plus reference tables are versioned and queryable.

## Phase 2 - validation and dataset release pipeline

Build:

- structural validation,
- gap and anomaly classifiers,
- sidecar masks,
- session quality tiers,
- staging catalog writer,
- release promotion tool.

**Exit gate:** at least one released dataset passes validation and can be recreated exactly.

## Phase 3 - simulation semantics and fidelity calibration

Build:

- execution profiles,
- bar timestamp correctness checks,
- fidelity calibration study,
- roll segmentation runner,
- and regression cases for DST, event windows, and forced-flat boundaries.

**Exit gate:** at least one simple strategy has been compared across bar and higher-fidelity representations, and the allowed screening fidelity is documented.

## Phase 4 - baselines and null suite

Build:

- random-entry nulls,
- time-shifted anchor null,
- side-flipped or ablated nulls,
- reporting against null distributions.

**Exit gate:** a baseline null distribution exists for the current protocol version.

## Phase 5 - first production candidate subfamily

Build and test one narrow subfamily first, not a giant family tree. Recommended first target:

- `eorb_0930_v1` or `eorb_0830_v1`

This phase includes:

- strategy implementation,
- coarse parameter neighborhood,
- failure criteria,
- screening, validation, stress, null comparison,
- and manual audit.

**Exit gate:** either a candidate survives honestly or the subfamily is abandoned.

## Phase 6 - selection governance and reporting

Build:

- hard gates,
- Pareto ranking,
- concentration diagnostics,
- parameter stability checks,
- block-bootstrap reporting,
- lockbox workflow.

**Exit gate:** the platform can make and document a promotion decision without ad-hoc judgment.

## Phase 7 - tuning system

Build only if a subfamily survives Phase 6.

Build:

- Optuna objective,
- staged pruning,
- trial artifact storage,
- robustness perturbations,
- candidate freeze workflow.

**Exit gate:** a tuned candidate exists without contamination of the lockbox.

## Phase 8 - additional subfamilies

Add more subfamilies only after the harness has proven it can reject bad ideas cleanly.

**Exit gate:** comparative family research is possible with honest budgeting and tracking.

## Phase 9 - paper and shadow deployment

Build:

- live schedule compiler,
- paper-trade runner,
- daily health checks,
- backtest-versus-paper comparison reports,
- runbooks and alerts.

**Exit gate:** at least one candidate completes a paper stage without critical operational or realism failures.

# 22. Definition of done

The platform is considered complete only when all of the following are true:

1. Raw vendor files, manifests, and dataset releases are reproducible.
2. Validation uses sidecar masks and session-quality tiers rather than PnL-driven edits.
3. Contract selection and roll handling are point-in-time and delivery-aware.
4. Screening fidelity is justified by explicit calibration.
5. Null comparisons, hard gates, and lockbox rules are implemented.
6. Every run has a manifest and reproducible artifact path.
7. Golden-session regression tests cover DST, event windows, roll boundaries, and forced-flat logic.
8. At least one candidate has completed the full chain:
   screening -> validation -> stress -> lockbox -> paper.
9. Runbooks and operational checks exist for paper deployment.
10. The system can reject a family cleanly without requiring more complexity.

# 23. Honest limitations and residual risks

No backtesting platform can prove that an edge is real. It can only reduce the number of ways the researcher can fool themselves.

Residual risks include:

- family-selection bias,
- unmodeled live latency or queue dynamics,
- vendor corrections after the fact,
- incomplete event metadata,
- regime shifts that invalidate old observations,
- paper-to-live divergence,
- and thin-liquidity behavior in overnight MGC sessions.

The platform therefore treats every positive result as provisional. Promotion means "worth further scrutiny," not "safe to trade."

# Appendix A - protocol source notes

This plan is aligned with current official documentation and exchange references as of March 22, 2026. The most important external assumptions were checked against:

- NautilusTrader documentation for `BacktestNode`, `BacktestRunConfig`, one-node-per-process constraints, bar timestamp handling, and execution realism settings.
- NautilusTrader Databento integration guidance requiring DEFINITION files before writing market data to the catalog.
- CME Group Micro Gold product overview, contract specifications, and calendar pages for product characteristics, lifecycle, and session conventions.
- Optuna documentation regarding storage choices and SQLite limitations for parallel optimization.

# Appendix B - implementation priorities in one page

If engineering time becomes tight, preserve these items first:

1. raw archive and release manifests,
2. point-in-time contract eligibility and hard delivery fences,
3. sidecar validation masks,
4. fidelity calibration,
5. null suite and hard promotion gates,
6. lockbox discipline,
7. paper stage.

These items do more to protect research integrity than any additional dashboard, fancy score, or custom fill model.