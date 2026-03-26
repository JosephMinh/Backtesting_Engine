"""Canonical lifecycle state-machine specs and compatibility domains."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, unique
from typing import TypeVar

SUPPORTED_LIFECYCLE_SPEC_SCHEMA_VERSION = 1

RELEASE_DATASET_MACHINE_ID = "release_dataset_lifecycle"
RELEASE_DERIVED_MACHINE_ID = "release_derived_lifecycle"
BUNDLE_READINESS_MACHINE_ID = "bundle_readiness_lifecycle"
DEPLOYMENT_INSTANCE_MACHINE_ID = "deployment_instance_lifecycle"
RESEARCH_RUN_MACHINE_ID = "research_run_lifecycle"
FAMILY_DECISION_MACHINE_ID = "family_decision_lifecycle"

APPROVAL_REQUIRED_TAG = "requires_approval"
FRESHNESS_REQUIRED_TAG = "requires_freshness"
RUNTIME_ACTIVE_TAG = "runtime_active"

EnumT = TypeVar("EnumT", bound=Enum)


@unique
class LifecycleContractStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"


@unique
class CompatibilityDomain(str, Enum):
    DATA_PROTOCOL = "data_protocol"
    STRATEGY_PROTOCOL = "strategy_protocol"
    OPS_PROTOCOL = "ops_protocol"
    POLICY_BUNDLE_HASH = "policy_bundle_hash"
    COMPATIBILITY_MATRIX_VERSION = "compatibility_matrix_version"


DEFAULT_COMPATIBILITY_DOMAIN_IDS = tuple(domain.value for domain in CompatibilityDomain)


@dataclass(frozen=True)
class LifecycleStateSpec:
    state_id: str
    summary: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "summary": self.summary,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class LifecycleMachineSpec:
    machine_id: str
    title: str
    initial_state: str
    terminal_states: tuple[str, ...]
    states: tuple[LifecycleStateSpec, ...]
    allowed_transitions: dict[str, tuple[str, ...]]
    notes: str
    schema_version: int = SUPPORTED_LIFECYCLE_SPEC_SCHEMA_VERSION

    def state_ids(self) -> tuple[str, ...]:
        return tuple(state.state_id for state in self.states)

    def state_spec(self, state_id: str) -> LifecycleStateSpec:
        for state in self.states:
            if state.state_id == state_id:
                return state
        raise KeyError(state_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "machine_id": self.machine_id,
            "title": self.title,
            "initial_state": self.initial_state,
            "terminal_states": list(self.terminal_states),
            "schema_version": self.schema_version,
            "states": [state.to_dict() for state in self.states],
            "allowed_transitions": {
                state_id: list(next_states)
                for state_id, next_states in self.allowed_transitions.items()
            },
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CompatibilityDomainSpec:
    domain_id: CompatibilityDomain
    title: str
    description: str
    canonical_evidence_fields: tuple[str, ...]
    consumers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "domain_id": self.domain_id.value,
            "title": self.title,
            "description": self.description,
            "canonical_evidence_fields": list(self.canonical_evidence_fields),
            "consumers": list(self.consumers),
        }


@dataclass(frozen=True)
class TransitionLog:
    machine_id: str
    from_state: str
    to_state: str
    allowed: bool
    allowed_next_states: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "machine_id": self.machine_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "allowed": self.allowed,
            "allowed_next_states": list(self.allowed_next_states),
        }


@dataclass(frozen=True)
class LifecycleTransitionReport:
    case_id: str
    machine_id: str
    status: str
    reason_code: str
    from_state: str
    to_state: str
    transition_log: TransitionLog
    explanation: str
    remediation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "machine_id": self.machine_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "transition_log": self.transition_log.to_dict(),
            "explanation": self.explanation,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class CompatibilityBindingRequest:
    case_id: str
    subject_ref: str
    provided_domains: dict[str, str]
    required_domains: tuple[str, ...] = DEFAULT_COMPATIBILITY_DOMAIN_IDS


@dataclass(frozen=True)
class CompatibilityBindingReport:
    case_id: str
    subject_ref: str
    status: str
    reason_code: str
    required_domains: tuple[str, ...]
    provided_domains: dict[str, str]
    missing_domains: tuple[str, ...]
    unknown_domains: tuple[str, ...]
    blank_domains: tuple[str, ...]
    explanation: str
    remediation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "subject_ref": self.subject_ref,
            "status": self.status,
            "reason_code": self.reason_code,
            "required_domains": list(self.required_domains),
            "provided_domains": self.provided_domains,
            "missing_domains": list(self.missing_domains),
            "unknown_domains": list(self.unknown_domains),
            "blank_domains": list(self.blank_domains),
            "explanation": self.explanation,
            "remediation": self.remediation,
        }


STATE_MACHINE_SPECS: tuple[LifecycleMachineSpec, ...] = (
    LifecycleMachineSpec(
        machine_id=RELEASE_DATASET_MACHINE_ID,
        title="Dataset release lifecycle",
        initial_state="DRAFT",
        terminal_states=("REVOKED",),
        states=(
            LifecycleStateSpec("DRAFT", "The dataset release exists but is not yet staged for certification."),
            LifecycleStateSpec(
                "STAGING",
                "The dataset release is being prepared for certification and may still absorb staging-time checks.",
            ),
            LifecycleStateSpec("CERTIFIED", "Validation and certification checks have passed."),
            LifecycleStateSpec("APPROVED", "The release is approved for activation."),
            LifecycleStateSpec("ACTIVE", "The release may seed new promotable work."),
            LifecycleStateSpec("SUPERSEDED", "The release remains reproducible but no longer seeds new work."),
            LifecycleStateSpec("QUARANTINED", "The release is blocked while an operator investigates issues."),
            LifecycleStateSpec("REVOKED", "The release is historically traceable but may not be reused."),
        ),
        allowed_transitions={
            "DRAFT": ("STAGING", "CERTIFIED", "REVOKED"),
            "STAGING": ("CERTIFIED", "QUARANTINED", "REVOKED"),
            "CERTIFIED": ("APPROVED", "QUARANTINED", "REVOKED"),
            "APPROVED": ("ACTIVE", "QUARANTINED", "REVOKED"),
            "ACTIVE": ("SUPERSEDED", "QUARANTINED", "REVOKED"),
            "SUPERSEDED": ("QUARANTINED", "REVOKED"),
            "QUARANTINED": ("APPROVED", "ACTIVE", "SUPERSEDED", "REVOKED"),
            "REVOKED": (),
        },
        notes="Datasets keep the extra STAGING step because feed semantics and lineage may need operator review before they become certified.",
    ),
    LifecycleMachineSpec(
        machine_id=RELEASE_DERIVED_MACHINE_ID,
        title="Derived release lifecycle",
        initial_state="DRAFT",
        terminal_states=("REVOKED",),
        states=(
            LifecycleStateSpec("DRAFT", "The derived release exists but is not yet certified."),
            LifecycleStateSpec("CERTIFIED", "The derived release passed its certification contract."),
            LifecycleStateSpec("APPROVED", "The derived release is approved for activation."),
            LifecycleStateSpec("ACTIVE", "The derived release may seed new promotable work."),
            LifecycleStateSpec("SUPERSEDED", "The derived release remains reproducible but should not seed new work."),
            LifecycleStateSpec("QUARANTINED", "The derived release is blocked while issues are investigated."),
            LifecycleStateSpec("REVOKED", "The derived release is permanently unusable for new work."),
        ),
        allowed_transitions={
            "DRAFT": ("CERTIFIED", "REVOKED"),
            "CERTIFIED": ("APPROVED", "QUARANTINED", "REVOKED"),
            "APPROVED": ("ACTIVE", "QUARANTINED", "REVOKED"),
            "ACTIVE": ("SUPERSEDED", "QUARANTINED", "REVOKED"),
            "SUPERSEDED": ("QUARANTINED", "REVOKED"),
            "QUARANTINED": ("APPROVED", "ACTIVE", "SUPERSEDED", "REVOKED"),
            "REVOKED": (),
        },
        notes="Analytic and data-profile releases skip STAGING and move directly from DRAFT into certification.",
    ),
    LifecycleMachineSpec(
        machine_id=BUNDLE_READINESS_MACHINE_ID,
        title="Candidate-bundle readiness lifecycle",
        initial_state="FROZEN",
        terminal_states=("REVOKED",),
        states=(
            LifecycleStateSpec("FROZEN", "The candidate bundle has been frozen and awaits readiness checks."),
            LifecycleStateSpec("PORTABILITY_PENDING", "Portability checks have been requested but not yet passed."),
            LifecycleStateSpec(
                "PORTABILITY_PASSED",
                "Portability checks passed.",
                tags=(APPROVAL_REQUIRED_TAG,),
            ),
            LifecycleStateSpec("REPLAY_PENDING", "Replay checks have been requested but not yet passed."),
            LifecycleStateSpec(
                "REPLAY_PASSED",
                "Replay checks passed.",
                tags=(APPROVAL_REQUIRED_TAG,),
            ),
            LifecycleStateSpec(
                "PAPER_ELIGIBLE",
                "The candidate may start paper execution.",
                tags=(APPROVAL_REQUIRED_TAG, FRESHNESS_REQUIRED_TAG),
            ),
            LifecycleStateSpec(
                "PAPER_PASSED",
                "Paper execution evidence passed.",
                tags=(APPROVAL_REQUIRED_TAG, FRESHNESS_REQUIRED_TAG),
            ),
            LifecycleStateSpec(
                "SHADOW_ELIGIBLE",
                "The candidate may start shadow-live execution.",
                tags=(APPROVAL_REQUIRED_TAG, FRESHNESS_REQUIRED_TAG),
            ),
            LifecycleStateSpec(
                "SHADOW_PASSED",
                "Shadow-live evidence passed.",
                tags=(APPROVAL_REQUIRED_TAG, FRESHNESS_REQUIRED_TAG),
            ),
            LifecycleStateSpec(
                "LIVE_ELIGIBLE",
                "The candidate may advance into live promotion.",
                tags=(APPROVAL_REQUIRED_TAG, FRESHNESS_REQUIRED_TAG),
            ),
            LifecycleStateSpec("RECERT_REQUIRED", "The candidate must re-run certification or readiness evidence."),
            LifecycleStateSpec("SUSPECT", "The candidate remains traceable but is currently unsafe to advance."),
            LifecycleStateSpec("REVOKED", "The candidate may never advance again."),
        ),
        allowed_transitions={
            "FROZEN": ("PORTABILITY_PENDING", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "PORTABILITY_PENDING": ("PORTABILITY_PASSED", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "PORTABILITY_PASSED": ("REPLAY_PENDING", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "REPLAY_PENDING": ("REPLAY_PASSED", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "REPLAY_PASSED": ("PAPER_ELIGIBLE", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "PAPER_ELIGIBLE": ("PAPER_PASSED", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "PAPER_PASSED": ("SHADOW_ELIGIBLE", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "SHADOW_ELIGIBLE": ("SHADOW_PASSED", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "SHADOW_PASSED": ("LIVE_ELIGIBLE", "RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "LIVE_ELIGIBLE": ("RECERT_REQUIRED", "SUSPECT", "REVOKED"),
            "RECERT_REQUIRED": ("PORTABILITY_PENDING", "REPLAY_PENDING", "SUSPECT", "REVOKED"),
            "SUSPECT": ("RECERT_REQUIRED", "REVOKED"),
            "REVOKED": (),
        },
        notes="Readiness states encode the plan-defined promotion ladder from frozen bundle through paper, shadow, and live eligibility.",
    ),
    LifecycleMachineSpec(
        machine_id=DEPLOYMENT_INSTANCE_MACHINE_ID,
        title="Deployment instance lifecycle",
        initial_state="PAPER_PENDING",
        terminal_states=("CLOSED",),
        states=(
            LifecycleStateSpec("PAPER_PENDING", "Paper deployment exists but has not started."),
            LifecycleStateSpec("PAPER_RUNNING", "Paper deployment is actively running.", tags=(RUNTIME_ACTIVE_TAG,)),
            LifecycleStateSpec("SHADOW_PENDING", "Shadow-live deployment exists but has not started."),
            LifecycleStateSpec("SHADOW_RUNNING", "Shadow-live deployment is actively running.", tags=(RUNTIME_ACTIVE_TAG,)),
            LifecycleStateSpec("LIVE_CANARY", "Live deployment is running in canary mode.", tags=(RUNTIME_ACTIVE_TAG,)),
            LifecycleStateSpec("LIVE_ACTIVE", "Live deployment is fully active.", tags=(RUNTIME_ACTIVE_TAG,)),
            LifecycleStateSpec("WITHDRAWN", "Deployment has been withdrawn and awaits closure."),
            LifecycleStateSpec("CLOSED", "Deployment is fully closed and no longer mutable."),
        ),
        allowed_transitions={
            "PAPER_PENDING": ("PAPER_RUNNING", "WITHDRAWN", "CLOSED"),
            "PAPER_RUNNING": ("WITHDRAWN", "CLOSED"),
            "SHADOW_PENDING": ("SHADOW_RUNNING", "WITHDRAWN", "CLOSED"),
            "SHADOW_RUNNING": ("WITHDRAWN", "CLOSED"),
            "LIVE_CANARY": ("LIVE_ACTIVE", "WITHDRAWN", "CLOSED"),
            "LIVE_ACTIVE": ("WITHDRAWN", "CLOSED"),
            "WITHDRAWN": ("CLOSED",),
            "CLOSED": (),
        },
        notes="Deployment states intentionally keep pending and running sub-machines separate per lane so operators can reason about withdrawals and closures deterministically.",
    ),
    LifecycleMachineSpec(
        machine_id=RESEARCH_RUN_MACHINE_ID,
        title="Research run lifecycle",
        initial_state="recorded",
        terminal_states=("superseded", "revoked"),
        states=(
            LifecycleStateSpec("recorded", "The research run is retained and auditable."),
            LifecycleStateSpec("superseded", "A newer research run replaced this one."),
            LifecycleStateSpec("quarantined", "The research run is under investigation."),
            LifecycleStateSpec("revoked", "The research run is permanently unusable."),
        ),
        allowed_transitions={
            "recorded": ("superseded", "quarantined", "revoked"),
            "superseded": (),
            "quarantined": ("revoked",),
            "revoked": (),
        },
        notes="Research runs are immutable records; they may only narrow into historical or blocked states.",
    ),
    LifecycleMachineSpec(
        machine_id=FAMILY_DECISION_MACHINE_ID,
        title="Family decision lifecycle",
        initial_state="active",
        terminal_states=("superseded", "expired"),
        states=(
            LifecycleStateSpec("active", "The family decision is currently in force."),
            LifecycleStateSpec("superseded", "A newer decision replaced this one."),
            LifecycleStateSpec("expired", "The decision timed out and needs renewal."),
        ),
        allowed_transitions={
            "active": ("superseded", "expired"),
            "superseded": (),
            "expired": (),
        },
        notes="Family-level governance decisions stay simple so budget and continuation reviews cannot drift into ambiguous intermediate states.",
    ),
)


COMPATIBILITY_DOMAIN_SPECS: tuple[CompatibilityDomainSpec, ...] = (
    CompatibilityDomainSpec(
        domain_id=CompatibilityDomain.DATA_PROTOCOL,
        title="Data protocol",
        description="Release lineage and feed semantics that define what bars, datasets, and context objects mean.",
        canonical_evidence_fields=("dataset_release_id", "data_profile_release_id", "resolved_context_bundle_id"),
        consumers=("research runs", "candidate freezing", "promotion packets", "startup checks"),
    ),
    CompatibilityDomainSpec(
        domain_id=CompatibilityDomain.STRATEGY_PROTOCOL,
        title="Strategy protocol",
        description="Signal-kernel, execution-profile, and parameterization bindings that make the strategy behavior reproducible.",
        canonical_evidence_fields=(
            "analytic_release_id",
            "signal_kernel_digest",
            "kernel_abi_version",
            "state_serialization_version",
        ),
        consumers=("research runs", "candidate bundles", "runtime startup"),
    ),
    CompatibilityDomainSpec(
        domain_id=CompatibilityDomain.OPS_PROTOCOL,
        title="Ops protocol",
        description="Operational and runtime expectations that must align before readiness, activation, or recovery.",
        canonical_evidence_fields=(
            "required_broker_capability_profile_id",
            "operating_envelope_profile_id",
            "target_account_binding_id",
        ),
        consumers=("bundle readiness", "promotion packets", "runtime startup", "recovery drills"),
    ),
    CompatibilityDomainSpec(
        domain_id=CompatibilityDomain.POLICY_BUNDLE_HASH,
        title="Policy bundle hash",
        description="The exact policy bundle hash that authorized the decision or activation workflow.",
        canonical_evidence_fields=("policy_bundle_hash",),
        consumers=("readiness records", "promotion packets", "governance workflows"),
    ),
    CompatibilityDomainSpec(
        domain_id=CompatibilityDomain.COMPATIBILITY_MATRIX_VERSION,
        title="Compatibility matrix version",
        description="The shared compatibility matrix version that later startup checks and migrations can compare directly.",
        canonical_evidence_fields=("compatibility_matrix_version",),
        consumers=("research runs", "candidate bundles", "promotion packets", "startup checks"),
    ),
)


def state_machine_spec(machine_id: str) -> LifecycleMachineSpec:
    for spec in STATE_MACHINE_SPECS:
        if spec.machine_id == machine_id:
            return spec
    raise KeyError(machine_id)


def compatibility_domain_spec(domain_id: str) -> CompatibilityDomainSpec:
    domain = CompatibilityDomain(domain_id)
    for spec in COMPATIBILITY_DOMAIN_SPECS:
        if spec.domain_id == domain:
            return spec
    raise KeyError(domain_id)


def build_enum_transition_map(
    machine_id: str, enum_type: type[EnumT]
) -> dict[EnumT, frozenset[EnumT]]:
    spec = state_machine_spec(machine_id)
    return {
        enum_type(state_id): frozenset(enum_type(next_state) for next_state in next_states)
        for state_id, next_states in spec.allowed_transitions.items()
    }


def build_tuple_transition_map(
    machine_id: str, enum_type: type[EnumT]
) -> dict[EnumT, tuple[EnumT, ...]]:
    spec = state_machine_spec(machine_id)
    return {
        enum_type(state_id): tuple(enum_type(next_state) for next_state in next_states)
        for state_id, next_states in spec.allowed_transitions.items()
    }


def states_with_tag(machine_id: str, tag: str, enum_type: type[EnumT]) -> frozenset[EnumT]:
    spec = state_machine_spec(machine_id)
    return frozenset(
        enum_type(state.state_id)
        for state in spec.states
        if tag in state.tags
    )


def evaluate_transition(
    case_id: str,
    machine_id: str,
    from_state: str,
    to_state: str,
) -> LifecycleTransitionReport:
    try:
        spec = state_machine_spec(machine_id)
    except KeyError:
        transition_log = TransitionLog(
            machine_id=machine_id,
            from_state=from_state,
            to_state=to_state,
            allowed=False,
            allowed_next_states=(),
        )
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine_id,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="STATE_MACHINE_UNKNOWN_MACHINE",
            from_state=from_state,
            to_state=to_state,
            transition_log=transition_log,
            explanation="The requested machine does not exist in the canonical lifecycle catalog.",
            remediation="Use one of the declared lifecycle machine identifiers.",
        )

    state_ids = spec.state_ids()
    allowed_next_states = spec.allowed_transitions.get(from_state, ())
    transition_log = TransitionLog(
        machine_id=machine_id,
        from_state=from_state,
        to_state=to_state,
        allowed=to_state in allowed_next_states,
        allowed_next_states=allowed_next_states,
    )

    if from_state not in state_ids or to_state not in state_ids:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine_id,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="STATE_MACHINE_UNKNOWN_STATE",
            from_state=from_state,
            to_state=to_state,
            transition_log=transition_log,
            explanation="The requested transition references a state outside the canonical lifecycle spec.",
            remediation="Use only state identifiers declared in the shared lifecycle catalog.",
        )

    if from_state == to_state:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine_id,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="STATE_MACHINE_NO_STATE_CHANGE",
            from_state=from_state,
            to_state=to_state,
            transition_log=transition_log,
            explanation="Lifecycle transitions must change state so downstream tooling can react deterministically.",
            remediation="Submit an actual transition or leave the record unchanged.",
        )

    if to_state not in allowed_next_states:
        return LifecycleTransitionReport(
            case_id=case_id,
            machine_id=machine_id,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="STATE_MACHINE_TRANSITION_NOT_ALLOWED",
            from_state=from_state,
            to_state=to_state,
            transition_log=transition_log,
            explanation="The requested transition is not part of the canonical lifecycle state machine.",
            remediation="Advance the record only through the plan-defined transitions.",
        )

    transition_log = TransitionLog(
        machine_id=machine_id,
        from_state=from_state,
        to_state=to_state,
        allowed=True,
        allowed_next_states=allowed_next_states,
    )
    return LifecycleTransitionReport(
        case_id=case_id,
        machine_id=machine_id,
        status=LifecycleContractStatus.PASS.value,
        reason_code="STATE_MACHINE_TRANSITION_ALLOWED",
        from_state=from_state,
        to_state=to_state,
        transition_log=transition_log,
        explanation="The requested transition is allowed by the canonical lifecycle state machine.",
        remediation="No remediation required.",
    )


def evaluate_compatibility_binding(
    request: CompatibilityBindingRequest,
) -> CompatibilityBindingReport:
    provided_domains = {
        str(domain_id): str(value)
        for domain_id, value in request.provided_domains.items()
    }
    known_domains = set(DEFAULT_COMPATIBILITY_DOMAIN_IDS)
    required_domains = tuple(str(domain_id) for domain_id in request.required_domains)
    unknown_domains = tuple(sorted(set(provided_domains).difference(known_domains)))
    missing_domains = tuple(
        domain_id for domain_id in required_domains if domain_id not in provided_domains
    )
    blank_domains = tuple(
        domain_id
        for domain_id in required_domains
        if domain_id in provided_domains and not provided_domains[domain_id].strip()
    )

    if unknown_domains:
        return CompatibilityBindingReport(
            case_id=request.case_id,
            subject_ref=request.subject_ref,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="COMPATIBILITY_DOMAIN_UNKNOWN",
            required_domains=required_domains,
            provided_domains=provided_domains,
            missing_domains=missing_domains,
            unknown_domains=unknown_domains,
            blank_domains=blank_domains,
            explanation="The provided compatibility context names a domain outside the canonical catalog.",
            remediation="Use only the declared compatibility domain identifiers.",
        )

    if missing_domains:
        return CompatibilityBindingReport(
            case_id=request.case_id,
            subject_ref=request.subject_ref,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="COMPATIBILITY_DOMAIN_MISSING",
            required_domains=required_domains,
            provided_domains=provided_domains,
            missing_domains=missing_domains,
            unknown_domains=unknown_domains,
            blank_domains=blank_domains,
            explanation="The compatibility context omitted one or more required domains.",
            remediation="Bind every required compatibility domain before startup, migration, or promotion.",
        )

    if blank_domains:
        return CompatibilityBindingReport(
            case_id=request.case_id,
            subject_ref=request.subject_ref,
            status=LifecycleContractStatus.INVALID.value,
            reason_code="COMPATIBILITY_DOMAIN_VALUE_MISSING",
            required_domains=required_domains,
            provided_domains=provided_domains,
            missing_domains=missing_domains,
            unknown_domains=unknown_domains,
            blank_domains=blank_domains,
            explanation="A required compatibility domain was present but blank, so downstream checks cannot compare it deterministically.",
            remediation="Populate every required compatibility domain with a stable non-empty value.",
        )

    return CompatibilityBindingReport(
        case_id=request.case_id,
        subject_ref=request.subject_ref,
        status=LifecycleContractStatus.PASS.value,
        reason_code="COMPATIBILITY_DOMAINS_BOUND",
        required_domains=required_domains,
        provided_domains=provided_domains,
        missing_domains=(),
        unknown_domains=(),
        blank_domains=(),
        explanation="Every required compatibility domain is bound and can be cited directly by startup, migration, and promotion checks.",
        remediation="No remediation required.",
    )


def validate_contract() -> list[str]:
    errors: list[str] = []
    machine_ids: set[str] = set()
    for spec in STATE_MACHINE_SPECS:
        if spec.machine_id in machine_ids:
            errors.append(f"{spec.machine_id}: machine identifiers must be unique")
        machine_ids.add(spec.machine_id)

        state_ids = spec.state_ids()
        if spec.schema_version != SUPPORTED_LIFECYCLE_SPEC_SCHEMA_VERSION:
            errors.append(f"{spec.machine_id}: unsupported schema_version {spec.schema_version}")
        if len(state_ids) != len(set(state_ids)):
            errors.append(f"{spec.machine_id}: state identifiers must be unique")
        if spec.initial_state not in state_ids:
            errors.append(f"{spec.machine_id}: initial_state must be declared")
        if not set(spec.terminal_states).issubset(set(state_ids)):
            errors.append(f"{spec.machine_id}: terminal_states must be declared states")
        if set(spec.allowed_transitions) != set(state_ids):
            errors.append(f"{spec.machine_id}: transition map must cover every declared state")

        for state in spec.states:
            if len(state.tags) != len(set(state.tags)):
                errors.append(f"{spec.machine_id}:{state.state_id}: tags must be unique")

        for state_id, next_states in spec.allowed_transitions.items():
            if state_id in spec.terminal_states and next_states:
                errors.append(f"{spec.machine_id}:{state_id}: terminal states may not have outgoing transitions")
            for next_state in next_states:
                if next_state not in state_ids:
                    errors.append(
                        f"{spec.machine_id}:{state_id}: transition references unknown state {next_state}"
                    )

    domain_ids = tuple(spec.domain_id.value for spec in COMPATIBILITY_DOMAIN_SPECS)
    if domain_ids != DEFAULT_COMPATIBILITY_DOMAIN_IDS:
        errors.append("compatibility domains must match the canonical plan order")

    if len(domain_ids) != len(set(domain_ids)):
        errors.append("compatibility domains must be unique")

    for spec in COMPATIBILITY_DOMAIN_SPECS:
        if not spec.canonical_evidence_fields:
            errors.append(f"{spec.domain_id.value}: canonical_evidence_fields may not be empty")
        if not spec.consumers:
            errors.append(f"{spec.domain_id.value}: consumers may not be empty")

    return errors


def contract_snapshot() -> dict[str, object]:
    return {
        "schema_version": SUPPORTED_LIFECYCLE_SPEC_SCHEMA_VERSION,
        "state_machines": [spec.to_dict() for spec in STATE_MACHINE_SPECS],
        "compatibility_domains": [spec.to_dict() for spec in COMPATIBILITY_DOMAIN_SPECS],
    }


def to_json() -> str:
    return json.dumps(contract_snapshot(), indent=2, sort_keys=True)


VALIDATION_ERRORS = validate_contract()
