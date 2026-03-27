"""Registry and run contracts for deterministic domain verification suites."""

from __future__ import annotations

import copy
import datetime
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum, unique
from typing import Any

from shared.policy.verification_contract import (
    ArtifactRequirement,
    FixtureSource,
    GATE_DECISION_ARTIFACTS,
    GOLDEN_LOG_FIXTURES,
    TracePlane,
    validate_log_fixture,
)


SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION = 1
REQUIRED_DOMAIN_ARTIFACT_ROLES = (
    "fixture_manifest",
    "structured_log",
    "expected_vs_actual_diff",
)


@unique
class DomainContractSuiteStatus(str, Enum):
    PASS = "pass"  # nosec B105 - verification status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@dataclass(frozen=True)
class DomainContractSuiteSpec:
    suite_id: str
    title: str
    trace_plane: TracePlane
    related_beads: tuple[str, ...]
    covered_domains: tuple[str, ...]
    required_test_modules: tuple[str, ...]
    required_fixture_sources: tuple[FixtureSource, ...]
    required_artifact_roles: tuple[str, ...] = REQUIRED_DOMAIN_ARTIFACT_ROLES
    retained_artifacts: tuple[ArtifactRequirement, ...] = GATE_DECISION_ARTIFACTS + (
        ArtifactRequirement.FIXTURE_MANIFESTS,
        ArtifactRequirement.REPRODUCIBILITY_STAMPS,
    )
    schema_version: int = SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trace_plane"] = self.trace_plane.value
        payload["required_fixture_sources"] = tuple(
            source.value for source in self.required_fixture_sources
        )
        payload["retained_artifacts"] = tuple(
            requirement.value for requirement in self.retained_artifacts
        )
        return payload


@dataclass(frozen=True)
class DomainContractSuiteArtifact:
    artifact_id: str
    artifact_role: str
    relative_path: str
    sha256: str
    content_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DomainContractSuiteArtifact":
        return cls(
            artifact_id=str(payload["artifact_id"]),
            artifact_role=str(payload["artifact_role"]),
            relative_path=str(payload["relative_path"]),
            sha256=str(payload["sha256"]),
            content_type=str(payload["content_type"]),
        )


@dataclass(frozen=True)
class DomainContractSuiteRun:
    suite_id: str
    run_id: str
    correlation_id: str
    decision_trace_id: str
    fixture_case_id: str
    fixture_manifest_id: str
    fixture_sources: tuple[FixtureSource, ...]
    test_modules: tuple[str, ...]
    expected_vs_actual_diff_artifact_ids: tuple[str, ...]
    artifacts: tuple[DomainContractSuiteArtifact, ...]
    structured_log: dict[str, Any]
    schema_version: int = SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fixture_sources"] = tuple(source.value for source in self.fixture_sources)
        payload["artifacts"] = tuple(artifact.to_dict() for artifact in self.artifacts)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DomainContractSuiteRun":
        structured_log = payload.get("structured_log")
        if not isinstance(structured_log, Mapping):
            raise ValueError("domain_contract_suite_run: structured_log must be a mapping")
        return cls(
            suite_id=str(payload["suite_id"]),
            run_id=str(payload["run_id"]),
            correlation_id=str(payload["correlation_id"]),
            decision_trace_id=str(payload["decision_trace_id"]),
            fixture_case_id=str(payload["fixture_case_id"]),
            fixture_manifest_id=str(payload["fixture_manifest_id"]),
            fixture_sources=tuple(
                FixtureSource(str(item)) for item in payload["fixture_sources"]
            ),
            test_modules=tuple(str(item) for item in payload["test_modules"]),
            expected_vs_actual_diff_artifact_ids=tuple(
                str(item) for item in payload["expected_vs_actual_diff_artifact_ids"]
            ),
            artifacts=tuple(
                DomainContractSuiteArtifact.from_dict(item)
                for item in payload["artifacts"]
                if isinstance(item, Mapping)
            ),
            structured_log=_tupleize_json_collections(dict(structured_log)),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DomainContractSuiteRun":
        return cls.from_dict(_decode_json_object(payload, "domain_contract_suite_run"))


@dataclass(frozen=True)
class DomainContractSuiteReport:
    case_id: str
    suite_id: str | None
    run_id: str | None
    status: str
    reason_code: str
    missing_fields: tuple[str, ...]
    context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DomainContractSuiteReport":
        context = payload.get("context")
        if not isinstance(context, Mapping):
            raise ValueError("domain_contract_suite_report: context must be a mapping")
        return cls(
            case_id=str(payload["case_id"]),
            suite_id=str(payload["suite_id"]) if payload.get("suite_id") else None,
            run_id=str(payload["run_id"]) if payload.get("run_id") else None,
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            missing_fields=tuple(str(item) for item in payload.get("missing_fields", ())),
            context=_tupleize_json_collections(dict(context)),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload["timestamp"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DomainContractSuiteReport":
        return cls.from_dict(_decode_json_object(payload, "domain_contract_suite_report"))


DOMAIN_CONTRACT_SUITE_SPECS: tuple[DomainContractSuiteSpec, ...] = (
    DomainContractSuiteSpec(
        suite_id="release_schema_and_artifact_lifecycle",
        title="Release schemas and artifact lifecycle semantics",
        trace_plane=TracePlane.RELEASE,
        related_beads=("backtesting_engine-ltc.3.9",),
        covered_domains=("release_schemas", "artifact_classes"),
        required_test_modules=(
            "tests/test_release_schemas.py",
            "tests/test_artifact_classes.py",
        ),
        required_fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="execution_profile_contracts",
        title="Execution-profile release and resolved-context binding semantics",
        trace_plane=TracePlane.RELEASE,
        related_beads=("backtesting_engine-ltc.4.1",),
        covered_domains=("execution_profile_release", "resolved_context_binding"),
        required_test_modules=("tests/test_resolved_context.py",),
        required_fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="bar_parity_contracts",
        title="Parity-sensitive bar semantics and certification behavior",
        trace_plane=TracePlane.RELEASE,
        related_beads=("backtesting_engine-ltc.4.5",),
        covered_domains=("bar_parity", "parity_dimensions"),
        required_test_modules=("tests/test_bar_parity.py",),
        required_fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="strategy_contract_contracts",
        title="Strategy contract and canonical signal-kernel behavior",
        trace_plane=TracePlane.POLICY,
        related_beads=("backtesting_engine-ltc.5.1",),
        covered_domains=("strategy_contract", "canonical_signal_kernel"),
        required_test_modules=("tests/test_strategy_contract.py",),
        required_fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="policy_engine_decision_traces",
        title="Policy engine decision traces and waiver semantics",
        trace_plane=TracePlane.POLICY,
        related_beads=("backtesting_engine-ltc.8.1",),
        covered_domains=("policy_engine", "decision_traces"),
        required_test_modules=("tests/test_policy_engine.py",),
        required_fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="lifecycle_compatibility_contracts",
        title="Lifecycle-state and compatibility-domain contracts",
        trace_plane=TracePlane.POLICY,
        related_beads=("backtesting_engine-ltc.8.2",),
        covered_domains=("lifecycle_specs", "lifecycle_compatibility"),
        required_test_modules=(
            "tests/test_lifecycle_specs.py",
            "tests/test_lifecycle_compatibility.py",
        ),
        required_fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
    DomainContractSuiteSpec(
        suite_id="broker_semantics_contracts",
        title="Broker conformance, idempotency, and fixture replay semantics",
        trace_plane=TracePlane.RUNTIME,
        related_beads=("backtesting_engine-ltc.7.10",),
        covered_domains=(
            "broker_conformance",
            "order_intent_idempotency",
            "broker_session_fixture_replay",
        ),
        required_test_modules=("tests/test_broker_semantics.py",),
        required_fixture_sources=(
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
    ),
)


def domain_contract_suite_specs_by_id() -> dict[str, DomainContractSuiteSpec]:
    return {spec.suite_id: spec for spec in DOMAIN_CONTRACT_SUITE_SPECS}


def domain_contract_suite_ids() -> tuple[str, ...]:
    return tuple(spec.suite_id for spec in DOMAIN_CONTRACT_SUITE_SPECS)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha_label(label: str) -> str:
    return f"sha256:{label}"


def build_sample_domain_contract_suite_run(
    suite_id: str,
    *,
    run_id: str | None = None,
    fixture_case_id: str = "golden",
) -> DomainContractSuiteRun:
    spec = domain_contract_suite_specs_by_id()[suite_id]
    effective_run_id = run_id or f"{suite_id}_run_v1"
    correlation_id = f"corr_{suite_id}_001"
    decision_trace_id = f"decision_trace_{suite_id}_001"
    fixture_manifest_id = f"{suite_id}_fixture_manifest"
    diff_artifact_id = f"{suite_id}_expected_vs_actual_diff"

    structured_log = copy.deepcopy(GOLDEN_LOG_FIXTURES[spec.trace_plane])
    structured_log["event_id"] = f"{suite_id}_{fixture_case_id}_event"
    structured_log["correlation_id"] = correlation_id
    structured_log["decision_trace_id"] = decision_trace_id
    structured_log["artifact_manifest"]["manifest_id"] = fixture_manifest_id
    structured_log["artifact_manifest"]["generated_at_utc"] = "2026-03-27T06:00:00Z"
    structured_log["artifact_manifest"]["artifacts"] = (
        {
            "artifact_id": diff_artifact_id,
            "artifact_role": "expected_vs_actual_diff",
            "relative_path": (
                f"verification/domain_suites/{suite_id}/{fixture_case_id}/expected_vs_actual.json"
            ),
            "sha256": _sha_label(f"{suite_id}_expected_vs_actual"),
            "content_type": "application/json",
        },
    )

    artifacts = (
        DomainContractSuiteArtifact(
            artifact_id=fixture_manifest_id,
            artifact_role="fixture_manifest",
            relative_path=(
                f"verification/domain_suites/{suite_id}/{fixture_case_id}/fixture_manifest.json"
            ),
            sha256=_sha_label(f"{suite_id}_fixture_manifest"),
            content_type="application/json",
        ),
        DomainContractSuiteArtifact(
            artifact_id=f"{effective_run_id}_structured_log",
            artifact_role="structured_log",
            relative_path=(
                f"verification/domain_suites/{suite_id}/{fixture_case_id}/structured_log.json"
            ),
            sha256=_sha_label(f"{suite_id}_structured_log"),
            content_type="application/json",
        ),
        DomainContractSuiteArtifact(
            artifact_id=diff_artifact_id,
            artifact_role="expected_vs_actual_diff",
            relative_path=(
                f"verification/domain_suites/{suite_id}/{fixture_case_id}/expected_vs_actual.json"
            ),
            sha256=_sha_label(f"{suite_id}_expected_vs_actual"),
            content_type="application/json",
        ),
    )

    return DomainContractSuiteRun(
        suite_id=suite_id,
        run_id=effective_run_id,
        correlation_id=correlation_id,
        decision_trace_id=decision_trace_id,
        fixture_case_id=fixture_case_id,
        fixture_manifest_id=fixture_manifest_id,
        fixture_sources=spec.required_fixture_sources,
        test_modules=spec.required_test_modules,
        expected_vs_actual_diff_artifact_ids=(diff_artifact_id,),
        artifacts=artifacts,
        structured_log=structured_log,
    )


def _report(
    *,
    case_id: str,
    run: DomainContractSuiteRun,
    status: DomainContractSuiteStatus,
    reason_code: str,
    missing_fields: tuple[str, ...] = (),
    context: dict[str, Any] | None = None,
    explanation: str,
    remediation: str,
) -> DomainContractSuiteReport:
    return DomainContractSuiteReport(
        case_id=case_id,
        suite_id=run.suite_id or None,
        run_id=run.run_id or None,
        status=status.value,
        reason_code=reason_code,
        missing_fields=missing_fields,
        context=context or {},
        explanation=explanation,
        remediation=remediation,
        timestamp=_utcnow(),
    )


def evaluate_domain_contract_suite_run(
    case_id: str,
    run: DomainContractSuiteRun,
) -> DomainContractSuiteReport:
    missing_fields = tuple(
        field_name
        for field_name in (
            "suite_id",
            "run_id",
            "correlation_id",
            "decision_trace_id",
            "fixture_case_id",
            "fixture_manifest_id",
        )
        if not getattr(run, field_name, "").strip()
    )
    if missing_fields:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.INVALID,
            reason_code="DOMAIN_SUITE_FIELDS_MISSING",
            missing_fields=missing_fields,
            explanation="Domain suite runs must declare stable run, trace, and fixture identifiers.",
            remediation="Populate the missing fields before emitting a domain suite report.",
        )

    spec = domain_contract_suite_specs_by_id().get(run.suite_id)
    if spec is None:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.INVALID,
            reason_code="DOMAIN_SUITE_UNKNOWN",
            explanation="The requested domain suite is not registered in the suite catalog.",
            remediation="Use one of the registered domain suite identifiers.",
        )

    if run.schema_version != SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.INVALID,
            reason_code="DOMAIN_SUITE_SCHEMA_VERSION_UNSUPPORTED",
            context={"schema_version": run.schema_version},
            explanation="The domain suite run uses an unsupported schema version.",
            remediation=(
                f"Emit schema_version={SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION} "
                "for suite run payloads."
            ),
        )

    if run.structured_log.get("correlation_id") != run.correlation_id or run.structured_log.get(
        "decision_trace_id"
    ) != run.decision_trace_id:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.INVALID,
            reason_code="DOMAIN_SUITE_LOG_LINKAGE_MISMATCH",
            explanation="The structured log must carry the same correlation and decision-trace IDs as the suite run envelope.",
            remediation="Keep the run envelope IDs and structured-log IDs in sync.",
        )

    log_errors = validate_log_fixture(spec.trace_plane, run.structured_log)
    if log_errors:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.INVALID,
            reason_code="DOMAIN_SUITE_LOG_INVALID",
            context={"log_errors": tuple(log_errors)},
            explanation="The domain suite structured log failed the shared logging contract.",
            remediation="Repair the structured log envelope and required referenced IDs.",
        )

    missing_test_modules = tuple(
        module_name
        for module_name in spec.required_test_modules
        if module_name not in set(run.test_modules)
    )
    if missing_test_modules:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_TEST_MODULES_INCOMPLETE",
            context={"missing_test_modules": missing_test_modules},
            explanation="The suite run does not cover every required deterministic test module.",
            remediation="Run and retain every required unit or contract test module for the suite.",
        )

    missing_fixture_sources = tuple(
        source.value
        for source in spec.required_fixture_sources
        if source not in set(run.fixture_sources)
    )
    if missing_fixture_sources:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_FIXTURE_PROVENANCE_INCOMPLETE",
            context={"missing_fixture_sources": missing_fixture_sources},
            explanation="The suite run omits required fixture provenance classes.",
            remediation="Retain the missing fixture provenance and include it in the run envelope.",
        )

    artifact_roles = {artifact.artifact_role for artifact in run.artifacts}
    missing_artifact_roles = tuple(
        role for role in spec.required_artifact_roles if role not in artifact_roles
    )
    if missing_artifact_roles:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_ARTIFACT_ROLES_INCOMPLETE",
            context={"missing_artifact_roles": missing_artifact_roles},
            explanation="The suite run does not retain every required diagnostic artifact role.",
            remediation="Retain fixture manifests, structured logs, and expected-vs-actual diffs for the suite run.",
        )

    if not run.expected_vs_actual_diff_artifact_ids:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_EXPECTED_DIFFS_MISSING",
            explanation="Domain suite runs must preserve expected-vs-actual diff artifacts for reproducible failures.",
            remediation="Retain at least one expected-vs-actual diff artifact ID in the suite envelope.",
        )

    diff_artifact_ids = {
        artifact.artifact_id
        for artifact in run.artifacts
        if artifact.artifact_role == "expected_vs_actual_diff"
    }
    missing_diff_artifacts = tuple(
        artifact_id
        for artifact_id in run.expected_vs_actual_diff_artifact_ids
        if artifact_id not in diff_artifact_ids
    )
    if missing_diff_artifacts:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_EXPECTED_DIFF_ARTIFACTS_MISSING",
            context={"missing_diff_artifacts": missing_diff_artifacts},
            explanation="The suite envelope references expected-vs-actual diffs that are not retained as artifacts.",
            remediation="Retain artifacts for every referenced expected-vs-actual diff ID.",
        )

    fixture_manifest_ids = {
        artifact.artifact_id
        for artifact in run.artifacts
        if artifact.artifact_role == "fixture_manifest"
    }
    if run.fixture_manifest_id not in fixture_manifest_ids:
        return _report(
            case_id=case_id,
            run=run,
            status=DomainContractSuiteStatus.VIOLATION,
            reason_code="DOMAIN_SUITE_FIXTURE_MANIFEST_MISSING",
            context={"fixture_manifest_id": run.fixture_manifest_id},
            explanation="The suite run fixture manifest must be retained as an explicit artifact.",
            remediation="Retain the fixture manifest artifact and reference it from the run envelope.",
        )

    return _report(
        case_id=case_id,
        run=run,
        status=DomainContractSuiteStatus.PASS,
        reason_code="DOMAIN_SUITE_READY",
        context={
            "suite_title": spec.title,
            "trace_plane": spec.trace_plane.value,
            "covered_domains": spec.covered_domains,
            "fixture_sources": tuple(source.value for source in run.fixture_sources),
            "artifact_roles": tuple(sorted(artifact_roles)),
            "test_module_count": len(run.test_modules),
        },
        explanation="The suite run is deterministic, trace-linked, and retains the artifacts needed to diagnose domain-semantic failures quickly.",
        remediation="None. The suite run is ready to gate merges and releases.",
    )


def validate_domain_contract_suite_catalog() -> list[str]:
    errors: list[str] = []
    seen_suite_ids: set[str] = set()

    for spec in DOMAIN_CONTRACT_SUITE_SPECS:
        if spec.suite_id in seen_suite_ids:
            errors.append(f"duplicate domain suite id: {spec.suite_id}")
        seen_suite_ids.add(spec.suite_id)

        if not spec.related_beads:
            errors.append(f"{spec.suite_id}: related beads are required")
        if not spec.covered_domains:
            errors.append(f"{spec.suite_id}: covered domains are required")
        if not spec.required_test_modules:
            errors.append(f"{spec.suite_id}: required test modules are required")
        if not spec.required_fixture_sources:
            errors.append(f"{spec.suite_id}: required fixture sources are required")
        if spec.schema_version != SUPPORTED_DOMAIN_CONTRACT_SUITE_SCHEMA_VERSION:
            errors.append(f"{spec.suite_id}: schema_version must remain 1")

        missing_roles = set(REQUIRED_DOMAIN_ARTIFACT_ROLES).difference(spec.required_artifact_roles)
        if missing_roles:
            errors.append(
                f"{spec.suite_id}: required artifact roles missing {tuple(sorted(missing_roles))}"
            )

        if not set(GATE_DECISION_ARTIFACTS).issubset(spec.retained_artifacts):
            errors.append(f"{spec.suite_id}: retained artifacts must include gate decision artifacts")

    return errors


def _decode_json_object(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised via callers
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _tupleize_json_collections(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tupleize_json_collections(item) for item in value)
    if isinstance(value, dict):
        return {key: _tupleize_json_collections(item) for key, item in value.items()}
    return value


VALIDATION_ERRORS = validate_domain_contract_suite_catalog()
