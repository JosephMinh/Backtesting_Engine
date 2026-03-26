"""Non-negotiable principles encoded as machine-readable program guardrails.

Each principle carries a stable ID, violation type, and reason code so that
downstream policy rules, contract tests, and operator-facing rejection logs
can reference concrete enforcement evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@unique
class PrincipleID(Enum):
    """Stable identifiers for the 15 non-negotiable principles."""

    P01_NO_CUSTOM_MATCHING_ENGINE = "P01"
    P02_NO_ADHOC_FILES = "P02"
    P03_NO_MUTABLE_REF_AFTER_FREEZE = "P03"
    P04_NO_GROSS_PNL_PROMOTION = "P04"
    P05_NO_NOTEBOOK_ONLY_EVIDENCE = "P05"
    P06_NO_LIVE_WITHOUT_FULL_EVIDENCE = "P06"
    P07_NO_STATE_AMBIGUITY = "P07"
    P08_NO_HIDDEN_OPTIMIZATION = "P08"
    P09_NO_PREMATURE_INFRA = "P09"
    P10_NO_RESEARCH_LIVE_FORK = "P10"
    P11_NO_BROKER_MUTATION_WITHOUT_INTENT = "P11"
    P12_NO_LIVE_WITHOUT_RECOVERABILITY = "P12"
    P13_NO_DEEP_BUDGET_BEFORE_VIABILITY = "P13"
    P14_NO_SESSION_WITHOUT_READINESS = "P14"
    P15_NO_SINGLE_PATH_EMERGENCY = "P15"


@unique
class ViolationType(Enum):
    """Categories of guardrail violations.

    Each maps to one or more principles and provides the violation_type
    field in structured decision traces.
    """

    CUSTOM_MATCHING_ENGINE = "custom_matching_engine"
    ADHOC_PROMOTABLE_FILE = "adhoc_promotable_file"
    MUTABLE_FREEZE_TIME_STATE = "mutable_freeze_time_state"
    GROSS_PNL_PROMOTION = "gross_pnl_promotion"
    NOTEBOOK_ONLY_EVIDENCE = "notebook_only_evidence"
    MISSING_LIVE_EVIDENCE = "missing_live_evidence"
    STATE_AMBIGUITY = "state_ambiguity"
    HIDDEN_OPTIMIZATION_SURFACE = "hidden_optimization_surface"
    PREMATURE_INFRASTRUCTURE = "premature_infrastructure"
    MISSING_SHARED_KERNEL = "missing_shared_kernel"
    NON_IDEMPOTENT_BROKER_MUTATION = "non_idempotent_broker_mutation"
    UNRECOVERABLE_STATE = "unrecoverable_state"
    PREMATURE_BUDGET_ALLOCATION = "premature_budget_allocation"
    MISSING_SESSION_READINESS = "missing_session_readiness"
    GUARDIAN_BYPASS = "guardian_bypass"


@dataclass(frozen=True)
class Principle:
    """A single non-negotiable program principle.

    Attributes:
        id: Stable principle identifier (P01-P15).
        short_name: Machine-friendly name for logs and policy references.
        statement: The full prohibition statement from Plan v3.8 section 1.3.
        violation_type: The violation category this principle guards against.
        reason_code: Stable reason code emitted in rejection logs.
    """

    id: PrincipleID
    short_name: str
    statement: str
    violation_type: ViolationType
    reason_code: str


PRINCIPLES: tuple[Principle, ...] = (
    Principle(
        id=PrincipleID.P01_NO_CUSTOM_MATCHING_ENGINE,
        short_name="no_custom_matching_engine",
        statement=(
            "No custom historical matching engine in v1. "
            "Historical simulation uses NautilusTrader high-level backtesting."
        ),
        violation_type=ViolationType.CUSTOM_MATCHING_ENGINE,
        reason_code="GUARDRAIL_P01_CUSTOM_MATCHING_ENGINE",
    ),
    Principle(
        id=PrincipleID.P02_NO_ADHOC_FILES,
        short_name="no_adhoc_files",
        statement=(
            "No ad-hoc files in promotable research. "
            "Experiments point to certified releases and immutable artifacts."
        ),
        violation_type=ViolationType.ADHOC_PROMOTABLE_FILE,
        reason_code="GUARDRAIL_P02_ADHOC_PROMOTABLE_FILE",
    ),
    Principle(
        id=PrincipleID.P03_NO_MUTABLE_REF_AFTER_FREEZE,
        short_name="no_mutable_ref_after_freeze",
        statement=(
            "No mutable reference resolution after freeze. "
            "Frozen candidates, replay, paper, shadow-live, and live use "
            "resolved-context bundles and approved data-profile releases by digest."
        ),
        violation_type=ViolationType.MUTABLE_FREEZE_TIME_STATE,
        reason_code="GUARDRAIL_P03_MUTABLE_FREEZE_TIME_STATE",
    ),
    Principle(
        id=PrincipleID.P04_NO_GROSS_PNL_PROMOTION,
        short_name="no_gross_pnl_promotion",
        statement=(
            "No promotion on gross PnL. "
            "Decisions use realistic costs, slippage, recurring operational costs, "
            "and both passive-gold and lower-touch cash benchmarks."
        ),
        violation_type=ViolationType.GROSS_PNL_PROMOTION,
        reason_code="GUARDRAIL_P04_GROSS_PNL_PROMOTION",
    ),
    Principle(
        id=PrincipleID.P05_NO_NOTEBOOK_ONLY_EVIDENCE,
        short_name="no_notebook_only_evidence",
        statement=(
            "No notebook-only evidence for promotion. "
            "Notebooks may explore; they may not directly advance promotable state."
        ),
        violation_type=ViolationType.NOTEBOOK_ONLY_EVIDENCE,
        reason_code="GUARDRAIL_P05_NOTEBOOK_ONLY_EVIDENCE",
    ),
    Principle(
        id=PrincipleID.P06_NO_LIVE_WITHOUT_FULL_EVIDENCE,
        short_name="no_live_without_full_evidence",
        statement=(
            "No live activation without deterministic replay, paper evidence, "
            "shadow-live evidence, and broker reconciliation controls."
        ),
        violation_type=ViolationType.MISSING_LIVE_EVIDENCE,
        reason_code="GUARDRAIL_P06_MISSING_LIVE_EVIDENCE",
    ),
    Principle(
        id=PrincipleID.P07_NO_STATE_AMBIGUITY,
        short_name="no_state_ambiguity",
        statement=(
            "No operational state ambiguity. "
            "Economically significant state is journaled, replayable, recoverable, "
            "and cross-checked against broker state intraday as well as at end of day."
        ),
        violation_type=ViolationType.STATE_AMBIGUITY,
        reason_code="GUARDRAIL_P07_STATE_AMBIGUITY",
    ),
    Principle(
        id=PrincipleID.P08_NO_HIDDEN_OPTIMIZATION,
        short_name="no_hidden_optimization",
        statement=(
            "No hidden optimization surfaces. "
            "Lockboxes, nulls, discovery accounting, and "
            "operational-evidence admissibility rules are enforced."
        ),
        violation_type=ViolationType.HIDDEN_OPTIMIZATION_SURFACE,
        reason_code="GUARDRAIL_P08_HIDDEN_OPTIMIZATION_SURFACE",
    ),
    Principle(
        id=PrincipleID.P09_NO_PREMATURE_INFRA,
        short_name="no_premature_infra",
        statement=(
            "No premature infrastructure. "
            "One host, PostgreSQL, off-host object storage, and in-process mailboxes "
            "remain the baseline until measured thresholds justify upgrades."
        ),
        violation_type=ViolationType.PREMATURE_INFRASTRUCTURE,
        reason_code="GUARDRAIL_P09_PREMATURE_INFRASTRUCTURE",
    ),
    Principle(
        id=PrincipleID.P10_NO_RESEARCH_LIVE_FORK,
        short_name="no_research_live_fork",
        statement=(
            "No research/live logic fork for live-eligible strategies. "
            "Research and operations must execute the same canonical signal kernel."
        ),
        violation_type=ViolationType.MISSING_SHARED_KERNEL,
        reason_code="GUARDRAIL_P10_MISSING_SHARED_KERNEL",
    ),
    Principle(
        id=PrincipleID.P11_NO_BROKER_MUTATION_WITHOUT_INTENT,
        short_name="no_broker_mutation_without_intent",
        statement=(
            "No broker mutation without durable intent identity. "
            "Submit, modify, cancel, and flatten actions must be journaled "
            "and idempotent across retry, restart, and reconnect."
        ),
        violation_type=ViolationType.NON_IDEMPOTENT_BROKER_MUTATION,
        reason_code="GUARDRAIL_P11_NON_IDEMPOTENT_BROKER_MUTATION",
    ),
    Principle(
        id=PrincipleID.P12_NO_LIVE_WITHOUT_RECOVERABILITY,
        short_name="no_live_without_recoverability",
        statement=(
            "No live-capable stack without operational recoverability. "
            "Backup/restore, migration, clock-discipline, secret-handling, "
            "and off-host tamper-evident durability controls are required "
            "before live approval."
        ),
        violation_type=ViolationType.UNRECOVERABLE_STATE,
        reason_code="GUARDRAIL_P12_UNRECOVERABLE_STATE",
    ),
    Principle(
        id=PrincipleID.P13_NO_DEEP_BUDGET_BEFORE_VIABILITY,
        short_name="no_deep_budget_before_viability",
        statement=(
            "No deep promotable budget before the intended execution lane "
            "clears the early viability gate."
        ),
        violation_type=ViolationType.PREMATURE_BUDGET_ALLOCATION,
        reason_code="GUARDRAIL_P13_PREMATURE_BUDGET_ALLOCATION",
    ),
    Principle(
        id=PrincipleID.P14_NO_SESSION_WITHOUT_READINESS,
        short_name="no_session_without_readiness",
        statement=(
            "No new tradeable session without a green session_readiness_packet "
            "and broker contract-conformance checks."
        ),
        violation_type=ViolationType.MISSING_SESSION_READINESS,
        reason_code="GUARDRAIL_P14_MISSING_SESSION_READINESS",
    ),
    Principle(
        id=PrincipleID.P15_NO_SINGLE_PATH_EMERGENCY,
        short_name="no_single_path_emergency",
        statement=(
            "No single-path emergency control for live safety. "
            "Emergency cancel/flatten must remain possible through "
            "a minimal out-of-band guardian path."
        ),
        violation_type=ViolationType.GUARDIAN_BYPASS,
        reason_code="GUARDRAIL_P15_GUARDIAN_BYPASS",
    ),
)


def get_principle(principle_id: PrincipleID) -> Principle:
    """Look up a principle by its ID."""
    for p in PRINCIPLES:
        if p.id == principle_id:
            return p
    raise KeyError(f"Unknown principle: {principle_id}")


def get_principle_by_code(reason_code: str) -> Principle:
    """Look up a principle by its stable reason code."""
    for p in PRINCIPLES:
        if p.reason_code == reason_code:
            return p
    raise KeyError(f"Unknown reason code: {reason_code}")
