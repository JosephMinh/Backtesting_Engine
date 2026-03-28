"""Stable strategy-contract and canonical signal-kernel policy surface."""

from __future__ import annotations

import datetime
import json
import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.guardrails import check_shared_kernel
from shared.policy.lifecycle_compatibility import CompatibilityDomain, COMPATIBILITY_DOMAIN_INDEX


SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION = 1
ALLOWED_DECISION_BASES = ("bar_close", "one_bar_late")
REQUIRED_ORDER_INTENT_FIELDS = (
    "intent_id",
    "strategy_decision_id",
    "symbol",
    "side",
    "quantity",
    "order_type",
    "time_in_force",
)
MIN_EQUIVALENCE_PROPERTY_CASES = 1
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(value)
    if match is None:
        return None
    return tuple(int(component) for component in match.groups())


def _parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name}: must be timezone-aware")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a non-empty string")
    parsed = value.strip()
    if not parsed:
        raise ValueError(f"{field_name}: must be a non-empty string")
    return parsed


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be boolean")
    return value


def _require_int(
    value: object,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}: must be an integer")
    if minimum is not None and value < minimum:
        qualifier = "positive" if minimum == 1 else f">= {minimum}"
        raise ValueError(f"{field_name}: must be {qualifier}")
    return value


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of strings")
    return tuple(_require_non_empty_string(item, field_name=field_name) for item in value)


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of objects")
    return tuple(_require_mapping(item, field_name=field_name) for item in value)


def _require_schema_version(value: object, *, field_name: str) -> int:
    parsed = _require_int(value, field_name=field_name, minimum=1)
    if parsed != SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"{field_name}: unsupported schema version {parsed}; "
            f"expected {SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION}"
        )
    return parsed


def _require_enum_value(
    value: object,
    *,
    field_name: str,
    enum_type: type[Enum],
    description: str,
) -> str:
    if isinstance(value, enum_type):
        return value.value
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid {description}")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid {description}") from exc


def _require_decision_basis(value: object, *, field_name: str) -> str:
    parsed = _require_non_empty_string(value, field_name=field_name)
    if parsed not in ALLOWED_DECISION_BASES:
        raise ValueError(f"{field_name}: must be a valid decision basis")
    return parsed


def _require_semver(value: object, *, field_name: str) -> str:
    parsed = _require_non_empty_string(value, field_name=field_name)
    if _parse_semver(parsed) is None:
        raise ValueError(f"{field_name}: must be a valid semantic version")
    return parsed


def _require_finite_mapping(
    value: object,
    *,
    field_name: str,
) -> dict[str, float]:
    mapping = _require_mapping(value, field_name=field_name)
    normalized: dict[str, float] = {}
    for key, item in mapping.items():
        normalized[_require_non_empty_string(key, field_name=field_name)] = _require_finite_float(
            item,
            field_name=field_name,
        )
    return normalized


def _require_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}: must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name}: must be finite")
    return parsed


def strategy_protocol_evidence_fields() -> tuple[str, ...]:
    return COMPATIBILITY_DOMAIN_INDEX[
        CompatibilityDomain.STRATEGY_PROTOCOL.value
    ].required_evidence_fields


@unique
class StrategyContractStatus(str, Enum):
    PASS = "pass"
    INVALID = "invalid"
    VIOLATION = "violation"
    INCOMPATIBLE = "incompatible"


@unique
class StrategyLifecycleClass(str, Enum):
    RESEARCH_ONLY = "research_only"
    PROMOTABLE = "promotable"
    LIVE_ELIGIBLE = "live_eligible"


@unique
class KernelImplementationKind(str, Enum):
    PYTHON = "python"
    RUST = "rust"


@dataclass(frozen=True)
class StrategyDependency:
    node_id: str
    depends_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyDependency":
        payload = _require_mapping(payload, field_name="strategy_dependency")
        return cls(
            node_id=_require_non_empty_string(payload["node_id"], field_name="node_id"),
            depends_on=_require_string_sequence(
                payload.get("depends_on", ()),
                field_name="depends_on",
            ),
        )


@dataclass(frozen=True)
class DecisionCadence:
    decision_basis: str
    interval_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionCadence":
        payload = _require_mapping(payload, field_name="decision_cadence")
        return cls(
            decision_basis=_require_decision_basis(
                payload["decision_basis"],
                field_name="decision_basis",
            ),
            interval_seconds=_require_int(
                payload["interval_seconds"],
                field_name="interval_seconds",
                minimum=1,
            ),
        )


@dataclass(frozen=True)
class WarmupRequirement:
    min_history_bars: int
    min_history_minutes: int
    requires_state_seed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WarmupRequirement":
        payload = _require_mapping(payload, field_name="warmup")
        return cls(
            min_history_bars=_require_int(
                payload["min_history_bars"],
                field_name="min_history_bars",
                minimum=0,
            ),
            min_history_minutes=_require_int(
                payload["min_history_minutes"],
                field_name="min_history_minutes",
                minimum=0,
            ),
            requires_state_seed=_require_bool(
                payload["requires_state_seed"],
                field_name="requires_state_seed",
            ),
        )


@dataclass(frozen=True)
class OrderIntentSchema:
    schema_id: str
    required_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OrderIntentSchema":
        payload = _require_mapping(payload, field_name="order_intent_schema")
        return cls(
            schema_id=_require_non_empty_string(payload["schema_id"], field_name="schema_id"),
            required_fields=_require_string_sequence(
                payload["required_fields"],
                field_name="required_fields",
            ),
        )


@dataclass(frozen=True)
class SignalKernelContract:
    signal_kernel_digest: str
    research_kernel_hash: str
    live_kernel_hash: str
    canonical_implementation_kind: str
    rust_crate: str | None
    python_binding_module: str | None
    python_promotable_logic_present: bool
    kernel_abi_version: str
    state_serialization_version: str
    semantic_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SignalKernelContract":
        payload = _require_mapping(payload, field_name="signal_kernel")
        return cls(
            signal_kernel_digest=_require_non_empty_string(
                payload["signal_kernel_digest"],
                field_name="signal_kernel_digest",
            ),
            research_kernel_hash=_require_non_empty_string(
                payload["research_kernel_hash"],
                field_name="research_kernel_hash",
            ),
            live_kernel_hash=_require_non_empty_string(
                payload["live_kernel_hash"],
                field_name="live_kernel_hash",
            ),
            canonical_implementation_kind=_require_enum_value(
                payload["canonical_implementation_kind"],
                field_name="canonical_implementation_kind",
                enum_type=KernelImplementationKind,
                description="kernel implementation kind",
            ),
            rust_crate=_require_optional_non_empty_string(
                payload.get("rust_crate"),
                field_name="rust_crate",
            ),
            python_binding_module=_require_optional_non_empty_string(
                payload.get("python_binding_module"),
                field_name="python_binding_module",
            ),
            python_promotable_logic_present=_require_bool(
                payload["python_promotable_logic_present"],
                field_name="python_promotable_logic_present",
            ),
            kernel_abi_version=_require_non_empty_string(
                payload["kernel_abi_version"],
                field_name="kernel_abi_version",
            ),
            state_serialization_version=_require_non_empty_string(
                payload["state_serialization_version"],
                field_name="state_serialization_version",
            ),
            semantic_version=_require_semver(
                payload["semantic_version"],
                field_name="semantic_version",
            ),
        )


@dataclass(frozen=True)
class EquivalenceCertification:
    certification_id: str | None
    golden_session_fixture_id: str | None
    property_case_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EquivalenceCertification":
        payload = _require_mapping(payload, field_name="equivalence_certification")
        return cls(
            certification_id=_require_optional_non_empty_string(
                payload.get("certification_id"),
                field_name="certification_id",
            ),
            golden_session_fixture_id=_require_optional_non_empty_string(
                payload.get("golden_session_fixture_id"),
                field_name="golden_session_fixture_id",
            ),
            property_case_count=_require_int(
                payload["property_case_count"],
                field_name="property_case_count",
                minimum=0,
            ),
        )


@dataclass(frozen=True)
class StrategyContract:
    contract_id: str
    strategy_family_id: str
    lifecycle_class: str
    parameter_schema_id: str
    required_inputs: tuple[str, ...]
    decision_cadence: DecisionCadence
    warmup: WarmupRequirement
    risk_control_hooks: tuple[str, ...]
    order_intent_schema: OrderIntentSchema
    dependency_dag: tuple[StrategyDependency, ...]
    signal_kernel: SignalKernelContract
    candidate_freeze_ready: bool
    equivalence_certification: EquivalenceCertification
    schema_version: int = SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision_cadence"] = self.decision_cadence.to_dict()
        payload["warmup"] = self.warmup.to_dict()
        payload["order_intent_schema"] = self.order_intent_schema.to_dict()
        payload["dependency_dag"] = [node.to_dict() for node in self.dependency_dag]
        payload["signal_kernel"] = self.signal_kernel.to_dict()
        payload["equivalence_certification"] = self.equivalence_certification.to_dict()
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyContract":
        payload = _require_mapping(payload, field_name="strategy_contract")
        return cls(
            contract_id=_require_non_empty_string(payload["contract_id"], field_name="contract_id"),
            strategy_family_id=_require_non_empty_string(
                payload["strategy_family_id"],
                field_name="strategy_family_id",
            ),
            lifecycle_class=_require_enum_value(
                payload["lifecycle_class"],
                field_name="lifecycle_class",
                enum_type=StrategyLifecycleClass,
                description="strategy lifecycle class",
            ),
            parameter_schema_id=_require_non_empty_string(
                payload["parameter_schema_id"],
                field_name="parameter_schema_id",
            ),
            required_inputs=_require_string_sequence(
                payload["required_inputs"],
                field_name="required_inputs",
            ),
            decision_cadence=DecisionCadence.from_dict(
                _require_mapping(payload["decision_cadence"], field_name="decision_cadence")
            ),
            warmup=WarmupRequirement.from_dict(
                _require_mapping(payload["warmup"], field_name="warmup")
            ),
            risk_control_hooks=_require_string_sequence(
                payload["risk_control_hooks"],
                field_name="risk_control_hooks",
            ),
            order_intent_schema=OrderIntentSchema.from_dict(
                _require_mapping(payload["order_intent_schema"], field_name="order_intent_schema")
            ),
            dependency_dag=tuple(
                StrategyDependency.from_dict(item)
                for item in _require_object_sequence(
                    payload["dependency_dag"],
                    field_name="dependency_dag",
                )
            ),
            signal_kernel=SignalKernelContract.from_dict(
                _require_mapping(payload["signal_kernel"], field_name="signal_kernel")
            ),
            candidate_freeze_ready=_require_bool(
                payload["candidate_freeze_ready"],
                field_name="candidate_freeze_ready",
            ),
            equivalence_certification=EquivalenceCertification.from_dict(
                _require_mapping(
                    payload["equivalence_certification"],
                    field_name="equivalence_certification",
                )
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version", SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "StrategyContract":
        return cls.from_dict(_decode_json_object(payload, label="strategy_contract"))


@dataclass(frozen=True)
class StrategyContractReport:
    contract_id: str
    strategy_family_id: str
    status: str
    reason_code: str
    stable_contract_complete: bool
    canonical_kernel_rule_satisfied: bool
    equivalence_certification_required: bool
    equivalence_certification_ready: bool
    dependency_dag_acyclic: bool
    strategy_protocol_evidence_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    violated_guarantees: tuple[str, ...]
    guardrail_result: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyContractReport":
        payload = _require_mapping(payload, field_name="strategy_contract_report")
        return cls(
            contract_id=_require_non_empty_string(payload["contract_id"], field_name="contract_id"),
            strategy_family_id=_require_non_empty_string(
                payload["strategy_family_id"],
                field_name="strategy_family_id",
            ),
            status=_require_enum_value(
                payload["status"],
                field_name="status",
                enum_type=StrategyContractStatus,
                description="strategy contract status",
            ),
            reason_code=_require_non_empty_string(payload["reason_code"], field_name="reason_code"),
            stable_contract_complete=_require_bool(
                payload["stable_contract_complete"],
                field_name="stable_contract_complete",
            ),
            canonical_kernel_rule_satisfied=_require_bool(
                payload["canonical_kernel_rule_satisfied"],
                field_name="canonical_kernel_rule_satisfied",
            ),
            equivalence_certification_required=_require_bool(
                payload["equivalence_certification_required"],
                field_name="equivalence_certification_required",
            ),
            equivalence_certification_ready=_require_bool(
                payload["equivalence_certification_ready"],
                field_name="equivalence_certification_ready",
            ),
            dependency_dag_acyclic=_require_bool(
                payload["dependency_dag_acyclic"],
                field_name="dependency_dag_acyclic",
            ),
            strategy_protocol_evidence_fields=_require_string_sequence(
                payload["strategy_protocol_evidence_fields"],
                field_name="strategy_protocol_evidence_fields",
            ),
            missing_fields=_require_string_sequence(
                payload["missing_fields"],
                field_name="missing_fields",
            ),
            violated_guarantees=_require_string_sequence(
                payload["violated_guarantees"],
                field_name="violated_guarantees",
            ),
            guardrail_result=_require_mapping(
                payload["guardrail_result"],
                field_name="guardrail_result",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "StrategyContractReport":
        return cls.from_dict(_decode_json_object(payload, label="strategy_contract_report"))


@dataclass(frozen=True)
class StrategyContractCompatibilityReport:
    contract_id: str
    previous_semantic_version: str
    current_semantic_version: str
    status: str
    reason_code: str
    compatible: bool
    requires_recertification: bool
    changed_fields: tuple[str, ...]
    broken_guarantees: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyContractCompatibilityReport":
        payload = _require_mapping(payload, field_name="strategy_contract_compatibility_report")
        return cls(
            contract_id=_require_non_empty_string(payload["contract_id"], field_name="contract_id"),
            previous_semantic_version=_require_semver(
                payload["previous_semantic_version"],
                field_name="previous_semantic_version",
            ),
            current_semantic_version=_require_semver(
                payload["current_semantic_version"],
                field_name="current_semantic_version",
            ),
            status=_require_enum_value(
                payload["status"],
                field_name="status",
                enum_type=StrategyContractStatus,
                description="strategy contract status",
            ),
            reason_code=_require_non_empty_string(payload["reason_code"], field_name="reason_code"),
            compatible=_require_bool(payload["compatible"], field_name="compatible"),
            requires_recertification=_require_bool(
                payload["requires_recertification"],
                field_name="requires_recertification",
            ),
            changed_fields=_require_string_sequence(
                payload["changed_fields"],
                field_name="changed_fields",
            ),
            broken_guarantees=_require_string_sequence(
                payload["broken_guarantees"],
                field_name="broken_guarantees",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "StrategyContractCompatibilityReport":
        return cls.from_dict(
            _decode_json_object(payload, label="strategy_contract_compatibility_report")
        )


def _lifecycle_is_promotable(lifecycle_class: str) -> bool:
    return lifecycle_class in {
        StrategyLifecycleClass.PROMOTABLE.value,
        StrategyLifecycleClass.LIVE_ELIGIBLE.value,
    }


def _dependency_graph_state(
    dependencies: tuple[StrategyDependency, ...],
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    node_ids = [dependency.node_id for dependency in dependencies]
    duplicates = tuple(
        node_id for node_id in sorted(set(node_ids)) if node_ids.count(node_id) > 1
    )
    node_set = set(node_ids)
    missing_targets = tuple(
        sorted(
            {
                target
                for dependency in dependencies
                for target in dependency.depends_on
                if target not in node_set
            }
        )
    )
    if duplicates or missing_targets:
        return False, duplicates, missing_targets

    adjacency = {dependency.node_id: dependency.depends_on for dependency in dependencies}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return False
        if node_id in visited:
            return True
        visiting.add(node_id)
        for parent in adjacency.get(node_id, ()):
            if not visit(parent):
                return False
        visiting.remove(node_id)
        visited.add(node_id)
        return True

    for node_id in adjacency:
        if not visit(node_id):
            return False, duplicates, missing_targets

    return True, duplicates, missing_targets


def evaluate_strategy_contract(contract: StrategyContract) -> StrategyContractReport:
    missing_fields: list[str] = []
    violated_guarantees: list[str] = []

    if contract.schema_version != SUPPORTED_STRATEGY_CONTRACT_SCHEMA_VERSION:
        missing_fields.append("schema_version")
    if contract.lifecycle_class not in {item.value for item in StrategyLifecycleClass}:
        missing_fields.append("lifecycle_class")
    if not contract.parameter_schema_id.strip():
        missing_fields.append("parameter_schema_id")
    if not contract.required_inputs:
        missing_fields.append("required_inputs")
    if contract.decision_cadence.decision_basis not in ALLOWED_DECISION_BASES:
        missing_fields.append("decision_cadence.decision_basis")
    if contract.decision_cadence.interval_seconds <= 0:
        missing_fields.append("decision_cadence.interval_seconds")
    if contract.warmup.min_history_bars < 0:
        missing_fields.append("warmup.min_history_bars")
    if contract.warmup.min_history_minutes < 0:
        missing_fields.append("warmup.min_history_minutes")
    if not contract.risk_control_hooks:
        missing_fields.append("risk_control_hooks")
    if not contract.order_intent_schema.schema_id.strip():
        missing_fields.append("order_intent_schema.schema_id")
    missing_order_intent_fields = tuple(
        field_name
        for field_name in REQUIRED_ORDER_INTENT_FIELDS
        if field_name not in contract.order_intent_schema.required_fields
    )
    if missing_order_intent_fields:
        missing_fields.append("order_intent_schema.required_fields")
    if not contract.signal_kernel.signal_kernel_digest.strip():
        missing_fields.append("signal_kernel.signal_kernel_digest")
    if not contract.signal_kernel.kernel_abi_version.strip():
        missing_fields.append("signal_kernel.kernel_abi_version")
    if not contract.signal_kernel.state_serialization_version.strip():
        missing_fields.append("signal_kernel.state_serialization_version")
    if _parse_semver(contract.signal_kernel.semantic_version) is None:
        missing_fields.append("signal_kernel.semantic_version")

    dependency_dag_acyclic, duplicate_nodes, missing_dependency_targets = _dependency_graph_state(
        contract.dependency_dag
    )
    if duplicate_nodes:
        missing_fields.append("dependency_dag.duplicate_nodes")
    if missing_dependency_targets:
        missing_fields.append("dependency_dag.missing_targets")
    if not dependency_dag_acyclic:
        violated_guarantees.append("dependency_dag.cycle")

    guardrail_result = check_shared_kernel(
        research_kernel_hash=contract.signal_kernel.research_kernel_hash,
        live_kernel_hash=contract.signal_kernel.live_kernel_hash,
    ).to_dict()

    promotable = _lifecycle_is_promotable(contract.lifecycle_class)
    if promotable:
        if (
            contract.signal_kernel.canonical_implementation_kind
            != KernelImplementationKind.RUST.value
        ):
            violated_guarantees.append("canonical_kernel.rust_required")
        if not contract.signal_kernel.rust_crate:
            violated_guarantees.append("canonical_kernel.rust_crate_missing")
        if not contract.signal_kernel.python_binding_module:
            violated_guarantees.append("canonical_kernel.python_binding_missing")
        if contract.signal_kernel.python_promotable_logic_present:
            violated_guarantees.append("canonical_kernel.parallel_python_logic")
        if not guardrail_result["passed"]:
            violated_guarantees.append("canonical_kernel.shared_digest_mismatch")

    equivalence_certification_required = contract.candidate_freeze_ready
    equivalence_certification_ready = (
        contract.equivalence_certification.certification_id is not None
        and contract.equivalence_certification.golden_session_fixture_id is not None
        and contract.equivalence_certification.property_case_count
        >= MIN_EQUIVALENCE_PROPERTY_CASES
    )
    if equivalence_certification_required and not equivalence_certification_ready:
        violated_guarantees.append("equivalence_certification.pre_freeze_required")

    stable_contract_complete = not missing_fields and dependency_dag_acyclic
    canonical_kernel_rule_satisfied = not any(
        violation.startswith("canonical_kernel") for violation in violated_guarantees
    )

    if missing_fields:
        status = StrategyContractStatus.INVALID.value
        reason_code = "STRATEGY_CONTRACT_INVALID"
        explanation = (
            "Strategy contract is incomplete or malformed. "
            f"Missing or invalid fields: {missing_fields}."
        )
        remediation = (
            "Populate the required schema, cadence, warm-up, risk-hook, order-intent, "
            "dependency, and version fields before the contract is used."
        )
    elif violated_guarantees:
        status = StrategyContractStatus.VIOLATION.value
        if "equivalence_certification.pre_freeze_required" in violated_guarantees:
            reason_code = "STRATEGY_CONTRACT_EQUIVALENCE_REQUIRED"
        elif "dependency_dag.cycle" in violated_guarantees:
            reason_code = "STRATEGY_CONTRACT_DEPENDENCY_DAG_CYCLE"
        elif "canonical_kernel.parallel_python_logic" in violated_guarantees:
            reason_code = "STRATEGY_CONTRACT_PYTHON_FORK_PRESENT"
        else:
            reason_code = "STRATEGY_CONTRACT_SHARED_KERNEL_REQUIRED"
        explanation = (
            "Strategy contract violated the canonical shared-kernel policy. "
            f"Violated guarantees: {violated_guarantees}."
        )
        remediation = (
            "Use one canonical Rust kernel for promotable work, keep Python limited to "
            "bindings and orchestration, and record equivalence certification before "
            "candidate freeze."
        )
    else:
        status = StrategyContractStatus.PASS.value
        reason_code = "STRATEGY_CONTRACT_PASS"
        explanation = (
            "Strategy contract is complete, the dependency DAG is acyclic, the canonical "
            "kernel rule is satisfied, and pre-freeze equivalence requirements are explicit."
        )
        remediation = "No remediation required."

    return StrategyContractReport(
        contract_id=contract.contract_id,
        strategy_family_id=contract.strategy_family_id,
        status=status,
        reason_code=reason_code,
        stable_contract_complete=stable_contract_complete,
        canonical_kernel_rule_satisfied=canonical_kernel_rule_satisfied,
        equivalence_certification_required=equivalence_certification_required,
        equivalence_certification_ready=equivalence_certification_ready,
        dependency_dag_acyclic=dependency_dag_acyclic,
        strategy_protocol_evidence_fields=strategy_protocol_evidence_fields(),
        missing_fields=tuple(missing_fields),
        violated_guarantees=tuple(violated_guarantees),
        guardrail_result=guardrail_result,
        explanation=explanation,
        remediation=remediation,
    )


def _dependency_signature(contract: StrategyContract) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        sorted((node.node_id, tuple(sorted(node.depends_on))) for node in contract.dependency_dag)
    )


def evaluate_strategy_contract_compatibility(
    previous: StrategyContract,
    current: StrategyContract,
) -> StrategyContractCompatibilityReport:
    if previous.contract_id != current.contract_id:
        return StrategyContractCompatibilityReport(
            contract_id=current.contract_id,
            previous_semantic_version=previous.signal_kernel.semantic_version,
            current_semantic_version=current.signal_kernel.semantic_version,
            status=StrategyContractStatus.INVALID.value,
            reason_code="STRATEGY_CONTRACT_ID_MISMATCH",
            compatible=False,
            requires_recertification=False,
            changed_fields=("contract_id",),
            broken_guarantees=("interface.contract_identity",),
            explanation="Compatibility checks require the same stable contract identifier.",
            remediation="Compare versions of the same strategy contract.",
        )

    previous_semver = _parse_semver(previous.signal_kernel.semantic_version)
    current_semver = _parse_semver(current.signal_kernel.semantic_version)
    if previous_semver is None or current_semver is None:
        return StrategyContractCompatibilityReport(
            contract_id=current.contract_id,
            previous_semantic_version=previous.signal_kernel.semantic_version,
            current_semantic_version=current.signal_kernel.semantic_version,
            status=StrategyContractStatus.INVALID.value,
            reason_code="STRATEGY_CONTRACT_SEMVER_INVALID",
            compatible=False,
            requires_recertification=False,
            changed_fields=("signal_kernel.semantic_version",),
            broken_guarantees=("semantic.semantic_version",),
            explanation="Semantic versions must use MAJOR.MINOR.PATCH format.",
            remediation="Publish valid semantic versions before running compatibility checks.",
        )

    changed_fields: list[str] = []
    broken_guarantees: list[str] = []

    if previous.parameter_schema_id != current.parameter_schema_id:
        changed_fields.append("parameter_schema_id")
        broken_guarantees.append("interface.parameter_schema")
    if set(previous.required_inputs) - set(current.required_inputs):
        changed_fields.append("required_inputs")
        broken_guarantees.append("interface.required_inputs")
    if previous.decision_cadence != current.decision_cadence:
        changed_fields.append("decision_cadence")
        broken_guarantees.append("semantic.decision_cadence")
    if previous.warmup != current.warmup:
        changed_fields.append("warmup")
        broken_guarantees.append("semantic.warmup")
    if set(previous.risk_control_hooks) - set(current.risk_control_hooks):
        changed_fields.append("risk_control_hooks")
        broken_guarantees.append("interface.risk_control_hooks")
    if (
        previous.order_intent_schema.schema_id != current.order_intent_schema.schema_id
        or set(previous.order_intent_schema.required_fields)
        - set(current.order_intent_schema.required_fields)
    ):
        changed_fields.append("order_intent_schema")
        broken_guarantees.append("interface.order_intent_schema")
    if _dependency_signature(previous) != _dependency_signature(current):
        changed_fields.append("dependency_dag")
        broken_guarantees.append("interface.dependency_dag")
    if previous.signal_kernel.kernel_abi_version != current.signal_kernel.kernel_abi_version:
        changed_fields.append("kernel_abi_version")
        broken_guarantees.append("kernel.kernel_abi_version")
    if (
        previous.signal_kernel.state_serialization_version
        != current.signal_kernel.state_serialization_version
    ):
        changed_fields.append("state_serialization_version")
        broken_guarantees.append("state.state_serialization_version")
    if previous.signal_kernel.signal_kernel_digest != current.signal_kernel.signal_kernel_digest:
        changed_fields.append("signal_kernel_digest")

    requires_recertification = any(
        field_name
        in {"signal_kernel_digest", "kernel_abi_version", "state_serialization_version"}
        for field_name in changed_fields
    )

    if current_semver <= previous_semver:
        status = StrategyContractStatus.INVALID.value
        reason_code = "STRATEGY_CONTRACT_SEMVER_REGRESSION"
        compatible = False
        explanation = (
            "Current semantic version does not advance beyond the previous version, so the "
            "compatibility decision is ambiguous."
        )
        remediation = "Increment the semantic version before publishing the updated contract."
    elif broken_guarantees:
        compatible = False
        if current_semver[0] <= previous_semver[0]:
            status = StrategyContractStatus.VIOLATION.value
            reason_code = "STRATEGY_CONTRACT_SEMVER_VIOLATION"
            explanation = (
                "Breaking contract changes were introduced without a major semantic-version bump. "
                f"Broken guarantees: {broken_guarantees}."
            )
            remediation = (
                "Bump the major semantic version or restore backward-compatible interface and "
                "state guarantees."
            )
        else:
            status = StrategyContractStatus.INCOMPATIBLE.value
            reason_code = "STRATEGY_CONTRACT_BREAKING_CHANGE"
            explanation = (
                "Breaking strategy-contract changes were introduced intentionally and require "
                f"downstream recertification. Broken guarantees: {broken_guarantees}."
            )
            remediation = (
                "Re-run equivalence, replay, and downstream compatibility certification before "
                "the new contract is admitted."
            )
    else:
        compatible = True
        status = StrategyContractStatus.PASS.value
        reason_code = "STRATEGY_CONTRACT_COMPATIBLE"
        explanation = (
            "Contract changes preserve interface, state, and semantic guarantees. Only "
            "non-breaking or recertification-scoped changes were detected."
        )
        remediation = "No remediation required."

    return StrategyContractCompatibilityReport(
        contract_id=current.contract_id,
        previous_semantic_version=previous.signal_kernel.semantic_version,
        current_semantic_version=current.signal_kernel.semantic_version,
        status=status,
        reason_code=reason_code,
        compatible=compatible,
        requires_recertification=requires_recertification,
        changed_fields=tuple(changed_fields),
        broken_guarantees=tuple(broken_guarantees),
        explanation=explanation,
        remediation=remediation,
    )


def validate_strategy_contract_catalog() -> list[str]:
    errors: list[str] = []
    if len(REQUIRED_ORDER_INTENT_FIELDS) != len(set(REQUIRED_ORDER_INTENT_FIELDS)):
        errors.append("required order-intent fields must be unique")
    if MIN_EQUIVALENCE_PROPERTY_CASES < 1:
        errors.append("minimum equivalence property cases must be positive")
    if not strategy_protocol_evidence_fields():
        errors.append("strategy protocol evidence fields must not be empty")
    return errors


VALIDATION_ERRORS = validate_strategy_contract_catalog()
