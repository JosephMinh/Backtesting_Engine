"""Guardrail enforcement framework.

Provides ``check_guardrail`` which evaluates a condition against a principle
and returns a structured ``GuardrailResult`` that doubles as a decision trace
suitable for logging, downstream policy evaluation, and operator-facing
rejection messages.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from shared.policy.principles import Principle, PrincipleID, ViolationType, get_principle


@dataclass(frozen=True)
class GuardrailResult:
    """Structured decision trace for a guardrail evaluation.

    Attributes:
        principle_id: Stable principle identifier (e.g. ``"P01"``).
        principle_name: Human-readable short name.
        violation_type: The violation category evaluated.
        passed: Whether the guardrail check passed (no violation).
        reason_code: Stable reason code for downstream references.
        diagnostic: Free-form context about what was evaluated.
        timestamp: ISO-8601 timestamp of the evaluation.
        context: Additional structured data about the evaluation.
    """

    principle_id: str
    principle_name: str
    violation_type: str
    passed: bool
    reason_code: str
    diagnostic: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary suitable for JSON logging."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to a JSON string for structured log output."""
        return json.dumps(self.to_dict(), default=str)

    @property
    def violated(self) -> bool:
        """True when the guardrail was violated."""
        return not self.passed


def check_guardrail(
    principle_id: PrincipleID,
    condition_met: bool,
    diagnostic: str,
    context: dict[str, Any] | None = None,
) -> GuardrailResult:
    """Evaluate a guardrail condition and produce a structured trace.

    Parameters
    ----------
    principle_id:
        Which principle to evaluate against.
    condition_met:
        ``True`` when the system state satisfies the guardrail
        (i.e. no violation).  ``False`` indicates a violation.
    diagnostic:
        Human-readable explanation of what was checked and why
        the result is pass or fail.
    context:
        Optional structured data providing additional detail
        (e.g. the offending file path, the mutation that lacked
        an intent ID, the missing evidence type).

    Returns
    -------
    GuardrailResult
        A frozen, serializable decision trace.
    """
    principle = get_principle(principle_id)
    return GuardrailResult(
        principle_id=principle.id.value,
        principle_name=principle.short_name,
        violation_type=principle.violation_type.value,
        passed=condition_met,
        reason_code=principle.reason_code,
        diagnostic=diagnostic,
        context=context or {},
    )


def check_mutable_freeze_time_state(
    *,
    references_are_resolved: bool,
    digest_verified: bool,
    diagnostic: str = "",
) -> GuardrailResult:
    """P03: Check that no mutable reference resolution occurs after freeze."""
    passed = references_are_resolved and digest_verified
    diag = diagnostic or (
        "All references resolved by digest"
        if passed
        else "Mutable reference detected after freeze"
    )
    return check_guardrail(
        PrincipleID.P03_NO_MUTABLE_REF_AFTER_FREEZE,
        condition_met=passed,
        diagnostic=diag,
        context={
            "references_resolved": references_are_resolved,
            "digest_verified": digest_verified,
        },
    )


def check_notebook_only_evidence(
    *,
    evidence_sources: list[str],
    diagnostic: str = "",
) -> GuardrailResult:
    """P05: Check that promotion evidence does not come solely from notebooks."""
    non_notebook = [s for s in evidence_sources if s != "notebook"]
    passed = len(non_notebook) > 0 and len(evidence_sources) > 0
    diag = diagnostic or (
        f"Evidence includes non-notebook sources: {non_notebook}"
        if passed
        else f"Only notebook evidence found: {evidence_sources}"
    )
    return check_guardrail(
        PrincipleID.P05_NO_NOTEBOOK_ONLY_EVIDENCE,
        condition_met=passed,
        diagnostic=diag,
        context={"evidence_sources": evidence_sources, "non_notebook_sources": non_notebook},
    )


def check_shared_kernel(
    *,
    research_kernel_hash: str,
    live_kernel_hash: str,
    diagnostic: str = "",
) -> GuardrailResult:
    """P10: Check that research and live use the same canonical signal kernel."""
    passed = research_kernel_hash == live_kernel_hash and research_kernel_hash != ""
    diag = diagnostic or (
        f"Kernel hashes match: {research_kernel_hash}"
        if passed
        else f"Kernel mismatch: research={research_kernel_hash} live={live_kernel_hash}"
    )
    return check_guardrail(
        PrincipleID.P10_NO_RESEARCH_LIVE_FORK,
        condition_met=passed,
        diagnostic=diag,
        context={
            "research_kernel_hash": research_kernel_hash,
            "live_kernel_hash": live_kernel_hash,
        },
    )


def check_idempotent_broker_mutation(
    *,
    intent_id: str | None,
    action: str,
    is_journaled: bool,
    diagnostic: str = "",
) -> GuardrailResult:
    """P11: Check that broker mutations carry a durable intent identity and are journaled."""
    passed = intent_id is not None and intent_id != "" and is_journaled
    diag = diagnostic or (
        f"Broker action '{action}' journaled with intent {intent_id}"
        if passed
        else f"Broker action '{action}' missing intent_id or journal entry"
    )
    return check_guardrail(
        PrincipleID.P11_NO_BROKER_MUTATION_WITHOUT_INTENT,
        condition_met=passed,
        diagnostic=diag,
        context={"intent_id": intent_id, "action": action, "is_journaled": is_journaled},
    )


def check_recoverability(
    *,
    backup_configured: bool,
    migration_tested: bool,
    clock_discipline: bool,
    secrets_managed: bool,
    offhost_durability: bool,
    diagnostic: str = "",
) -> GuardrailResult:
    """P12: Check that all operational recoverability requirements are met."""
    checks = {
        "backup_configured": backup_configured,
        "migration_tested": migration_tested,
        "clock_discipline": clock_discipline,
        "secrets_managed": secrets_managed,
        "offhost_durability": offhost_durability,
    }
    passed = all(checks.values())
    failing = [k for k, v in checks.items() if not v]
    diag = diagnostic or (
        "All recoverability controls verified"
        if passed
        else f"Missing recoverability controls: {failing}"
    )
    return check_guardrail(
        PrincipleID.P12_NO_LIVE_WITHOUT_RECOVERABILITY,
        condition_met=passed,
        diagnostic=diag,
        context=checks,
    )


def check_guardian_path(
    *,
    guardian_reachable: bool,
    guardian_independent: bool,
    diagnostic: str = "",
) -> GuardrailResult:
    """P15: Check that an out-of-band guardian emergency path exists."""
    passed = guardian_reachable and guardian_independent
    diag = diagnostic or (
        "Guardian path available and independent"
        if passed
        else "Guardian path missing or not independent of main control path"
    )
    return check_guardrail(
        PrincipleID.P15_NO_SINGLE_PATH_EMERGENCY,
        condition_met=passed,
        diagnostic=diag,
        context={
            "guardian_reachable": guardian_reachable,
            "guardian_independent": guardian_independent,
        },
    )
