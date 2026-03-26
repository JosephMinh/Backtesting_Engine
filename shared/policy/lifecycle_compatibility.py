"""Canonical lifecycle state-machine specs and compatibility-domain contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique

from shared.policy.deployment_packets import (
    DEPLOYMENT_ALLOWED_TRANSITIONS,
    READINESS_ALLOWED_TRANSITIONS,
)
from shared.policy.release_validation import (
    DATASET_ALLOWED_TRANSITIONS,
    DERIVED_ALLOWED_TRANSITIONS,
)
from shared.policy.research_state import (
    _ALLOWED_DECISION_TRANSITIONS,
    _ALLOWED_RUN_TRANSITIONS,
)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@unique
class LifecycleSpecStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"
    INCOMPATIBLE = "incompatible"


@unique
class LifecycleConsumer(str, Enum):
    PYTHON_TOOLING = "python_tooling"
    RUST_RUNTIME = "rust_runtime"
    SQL_CHECKS = "sql_checks"
    CLI_TOOLING = "cli_tooling"
    DASHBOARDS = "dashboards"


@unique
class CompatibilityDomain(str, Enum):
    DATA_PROTOCOL = "data_protocol"
    STRATEGY_PROTOCOL = "strategy_protocol"
    OPS_PROTOCOL = "ops_protocol"
    POLICY_BUNDLE_HASH = "policy_bundle_hash"
    COMPATIBILITY_MATRIX_VERSION = "compatibility_matrix_version"


@unique
class LifecycleMachine(str, Enum):
    RESEARCH_RUN = "research_run_lifecycle"
    FAMILY_DECISION = "family_decision_lifecycle"
    DATASET_RELEASE = "dataset_release_lifecycle"
    DERIVED_RELEASE = "derived_release_lifecycle"
    BUNDLE_READINESS = "bundle_readiness_lifecycle"
    DEPLOYMENT_INSTANCE = "deployment_instance_lifecycle"


CANONICAL_LIFECYCLE_CONSUMERS = tuple(
    consumer.value for consumer in LifecycleConsumer
)

REQUIRED_COMPATIBILITY_FIELDS = tuple(domain.value for domain in CompatibilityDomain)


@dataclass(frozen=True)
class CompatibilityDomainSpec:
    domain: str
    description: str
    startup_blocking: bool
    requires_recertification_when_changed: bool
    required_evidence_fields: tuple[str, ...]
    consumers: tuple[str, ...] = CANONICAL_LIFECYCLE_CONSUMERS

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TransitionRule:
    from_state: str
    to_state: str
    affected_domains: tuple[str, ...]
    required_evidence_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LifecycleMachineSpec:
    machine_id: str
    description: str
    consumers: tuple[str, ...]
    states: tuple[str, ...]
    initial_states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    compatibility_domains: tuple[str, ...]
    transitions: tuple[TransitionRule, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["transitions"] = [rule.to_dict() for rule in self.transitions]
        return payload


@dataclass(frozen=True)
class TransitionLogEntry:
    stage: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class LifecycleTransitionReport:
    case_id: str
    machine_id: str
    status: str
    reason_code: str
    from_state: str
    to_state: str
    allowed: bool
    affected_domains: tuple[str, ...]
    required_evidence_fields: tuple[str, ...]
    transition_log: tuple[TransitionLogEntry, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["transition_log"] = [entry.to_dict() for entry in self.transition_log]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class CompatibilityVector:
    data_protocol: str
    strategy_protocol: str
    ops_protocol: str
    policy_bundle_hash: str
    compatibility_matrix_version: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class CompatibilityCheckRequest:
    case_id: str
    subject_id: str
    machine_id: str
    baseline: CompatibilityVector
    candidate: CompatibilityVector
    declared_affected_domains: tuple[str, ...] = ()
    active_session: bool = False


@dataclass(frozen=True)
class CompatibilityDomainResult:
    domain: str
    baseline_value: str
    candidate_value: str
    changed: bool
    startup_blocking: bool
    requires_recertification: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CompatibilityCheckReport:
    case_id: str
    subject_id: str
    machine_id: str
    status: str
    reason_code: str
    compatible: bool
    changed_domains: tuple[str, ...]
    blocking_domains: tuple[str, ...]
    recertification_domains: tuple[str, ...]
    declared_affected_domains: tuple[str, ...]
    domain_results: tuple[CompatibilityDomainResult, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["domain_results"] = [result.to_dict() for result in self.domain_results]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


COMPATIBILITY_DOMAIN_SPECS = (
    CompatibilityDomainSpec(
        domain=CompatibilityDomain.DATA_PROTOCOL.value,
        description=(
            "Historical/live bar semantics, symbology, sessions, and data-profile rules "
            "that must stay compatible across research, release packaging, and live feed use."
        ),
        startup_blocking=True,
        requires_recertification_when_changed=True,
        required_evidence_fields=(
            "dataset_release_id",
            "data_profile_release_id",
            "protocol_versions",
        ),
    ),
    CompatibilityDomainSpec(
        domain=CompatibilityDomain.STRATEGY_PROTOCOL.value,
        description=(
            "Signal-kernel ABI, state serialization, feature contracts, and parameterization "
            "semantics shared by research artifacts and runtime execution."
        ),
        startup_blocking=True,
        requires_recertification_when_changed=True,
        required_evidence_fields=(
            "signal_kernel_digest",
            "kernel_abi_version",
            "state_serialization_version",
        ),
    ),
    CompatibilityDomainSpec(
        domain=CompatibilityDomain.OPS_PROTOCOL.value,
        description=(
            "Operational packet, runtime snapshot, recovery, and reconciliation semantics "
            "used by activation, sessions, and restore workflows."
        ),
        startup_blocking=True,
        requires_recertification_when_changed=True,
        required_evidence_fields=(
            "promotion_packet_id",
            "session_readiness_packet_id",
            "deployment_instance_id",
        ),
    ),
    CompatibilityDomainSpec(
        domain=CompatibilityDomain.POLICY_BUNDLE_HASH.value,
        description=(
            "Frozen policy bundle identity that binds guardrails, gating rules, and "
            "operator workflows to a deterministic policy snapshot."
        ),
        startup_blocking=True,
        requires_recertification_when_changed=True,
        required_evidence_fields=("policy_bundle_hash",),
    ),
    CompatibilityDomainSpec(
        domain=CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value,
        description=(
            "The declared compatibility matrix revision that downstream startup checks "
            "and migration tooling compare before activating a new binary or bundle."
        ),
        startup_blocking=True,
        requires_recertification_when_changed=False,
        required_evidence_fields=("compatibility_matrix_version",),
    ),
)

COMPATIBILITY_DOMAIN_INDEX = {
    spec.domain: spec for spec in COMPATIBILITY_DOMAIN_SPECS
}


def _state_value(state: object) -> str:
    return getattr(state, "value", str(state))


def _build_machine_spec(
    *,
    machine_id: LifecycleMachine,
    description: str,
    transitions_map: dict[object, object],
    compatibility_domains: tuple[CompatibilityDomain, ...],
    required_evidence_fields: tuple[str, ...],
    initial_states: tuple[str, ...],
    terminal_states: tuple[str, ...],
) -> LifecycleMachineSpec:
    transitions: list[TransitionRule] = []
    states = tuple(_state_value(state) for state in transitions_map)
    domains = tuple(domain.value for domain in compatibility_domains)

    for from_state, to_states in transitions_map.items():
        for to_state in to_states:
            transitions.append(
                TransitionRule(
                    from_state=_state_value(from_state),
                    to_state=_state_value(to_state),
                    affected_domains=domains,
                    required_evidence_fields=required_evidence_fields,
                )
            )

    return LifecycleMachineSpec(
        machine_id=machine_id.value,
        description=description,
        consumers=CANONICAL_LIFECYCLE_CONSUMERS,
        states=states,
        initial_states=initial_states,
        terminal_states=terminal_states,
        compatibility_domains=domains,
        transitions=tuple(transitions),
    )


LIFECYCLE_MACHINE_SPECS = (
    _build_machine_spec(
        machine_id=LifecycleMachine.RESEARCH_RUN,
        description=(
            "Research-run lifecycle state machine covering recorded, quarantined, "
            "superseded, and revoked evidence."
        ),
        transitions_map=_ALLOWED_RUN_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.DATA_PROTOCOL,
            CompatibilityDomain.STRATEGY_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
        ),
        required_evidence_fields=(
            "research_run_id",
            "dataset_release_id",
            "analytic_release_id",
            "data_profile_release_id",
            "resolved_context_bundle_id",
        ),
        initial_states=("recorded",),
        terminal_states=("superseded", "revoked"),
    ),
    _build_machine_spec(
        machine_id=LifecycleMachine.FAMILY_DECISION,
        description=(
            "Family-decision lifecycle state machine binding selection decisions to "
            "research evidence and expiration/supersession rules."
        ),
        transitions_map=_ALLOWED_DECISION_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.STRATEGY_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
        ),
        required_evidence_fields=(
            "family_decision_record_id",
            "research_run_id",
            "resolved_context_bundle_id",
        ),
        initial_states=("active",),
        terminal_states=("superseded", "expired"),
    ),
    _build_machine_spec(
        machine_id=LifecycleMachine.DATASET_RELEASE,
        description=(
            "Dataset-release lifecycle state machine for raw/reference artifacts and "
            "their certification, approval, activation, quarantine, and revocation."
        ),
        transitions_map=DATASET_ALLOWED_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.DATA_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
            CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION,
        ),
        required_evidence_fields=(
            "release_id",
            "protocol_versions",
            "policy_bundle_hash",
            "certification_report_hash",
        ),
        initial_states=("DRAFT",),
        terminal_states=("REVOKED",),
    ),
    _build_machine_spec(
        machine_id=LifecycleMachine.DERIVED_RELEASE,
        description=(
            "Derived-release lifecycle state machine for analytic and data-profile "
            "artifacts that depend on frozen dataset and strategy semantics."
        ),
        transitions_map=DERIVED_ALLOWED_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.DATA_PROTOCOL,
            CompatibilityDomain.STRATEGY_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
            CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION,
        ),
        required_evidence_fields=(
            "release_id",
            "dataset_release_id",
            "protocol_versions",
            "policy_bundle_hash",
        ),
        initial_states=("DRAFT",),
        terminal_states=("REVOKED",),
    ),
    _build_machine_spec(
        machine_id=LifecycleMachine.BUNDLE_READINESS,
        description=(
            "Readiness lifecycle state machine for candidate bundles as they move from "
            "frozen evidence into portability, replay, paper, shadow, and live gates."
        ),
        transitions_map=READINESS_ALLOWED_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.DATA_PROTOCOL,
            CompatibilityDomain.STRATEGY_PROTOCOL,
            CompatibilityDomain.OPS_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
            CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION,
        ),
        required_evidence_fields=(
            "bundle_id",
            "resolved_context_bundle_id",
            "execution_profile_release_id",
            "data_profile_release_id",
            "policy_bundle_hash",
        ),
        initial_states=("FROZEN",),
        terminal_states=("REVOKED",),
    ),
    _build_machine_spec(
        machine_id=LifecycleMachine.DEPLOYMENT_INSTANCE,
        description=(
            "Deployment-instance lifecycle state machine for paper, shadow-live, and "
            "live activation states, including withdrawal and closure."
        ),
        transitions_map=DEPLOYMENT_ALLOWED_TRANSITIONS,
        compatibility_domains=(
            CompatibilityDomain.DATA_PROTOCOL,
            CompatibilityDomain.STRATEGY_PROTOCOL,
            CompatibilityDomain.OPS_PROTOCOL,
            CompatibilityDomain.POLICY_BUNDLE_HASH,
            CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION,
        ),
        required_evidence_fields=(
            "deployment_instance_id",
            "promotion_packet_id",
            "session_readiness_packet_id",
            "policy_bundle_hash",
        ),
        initial_states=("PAPER_PENDING",),
        terminal_states=("WITHDRAWN", "CLOSED"),
    ),
)

LIFECYCLE_MACHINE_INDEX = {
    spec.machine_id: spec for spec in LIFECYCLE_MACHINE_SPECS
}


def machine_specs_by_id() -> dict[str, LifecycleMachineSpec]:
    return dict(LIFECYCLE_MACHINE_INDEX)


def compatibility_domain_names() -> tuple[str, ...]:
    return tuple(spec.domain for spec in COMPATIBILITY_DOMAIN_SPECS)


def _normalize_machine_id(machine_id: str) -> str:
    try:
        return LifecycleMachine(machine_id).value
    except ValueError:
        return machine_id


def _normalize_domains(domains: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for domain in domains:
        value = CompatibilityDomain(domain).value
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _find_transition_rule(
    machine: LifecycleMachineSpec, from_state: str, to_state: str
) -> TransitionRule | None:
    for rule in machine.transitions:
        if rule.from_state == from_state and rule.to_state == to_state:
            return rule
    return None


def evaluate_lifecycle_transition(
    case_id: str,
    machine_id: str,
    from_state: str,
    to_state: str,
) -> LifecycleTransitionReport:
    normalized_machine_id = _normalize_machine_id(machine_id)
    machine = LIFECYCLE_MACHINE_INDEX.get(normalized_machine_id)
    if machine is None:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="UNKNOWN_LIFECYCLE_MACHINE",
            from_state=from_state,
            to_state=to_state,
            allowed=False,
            affected_domains=(),
            required_evidence_fields=(),
            transition_log=(
                TransitionLogEntry(
                    stage="lookup",
                    detail="Requested lifecycle machine is not declared in the shared catalog.",
                ),
            ),
            explanation="Use one of the canonical lifecycle machine identifiers.",
            remediation="Resolve the machine identifier from the shared lifecycle catalog.",
        )

    transition_log = (
        TransitionLogEntry(
            stage="lookup",
            detail=(
                f"Loaded {machine.machine_id} with {len(machine.states)} canonical states "
                "from the shared lifecycle catalog."
            ),
        ),
    )
    if from_state not in machine.states or to_state not in machine.states:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="UNKNOWN_LIFECYCLE_STATE",
            from_state=from_state,
            to_state=to_state,
            allowed=False,
            affected_domains=machine.compatibility_domains,
            required_evidence_fields=(),
            transition_log=transition_log
            + (
                TransitionLogEntry(
                    stage="validate_transition",
                    detail="Transition references a state outside the canonical state machine.",
                ),
            ),
            explanation="Lifecycle transitions must use the shared canonical state names.",
            remediation="Look up the machine spec and use one of its declared states.",
        )

    if from_state == to_state:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="LIFECYCLE_TRANSITION_NOOP",
            from_state=from_state,
            to_state=to_state,
            allowed=False,
            affected_domains=machine.compatibility_domains,
            required_evidence_fields=(),
            transition_log=transition_log
            + (
                TransitionLogEntry(
                    stage="validate_transition",
                    detail="No-op transitions are rejected so downstream gates can react deterministically.",
                ),
            ),
            explanation="Lifecycle transitions must move the subject into a new state.",
            remediation="Submit a real state change or leave the subject unchanged.",
        )

    rule = _find_transition_rule(machine, from_state, to_state)
    if rule is None:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="LIFECYCLE_TRANSITION_BLOCKED",
            from_state=from_state,
            to_state=to_state,
            allowed=False,
            affected_domains=machine.compatibility_domains,
            required_evidence_fields=(),
            transition_log=transition_log
            + (
                TransitionLogEntry(
                    stage="validate_transition",
                    detail="Requested transition is not part of the canonical state machine.",
                ),
            ),
            explanation="The transition skips required review or activation checkpoints.",
            remediation="Advance the subject only through the plan-defined lifecycle transitions.",
        )

    return LifecycleTransitionReport(
        case_id=case_id,
        machine_id=machine.machine_id,
        status=LifecycleSpecStatus.PASS.value,
        reason_code="LIFECYCLE_TRANSITION_ALLOWED",
        from_state=from_state,
        to_state=to_state,
        allowed=True,
        affected_domains=rule.affected_domains,
        required_evidence_fields=rule.required_evidence_fields,
        transition_log=transition_log
        + (
            TransitionLogEntry(
                stage="validate_transition",
                detail="Transition matches the canonical lifecycle state machine.",
            ),
            TransitionLogEntry(
                stage="compatibility_domains",
                detail=(
                    "Affected compatibility domains: "
                    + ", ".join(rule.affected_domains)
                    + "."
                ),
            ),
            TransitionLogEntry(
                stage="evidence_contract",
                detail=(
                    "Required evidence fields: "
                    + ", ".join(rule.required_evidence_fields)
                    + "."
                ),
            ),
        ),
        explanation="The requested transition is allowed by the shared lifecycle catalog.",
        remediation="Record the transition with the declared evidence fields and retained logs.",
    )


def evaluate_compatibility(
    request: CompatibilityCheckRequest,
) -> CompatibilityCheckReport:
    normalized_machine_id = _normalize_machine_id(request.machine_id)
    machine = LIFECYCLE_MACHINE_INDEX.get(normalized_machine_id)
    if machine is None:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=request.machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="UNKNOWN_LIFECYCLE_MACHINE",
            compatible=False,
            changed_domains=(),
            blocking_domains=(),
            recertification_domains=(),
            declared_affected_domains=(),
            domain_results=(),
            explanation="Compatibility checks require a canonical lifecycle machine identifier.",
            remediation="Resolve the lifecycle machine from the shared catalog before checking compatibility.",
        )

    try:
        declared_domains = _normalize_domains(request.declared_affected_domains)
    except ValueError:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="UNKNOWN_COMPATIBILITY_DOMAIN",
            compatible=False,
            changed_domains=(),
            blocking_domains=(),
            recertification_domains=(),
            declared_affected_domains=request.declared_affected_domains,
            domain_results=(),
            explanation="Declared affected domains must use the canonical compatibility-domain names.",
            remediation="Normalize the domain names to the shared compatibility-domain catalog.",
        )

    baseline = request.baseline.to_dict()
    candidate = request.candidate.to_dict()
    missing_fields = tuple(
        field_name
        for field_name in REQUIRED_COMPATIBILITY_FIELDS
        if not baseline.get(field_name) or not candidate.get(field_name)
    )
    if missing_fields:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="COMPATIBILITY_FIELDS_MISSING",
            compatible=False,
            changed_domains=(),
            blocking_domains=(),
            recertification_domains=(),
            declared_affected_domains=declared_domains,
            domain_results=(),
            explanation=(
                "Compatibility vectors must populate every canonical domain value. "
                f"Missing: {missing_fields}."
            ),
            remediation="Populate every compatibility domain before running startup or migration checks.",
        )

    domain_results: list[CompatibilityDomainResult] = []
    changed_domains: list[str] = []
    blocking_domains: list[str] = []
    recertification_domains: list[str] = []

    for spec in COMPATIBILITY_DOMAIN_SPECS:
        changed = baseline[spec.domain] != candidate[spec.domain]
        if changed:
            changed_domains.append(spec.domain)
            if spec.startup_blocking:
                blocking_domains.append(spec.domain)
            if spec.requires_recertification_when_changed:
                recertification_domains.append(spec.domain)

        domain_results.append(
            CompatibilityDomainResult(
                domain=spec.domain,
                baseline_value=baseline[spec.domain],
                candidate_value=candidate[spec.domain],
                changed=changed,
                startup_blocking=spec.startup_blocking,
                requires_recertification=(
                    changed and spec.requires_recertification_when_changed
                ),
            )
        )

    changed_tuple = tuple(changed_domains)
    blocking_tuple = tuple(blocking_domains)
    recertification_tuple = tuple(recertification_domains)
    undeclared_changes = tuple(
        domain for domain in changed_tuple if domain not in declared_domains
    )
    matrix_changed = (
        CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value in changed_tuple
    )
    protocol_change_without_matrix = (
        any(
            domain != CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION.value
            for domain in changed_tuple
        )
        and not matrix_changed
    )

    if protocol_change_without_matrix:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="COMPATIBILITY_MATRIX_NOT_BUMPED",
            compatible=False,
            changed_domains=changed_tuple,
            blocking_domains=blocking_tuple,
            recertification_domains=recertification_tuple,
            declared_affected_domains=declared_domains,
            domain_results=tuple(domain_results),
            explanation=(
                "Protocol or policy changes were detected without changing "
                "`compatibility_matrix_version`."
            ),
            remediation=(
                "Bump the compatibility matrix version whenever a protocol or policy "
                "domain changes."
            ),
        )

    if undeclared_changes:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="UNDECLARED_COMPATIBILITY_DRIFT",
            compatible=False,
            changed_domains=changed_tuple,
            blocking_domains=blocking_tuple,
            recertification_domains=recertification_tuple,
            declared_affected_domains=declared_domains,
            domain_results=tuple(domain_results),
            explanation=(
                "The candidate changed one or more compatibility domains without "
                "declaring them in the migration/startup request."
            ),
            remediation=(
                "Declare every changed compatibility domain so recertification and "
                "startup gates can react deterministically."
            ),
        )

    if request.active_session and changed_tuple:
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="ACTIVE_SESSION_COMPATIBILITY_CHANGE_BLOCKED",
            compatible=False,
            changed_domains=changed_tuple,
            blocking_domains=blocking_tuple,
            recertification_domains=recertification_tuple,
            declared_affected_domains=declared_domains,
            domain_results=tuple(domain_results),
            explanation=(
                "Active sessions may not absorb compatibility-domain changes outside "
                "incident procedure."
            ),
            remediation=(
                "Wait for the active session to end or route the change through the "
                "incident workflow."
            ),
        )

    if changed_tuple:
        reason_code = (
            "COMPATIBILITY_DRIFT_REQUIRES_RECERTIFICATION"
            if recertification_tuple
            else "COMPATIBILITY_MATRIX_CHANGED"
        )
        explanation = (
            "Compatibility drift was declared correctly, but startup and promotion "
            "logic must treat it as a fresh certification boundary."
        )
        remediation = (
            "Run the required replay, parity, or operational recertification before "
            "promoting the candidate into a new session."
        )
        return CompatibilityCheckReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine.machine_id,
            status=LifecycleSpecStatus.INCOMPATIBLE.value,
            reason_code=reason_code,
            compatible=False,
            changed_domains=changed_tuple,
            blocking_domains=blocking_tuple,
            recertification_domains=recertification_tuple,
            declared_affected_domains=declared_domains,
            domain_results=tuple(domain_results),
            explanation=explanation,
            remediation=remediation,
        )

    return CompatibilityCheckReport(
        case_id=request.case_id,
        subject_id=request.subject_id,
        machine_id=machine.machine_id,
        status=LifecycleSpecStatus.PASS.value,
        reason_code="COMPATIBILITY_CONFIRMED",
        compatible=True,
        changed_domains=(),
        blocking_domains=(),
        recertification_domains=(),
        declared_affected_domains=declared_domains,
        domain_results=tuple(domain_results),
        explanation=(
            "All canonical compatibility domains match the approved baseline for this "
            "lifecycle subject."
        ),
        remediation="No recertification is required for this unchanged compatibility vector.",
    )


def validate_contract() -> list[str]:
    errors: list[str] = []

    if compatibility_domain_names() != REQUIRED_COMPATIBILITY_FIELDS:
        errors.append("compatibility domains must cover every canonical domain exactly once")

    if set(LIFECYCLE_MACHINE_INDEX) != {
        machine.value for machine in LifecycleMachine
    }:
        errors.append("lifecycle machine catalog must cover every canonical machine")

    for spec in COMPATIBILITY_DOMAIN_SPECS:
        if not spec.required_evidence_fields:
            errors.append(f"{spec.domain} must declare required evidence fields")
        if not spec.consumers:
            errors.append(f"{spec.domain} must declare downstream consumers")

    for machine in LIFECYCLE_MACHINE_SPECS:
        if not machine.states:
            errors.append(f"{machine.machine_id} must declare canonical states")
        if not machine.transitions:
            errors.append(f"{machine.machine_id} must declare canonical transitions")
        if not set(machine.initial_states).issubset(machine.states):
            errors.append(f"{machine.machine_id} initial states must be canonical states")
        if not set(machine.terminal_states).issubset(machine.states):
            errors.append(f"{machine.machine_id} terminal states must be canonical states")
        if not set(machine.compatibility_domains).issubset(
            COMPATIBILITY_DOMAIN_INDEX
        ):
            errors.append(
                f"{machine.machine_id} references unknown compatibility domains"
            )
        for rule in machine.transitions:
            if rule.from_state not in machine.states or rule.to_state not in machine.states:
                errors.append(
                    f"{machine.machine_id} transition {rule.from_state}->{rule.to_state} "
                    "uses unknown states"
                )
            if not set(rule.affected_domains).issubset(machine.compatibility_domains):
                errors.append(
                    f"{machine.machine_id} transition {rule.from_state}->{rule.to_state} "
                    "uses domains outside the machine declaration"
                )
            if not rule.required_evidence_fields:
                errors.append(
                    f"{machine.machine_id} transition {rule.from_state}->{rule.to_state} "
                    "must declare required evidence"
                )

    return errors


VALIDATION_ERRORS = validate_contract()
