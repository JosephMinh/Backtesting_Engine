"""Scope boundaries for the first full protocol cycle.

Encodes the in-scope deliverables, explicit anti-scope rules, and capability
tiers from Plan v3.8 section 2.  Downstream code can classify any proposed
work item as in-scope, anti-scope (deferred), or unknown, with structured
explanations suitable for operator-facing rejection logs.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


# ---------------------------------------------------------------------------
# Capability tiers (Plan v3.8 section 2.3)
# ---------------------------------------------------------------------------

@unique
class CapabilityTier(Enum):
    """Every subsystem must declare one of these tiers."""

    V1_CORE_REQUIRED = "v1_core_required"
    V1_CONDITIONAL = "v1_conditional"
    FUTURE_ONLY = "future_only"


# ---------------------------------------------------------------------------
# Scope classification result
# ---------------------------------------------------------------------------

@unique
class ScopeCategory(Enum):
    IN_SCOPE = "in_scope"
    ANTI_SCOPE = "anti_scope"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScopeClassification:
    """Structured decision trace for a scope boundary check.

    Attributes:
        item: The proposed work item or feature name.
        category: Whether it is in_scope, anti_scope, or unknown.
        tier: The capability tier if classified, None if unknown.
        rule: The matching rule or anti-scope entry that governed the decision.
        plan_section: The plan section that defines this boundary.
        reason_code: Stable code for downstream references.
        explanation: Operator-readable explanation of the classification.
        timestamp: ISO-8601 timestamp.
    """

    item: str
    category: str
    tier: str | None
    rule: str
    plan_section: str
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @property
    def is_allowed(self) -> bool:
        return self.category == ScopeCategory.IN_SCOPE.value

    @property
    def is_rejected(self) -> bool:
        return self.category == ScopeCategory.ANTI_SCOPE.value


# ---------------------------------------------------------------------------
# In-scope deliverables (Plan v3.8 section 2.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScopeItem:
    """A single in-scope or anti-scope item."""

    key: str
    description: str
    tier: CapabilityTier
    plan_section: str


IN_SCOPE_ITEMS: tuple[ScopeItem, ...] = (
    ScopeItem(
        key="early_execution_lane_vertical_slice",
        description=(
            "Early execution-lane vertical slice proving 1OZ entitlement, "
            "approved bar construction, dummy-strategy replay, paper routing, "
            "shadow-live suppression, and reconciliation"
        ),
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="immutable_historical_ingestion",
        description="Immutable historical ingestion and release certification",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="bitemporal_reference_data",
        description="Bitemporal reference data with observation cutoffs",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="data_profile_release",
        description="Versioned data_profile_release artifacts for research/live market-data semantics",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="normalized_research_catalogs",
        description="Normalized research catalogs and derived analytic releases",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="nautilus_backtesting",
        description="Realistic Nautilus backtesting and regime-conditioned execution-profile calibration",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="family_governance",
        description=(
            "Family preregistration, research_run logging, family_decision_record "
            "governance, nulls, discovery accounting, and lockbox discipline"
        ),
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="candidate_freeze",
        description="Candidate freezing into immutable deployment-grade bundles",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="execution_symbol_viability",
        description=(
            "Execution-symbol-first viability screens, MGC-to-1OZ portability "
            "certification, and native execution-symbol validation on 1OZ"
        ),
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="replay_certification",
        description="Deterministic replay certification before paper",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="paper_and_shadow_live",
        description=(
            "Mandatory paper trading and shadow-live on the production "
            "connectivity lane before live canary"
        ),
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="rust_operational_daemon",
        description=(
            "Rust operational daemon with recovery fence, session-readiness packets, "
            "guardian emergency control, kill switch, and intraday plus end-of-day reconciliation"
        ),
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="eod_broker_reconciliation",
        description="Authoritative end-of-day broker statement reconciliation",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    ScopeItem(
        key="narrow_first_live_lane",
        description="Narrow first live lane on IBKR",
        tier=CapabilityTier.V1_CORE_REQUIRED,
        plan_section="2.1",
    ),
    # v1_conditional items (section 2.3)
    ScopeItem(
        key="overnight_candidate_class",
        description="Overnight candidate class with stricter gates",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
    ScopeItem(
        key="native_1oz_validation",
        description="Native 1OZ validation when enough history exists",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
    ScopeItem(
        key="screening_fast_path",
        description="Screening fast path for candidate pre-filtering",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
    ScopeItem(
        key="nats_transport",
        description="NATS transport for ordered event fan-out",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
    ScopeItem(
        key="dedicated_telemetry_store",
        description="Dedicated telemetry store when query load degrades metadata latency",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
    ScopeItem(
        key="heavier_secret_management",
        description="Heavier secret-management tooling when credential domains grow",
        tier=CapabilityTier.V1_CONDITIONAL,
        plan_section="2.3",
    ),
)


# ---------------------------------------------------------------------------
# Anti-scope items (Plan v3.8 section 2.2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AntiScopeRule:
    """An explicitly deferred item that must be rejected until continuation review."""

    key: str
    description: str
    plan_section: str
    rejection_reason: str


ANTI_SCOPE_RULES: tuple[AntiScopeRule, ...] = (
    AntiScopeRule(
        key="custom_matching_engine",
        description="Custom historical matching or queue simulation engine",
        plan_section="2.2",
        rejection_reason="Custom matching engines are anti-scope; use NautilusTrader high-level backtesting",
    ),
    AntiScopeRule(
        key="sub_minute_live_strategies",
        description="Sub-minute live strategies",
        plan_section="2.2",
        rejection_reason="Sub-minute strategies are research-only; live-eligible must be >= 60s decision interval",
    ),
    AntiScopeRule(
        key="depth_driven_live_alpha",
        description="Depth-driven or latency-sensitive live alpha",
        plan_section="2.2",
        rejection_reason="Depth-driven and latency-sensitive alpha is deferred until continuation review",
    ),
    AntiScopeRule(
        key="second_broker",
        description="A second broker on the live hot path",
        plan_section="2.2",
        rejection_reason="Only IBKR is approved for v1; second broker requires continuation review",
    ),
    AntiScopeRule(
        key="live_premium_feed",
        description="Live premium feed subscription for live alpha production",
        plan_section="2.2",
        rejection_reason="Premium feed subscription is deferred; use IBKR data in v1",
    ),
    AntiScopeRule(
        key="kubernetes_orchestration",
        description="Kubernetes or multi-host orchestration",
        plan_section="2.2",
        rejection_reason="One-host baseline remains; multi-host requires justified continuation memo",
    ),
    AntiScopeRule(
        key="mandatory_nats",
        description="Mandatory NATS or other external transport",
        plan_section="2.2",
        rejection_reason="NATS is v1_conditional only; mandatory external transport is anti-scope",
    ),
    AntiScopeRule(
        key="dedicated_timescaledb",
        description="Dedicated TimescaleDB or separate telemetry cluster by default",
        plan_section="2.2",
        rejection_reason="Dedicated telemetry cluster is anti-scope; PostgreSQL baseline until upgrade trigger met",
    ),
    AntiScopeRule(
        key="generalized_feature_store",
        description="A generalized feature-store product",
        plan_section="2.2",
        rejection_reason="Feature-store products are deferred; not needed for v1 protocol cycle",
    ),
    AntiScopeRule(
        key="multi_product_portfolio_optimization",
        description="Multi-product portfolio optimization",
        plan_section="2.2",
        rejection_reason="Portfolio optimization across products is deferred; v1 focuses on single product",
    ),
    AntiScopeRule(
        key="multiple_active_live_bundles",
        description="Multiple simultaneously active live bundles per account by default",
        plan_section="2.2",
        rejection_reason="One active live bundle per account is the approved posture",
    ),
)


# ---------------------------------------------------------------------------
# Scope index for fast lookup
# ---------------------------------------------------------------------------

_IN_SCOPE_INDEX: dict[str, ScopeItem] = {item.key: item for item in IN_SCOPE_ITEMS}
_ANTI_SCOPE_INDEX: dict[str, AntiScopeRule] = {rule.key: rule for rule in ANTI_SCOPE_RULES}


# ---------------------------------------------------------------------------
# Classification API
# ---------------------------------------------------------------------------

def classify_item(item_key: str) -> ScopeClassification:
    """Classify a proposed work item against the v1 scope boundaries.

    Returns a structured trace with category, tier, matching rule,
    plan section, and operator-readable explanation.
    """
    if item_key in _IN_SCOPE_INDEX:
        entry = _IN_SCOPE_INDEX[item_key]
        return ScopeClassification(
            item=item_key,
            category=ScopeCategory.IN_SCOPE.value,
            tier=entry.tier.value,
            rule=entry.key,
            plan_section=entry.plan_section,
            reason_code=f"SCOPE_IN_{item_key.upper()}",
            explanation=f"In scope (tier: {entry.tier.value}): {entry.description}",
        )

    if item_key in _ANTI_SCOPE_INDEX:
        rule = _ANTI_SCOPE_INDEX[item_key]
        return ScopeClassification(
            item=item_key,
            category=ScopeCategory.ANTI_SCOPE.value,
            tier=CapabilityTier.FUTURE_ONLY.value,
            rule=rule.key,
            plan_section=rule.plan_section,
            reason_code=f"SCOPE_ANTI_{item_key.upper()}",
            explanation=rule.rejection_reason,
        )

    return ScopeClassification(
        item=item_key,
        category=ScopeCategory.UNKNOWN.value,
        tier=None,
        rule="no_match",
        plan_section="n/a",
        reason_code="SCOPE_UNKNOWN",
        explanation=f"Item '{item_key}' is not in the scope registry; requires explicit classification",
    )


def classify_items(item_keys: list[str]) -> list[ScopeClassification]:
    """Classify multiple items at once."""
    return [classify_item(k) for k in item_keys]


def get_items_by_tier(tier: CapabilityTier) -> list[ScopeItem]:
    """Return all in-scope items for a given capability tier."""
    return [item for item in IN_SCOPE_ITEMS if item.tier == tier]


def get_all_anti_scope_keys() -> list[str]:
    """Return all anti-scope item keys."""
    return list(_ANTI_SCOPE_INDEX.keys())
