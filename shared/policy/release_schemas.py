"""Canonical release schema contracts for historical, analytic, and data-profile artifacts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp


SUPPORTED_RELEASE_SCHEMA_VERSION = 1


def _require_schema_version(value: object, *, release_kind: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{release_kind}: schema_version must be an integer")
    return value


def _normalize_observation_cutoff(value: str) -> str:
    try:
        normalized = canonicalize_persisted_timestamp(
            datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "dataset_release: observation_cutoff_utc must be timezone-aware and UTC-normalizable"
        ) from exc
    return normalized.isoformat()


@unique
class ReleaseStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"
    INCOMPATIBLE = "incompatible"


@unique
class ReleaseLifecycleState(str, Enum):
    DRAFT = "draft"
    CERTIFIED = "certified"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ReleaseDefinition:
    release_kind: str
    plan_section: str
    description: str
    required_fields: tuple[str, ...]


@dataclass(frozen=True)
class DatasetRelease:
    release_id: str
    raw_input_hashes: tuple[str, ...]
    reference_version_hashes: tuple[str, ...]
    observation_cutoff_utc: str
    validation_rules_version: str
    catalog_version: str
    protocol_versions: dict[str, str]
    vendor_revision_watermark: str
    correction_horizon: str
    certification_report_hash: str
    policy_bundle_hash: str
    lifecycle_state: ReleaseLifecycleState
    schema_version: int = SUPPORTED_RELEASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_cutoff_utc",
            _normalize_observation_cutoff(self.observation_cutoff_utc),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(
                self.schema_version,
                release_kind=self.release_kind,
            ),
        )

    @property
    def release_kind(self) -> str:
        return "dataset_release"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["release_kind"] = self.release_kind
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DatasetRelease":
        return cls(
            release_id=payload["release_id"],
            raw_input_hashes=tuple(payload["raw_input_hashes"]),
            reference_version_hashes=tuple(payload["reference_version_hashes"]),
            observation_cutoff_utc=payload["observation_cutoff_utc"],
            validation_rules_version=payload["validation_rules_version"],
            catalog_version=payload["catalog_version"],
            protocol_versions=dict(payload["protocol_versions"]),
            vendor_revision_watermark=payload["vendor_revision_watermark"],
            correction_horizon=payload["correction_horizon"],
            certification_report_hash=payload["certification_report_hash"],
            policy_bundle_hash=payload["policy_bundle_hash"],
            lifecycle_state=ReleaseLifecycleState(payload["lifecycle_state"]),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                release_kind="dataset_release",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DatasetRelease":
        return cls.from_dict(_decode_release_json(payload, "dataset_release"))


@dataclass(frozen=True)
class AnalyticRelease:
    release_id: str
    dataset_release_id: str
    feature_version: str
    analytic_series_version: str
    feature_block_manifests: tuple[str, ...]
    feature_availability_contracts: tuple[str, ...]
    slice_manifests: tuple[str, ...]
    artifact_root_hash: str
    lifecycle_state: ReleaseLifecycleState
    schema_version: int = SUPPORTED_RELEASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(
                self.schema_version,
                release_kind=self.release_kind,
            ),
        )

    @property
    def release_kind(self) -> str:
        return "analytic_release"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["release_kind"] = self.release_kind
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnalyticRelease":
        return cls(
            release_id=payload["release_id"],
            dataset_release_id=payload["dataset_release_id"],
            feature_version=payload["feature_version"],
            analytic_series_version=payload["analytic_series_version"],
            feature_block_manifests=tuple(payload["feature_block_manifests"]),
            feature_availability_contracts=tuple(payload["feature_availability_contracts"]),
            slice_manifests=tuple(payload.get("slice_manifests", ())),
            artifact_root_hash=payload["artifact_root_hash"],
            lifecycle_state=ReleaseLifecycleState(payload["lifecycle_state"]),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                release_kind="analytic_release",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AnalyticRelease":
        return cls.from_dict(_decode_release_json(payload, "analytic_release"))


@dataclass(frozen=True)
class DataProfileRelease:
    release_id: str
    source_feeds: tuple[str, ...]
    venue_dataset_ids: tuple[str, ...]
    schema_selection_rules: tuple[str, ...]
    timestamp_precedence_rule: str
    bar_construction_rules: tuple[str, ...]
    session_anchor_rule: str
    trade_quote_precedence_rule: str
    zero_volume_bar_policy: str
    late_print_policy: str
    correction_policy: str
    gap_policy: str
    forward_fill_policy: str
    symbology_mapping_rules: tuple[str, ...]
    live_historical_parity_expectations: tuple[str, ...]
    lifecycle_state: ReleaseLifecycleState
    schema_version: int = SUPPORTED_RELEASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(
                self.schema_version,
                release_kind=self.release_kind,
            ),
        )

    @property
    def release_kind(self) -> str:
        return "data_profile_release"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["release_kind"] = self.release_kind
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataProfileRelease":
        return cls(
            release_id=payload["release_id"],
            source_feeds=tuple(payload["source_feeds"]),
            venue_dataset_ids=tuple(payload["venue_dataset_ids"]),
            schema_selection_rules=tuple(payload["schema_selection_rules"]),
            timestamp_precedence_rule=payload["timestamp_precedence_rule"],
            bar_construction_rules=tuple(payload["bar_construction_rules"]),
            session_anchor_rule=payload["session_anchor_rule"],
            trade_quote_precedence_rule=payload["trade_quote_precedence_rule"],
            zero_volume_bar_policy=payload["zero_volume_bar_policy"],
            late_print_policy=payload["late_print_policy"],
            correction_policy=payload["correction_policy"],
            gap_policy=payload["gap_policy"],
            forward_fill_policy=payload["forward_fill_policy"],
            symbology_mapping_rules=tuple(payload["symbology_mapping_rules"]),
            live_historical_parity_expectations=tuple(payload["live_historical_parity_expectations"]),
            lifecycle_state=ReleaseLifecycleState(payload["lifecycle_state"]),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                release_kind="data_profile_release",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DataProfileRelease":
        return cls.from_dict(_decode_release_json(payload, "data_profile_release"))


@dataclass(frozen=True)
class ReleaseCompatibilityReport:
    release_kind: str
    release_id: str | None
    status: str
    reason_code: str
    compatible: bool
    expected_schema_version: int
    actual_schema_version: int | None
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class ReleasePublicationReport:
    case_id: str
    release_kind: str
    release_id: str | None
    status: str
    reason_code: str
    schema_version: int | None
    lifecycle_state: str | None
    missing_fields: tuple[str, ...]
    field_errors: dict[str, str]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class PromotableSurfaceBindingRequest:
    case_id: str
    surface_name: str
    requested_data_profile_release_id: str
    approved_data_profile_release_ids: tuple[str, ...]
    mutable_feed_semantics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromotableSurfaceBindingReport:
    case_id: str
    surface_name: str
    status: str
    reason_code: str
    requested_data_profile_release_id: str | None
    approved_data_profile_release_ids: tuple[str, ...]
    mutable_feed_semantics: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


RELEASE_SCHEMA_DEFINITIONS: tuple[ReleaseDefinition, ...] = (
    ReleaseDefinition(
        release_kind="dataset_release",
        plan_section="4.3",
        description="Certified point-in-time historical dataset release.",
        required_fields=(
            "release_id",
            "raw_input_hashes",
            "reference_version_hashes",
            "observation_cutoff_utc",
            "validation_rules_version",
            "catalog_version",
            "protocol_versions",
            "vendor_revision_watermark",
            "correction_horizon",
            "certification_report_hash",
            "policy_bundle_hash",
            "lifecycle_state",
        ),
    ),
    ReleaseDefinition(
        release_kind="analytic_release",
        plan_section="4.3",
        description="Derived analytic release tied to exactly one dataset release.",
        required_fields=(
            "release_id",
            "dataset_release_id",
            "feature_version",
            "analytic_series_version",
            "feature_block_manifests",
            "feature_availability_contracts",
            "artifact_root_hash",
            "lifecycle_state",
        ),
    ),
    ReleaseDefinition(
        release_kind="data_profile_release",
        plan_section="4.3",
        description="Immutable market-data interpretation contract for promotable work.",
        required_fields=(
            "release_id",
            "source_feeds",
            "venue_dataset_ids",
            "schema_selection_rules",
            "timestamp_precedence_rule",
            "bar_construction_rules",
            "session_anchor_rule",
            "trade_quote_precedence_rule",
            "zero_volume_bar_policy",
            "late_print_policy",
            "correction_policy",
            "gap_policy",
            "forward_fill_policy",
            "symbology_mapping_rules",
            "live_historical_parity_expectations",
            "lifecycle_state",
        ),
    ),
)


def release_definitions_by_kind() -> dict[str, ReleaseDefinition]:
    return {
        definition.release_kind: definition
        for definition in RELEASE_SCHEMA_DEFINITIONS
    }


def validate_release_schema_catalog() -> list[str]:
    errors: list[str] = []
    kinds = [definition.release_kind for definition in RELEASE_SCHEMA_DEFINITIONS]

    if len(kinds) != len(set(kinds)):
        errors.append("release schema kinds must be unique")

    for required_kind in ("dataset_release", "analytic_release", "data_profile_release"):
        if required_kind not in release_definitions_by_kind():
            errors.append(f"{required_kind} must be defined explicitly")

    return errors


def _decode_release_json(payload: str, release_kind: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{release_kind}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{release_kind}: payload must decode to a JSON object")
    return decoded


def _missing_required_fields(
    release_kind: str,
    payload: dict[str, Any],
) -> tuple[str, ...]:
    definition = release_definitions_by_kind()[release_kind]
    return tuple(
        field_name
        for field_name in definition.required_fields
        if not payload.get(field_name)
    )


def evaluate_release_compatibility(
    release_kind: str,
    payload: dict[str, Any],
) -> ReleaseCompatibilityReport:
    release_id = payload.get("release_id")
    actual_version = payload.get("schema_version")

    if release_kind not in release_definitions_by_kind():
        return ReleaseCompatibilityReport(
            release_kind=release_kind,
            release_id=release_id,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_SCHEMA_UNKNOWN_KIND",
            compatible=False,
            expected_schema_version=SUPPORTED_RELEASE_SCHEMA_VERSION,
            actual_schema_version=actual_version,
            explanation="The release kind is not part of the canonical schema catalog.",
            remediation="Publish only dataset_release, analytic_release, or data_profile_release objects.",
        )

    if not isinstance(actual_version, int):
        return ReleaseCompatibilityReport(
            release_kind=release_kind,
            release_id=release_id,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_SCHEMA_VERSION_MISSING",
            compatible=False,
            expected_schema_version=SUPPORTED_RELEASE_SCHEMA_VERSION,
            actual_schema_version=None,
            explanation="The release payload does not declare an integer schema version.",
            remediation="Stamp every release object with the canonical schema_version before publication.",
        )

    if actual_version != SUPPORTED_RELEASE_SCHEMA_VERSION:
        return ReleaseCompatibilityReport(
            release_kind=release_kind,
            release_id=release_id,
            status=ReleaseStatus.INCOMPATIBLE.value,
            reason_code="RELEASE_SCHEMA_VERSION_UNSUPPORTED",
            compatible=False,
            expected_schema_version=SUPPORTED_RELEASE_SCHEMA_VERSION,
            actual_schema_version=actual_version,
            explanation=(
                f"The payload uses schema_version {actual_version}, but the catalog currently "
                f"supports version {SUPPORTED_RELEASE_SCHEMA_VERSION}."
            ),
            remediation="Upgrade or downgrade the payload to the supported schema version before publication.",
        )

    return ReleaseCompatibilityReport(
        release_kind=release_kind,
        release_id=release_id,
        status=ReleaseStatus.PASS.value,
        reason_code="RELEASE_SCHEMA_VERSION_SUPPORTED",
        compatible=True,
        expected_schema_version=SUPPORTED_RELEASE_SCHEMA_VERSION,
        actual_schema_version=actual_version,
        explanation="The release payload uses the supported canonical schema version.",
        remediation="No remediation required.",
    )


def _validate_dataset_release_fields(payload: dict[str, Any]) -> dict[str, str]:
    field_errors: dict[str, str] = {}

    try:
        canonicalize_persisted_timestamp(
            datetime.datetime.fromisoformat(payload["observation_cutoff_utc"])
        )
    except (KeyError, TypeError, ValueError):
        field_errors["observation_cutoff_utc"] = (
            "observation_cutoff_utc must be a timezone-aware UTC-normalizable timestamp"
        )

    protocol_versions = payload.get("protocol_versions")
    if not isinstance(protocol_versions, dict) or not protocol_versions:
        field_errors["protocol_versions"] = (
            "protocol_versions must map protocol domains to immutable version identifiers"
        )

    return field_errors


def _validate_analytic_release_fields(payload: dict[str, Any]) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    if not payload.get("feature_block_manifests"):
        field_errors["feature_block_manifests"] = (
            "analytic_release requires at least one feature block manifest"
        )
    if not payload.get("feature_availability_contracts"):
        field_errors["feature_availability_contracts"] = (
            "analytic_release requires at least one feature availability contract"
        )
    return field_errors


def _validate_data_profile_release_fields(payload: dict[str, Any]) -> dict[str, str]:
    field_errors: dict[str, str] = {}

    if not payload.get("source_feeds"):
        field_errors["source_feeds"] = "data_profile_release must name at least one source feed"
    if not payload.get("venue_dataset_ids"):
        field_errors["venue_dataset_ids"] = (
            "data_profile_release must identify at least one source venue or dataset"
        )
    if not payload.get("live_historical_parity_expectations"):
        field_errors["live_historical_parity_expectations"] = (
            "data_profile_release must spell out live versus historical parity expectations"
        )

    return field_errors


def _build_publication_report(
    case_id: str,
    release_kind: str,
    payload: dict[str, Any],
    field_errors: dict[str, str],
) -> ReleasePublicationReport:
    compatibility = evaluate_release_compatibility(release_kind, payload)
    if not compatibility.compatible:
        return ReleasePublicationReport(
            case_id=case_id,
            release_kind=release_kind,
            release_id=payload.get("release_id"),
            status=compatibility.status,
            reason_code=compatibility.reason_code,
            schema_version=compatibility.actual_schema_version,
            lifecycle_state=payload.get("lifecycle_state"),
            missing_fields=(),
            field_errors={},
            explanation=compatibility.explanation,
            remediation=compatibility.remediation,
        )

    missing_fields = _missing_required_fields(release_kind, payload)
    if missing_fields:
        return ReleasePublicationReport(
            case_id=case_id,
            release_kind=release_kind,
            release_id=payload.get("release_id"),
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_SCHEMA_MISSING_REQUIRED_FIELDS",
            schema_version=payload.get("schema_version"),
            lifecycle_state=payload.get("lifecycle_state"),
            missing_fields=missing_fields,
            field_errors={},
            explanation=(
                "The release payload is missing one or more required fields: "
                f"{missing_fields}."
            ),
            remediation="Populate every required field before publishing the release object.",
        )

    if field_errors:
        return ReleasePublicationReport(
            case_id=case_id,
            release_kind=release_kind,
            release_id=payload.get("release_id"),
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_SCHEMA_FIELD_VALIDATION_FAILED",
            schema_version=payload.get("schema_version"),
            lifecycle_state=payload.get("lifecycle_state"),
            missing_fields=(),
            field_errors=field_errors,
            explanation="The release payload failed field-level validation checks.",
            remediation="Correct the reported field errors before publishing the release object.",
        )

    return ReleasePublicationReport(
        case_id=case_id,
        release_kind=release_kind,
        release_id=payload.get("release_id"),
        status=ReleaseStatus.PASS.value,
        reason_code="RELEASE_SCHEMA_PUBLISHABLE",
        schema_version=payload.get("schema_version"),
        lifecycle_state=payload.get("lifecycle_state"),
        missing_fields=(),
        field_errors={},
        explanation=(
            "The release payload is structurally complete, compatible with the canonical schema, "
            "and publishable with machine-readable diagnostics."
        ),
        remediation="No remediation required.",
    )


def validate_dataset_release(
    case_id: str,
    release: DatasetRelease,
) -> ReleasePublicationReport:
    payload = release.to_dict()
    return _build_publication_report(
        case_id=case_id,
        release_kind=release.release_kind,
        payload=payload,
        field_errors=_validate_dataset_release_fields(payload),
    )


def validate_analytic_release(
    case_id: str,
    release: AnalyticRelease,
) -> ReleasePublicationReport:
    payload = release.to_dict()
    return _build_publication_report(
        case_id=case_id,
        release_kind=release.release_kind,
        payload=payload,
        field_errors=_validate_analytic_release_fields(payload),
    )


def validate_data_profile_release(
    case_id: str,
    release: DataProfileRelease,
) -> ReleasePublicationReport:
    payload = release.to_dict()
    return _build_publication_report(
        case_id=case_id,
        release_kind=release.release_kind,
        payload=payload,
        field_errors=_validate_data_profile_release_fields(payload),
    )


def validate_promotable_surface_binding(
    request: PromotableSurfaceBindingRequest,
) -> PromotableSurfaceBindingReport:
    if not request.requested_data_profile_release_id:
        return PromotableSurfaceBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name,
            status=ReleaseStatus.INVALID.value,
            reason_code="DATA_PROFILE_RELEASE_BINDING_MISSING",
            requested_data_profile_release_id=None,
            approved_data_profile_release_ids=request.approved_data_profile_release_ids,
            mutable_feed_semantics=request.mutable_feed_semantics,
            explanation="The promotable surface does not name a data_profile_release.",
            remediation="Bind exactly one approved data_profile_release before promotion or activation.",
        )

    if request.mutable_feed_semantics:
        return PromotableSurfaceBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name,
            status=ReleaseStatus.VIOLATION.value,
            reason_code="DATA_PROFILE_RELEASE_MUTABLE_FEED_SEMANTICS",
            requested_data_profile_release_id=request.requested_data_profile_release_id,
            approved_data_profile_release_ids=request.approved_data_profile_release_ids,
            mutable_feed_semantics=request.mutable_feed_semantics,
            explanation=(
                "The promotable surface still depends on mutable feed semantics instead of a "
                f"single approved data_profile_release: {request.mutable_feed_semantics}."
            ),
            remediation="Remove mutable feed semantics and bind exactly one approved data_profile_release.",
        )

    if request.requested_data_profile_release_id not in request.approved_data_profile_release_ids:
        return PromotableSurfaceBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name,
            status=ReleaseStatus.VIOLATION.value,
            reason_code="DATA_PROFILE_RELEASE_NOT_APPROVED",
            requested_data_profile_release_id=request.requested_data_profile_release_id,
            approved_data_profile_release_ids=request.approved_data_profile_release_ids,
            mutable_feed_semantics=request.mutable_feed_semantics,
            explanation=(
                "The promotable surface references a data_profile_release that is not approved "
                "for use on this path."
            ),
            remediation="Bind one approved data_profile_release and reject unapproved feed semantics.",
        )

    return PromotableSurfaceBindingReport(
        case_id=request.case_id,
        surface_name=request.surface_name,
        status=ReleaseStatus.PASS.value,
        reason_code="DATA_PROFILE_RELEASE_BINDING_ALLOWED",
        requested_data_profile_release_id=request.requested_data_profile_release_id,
        approved_data_profile_release_ids=request.approved_data_profile_release_ids,
        mutable_feed_semantics=request.mutable_feed_semantics,
        explanation=(
            "The promotable surface binds exactly one approved data_profile_release and does not "
            "fall back to mutable feed semantics."
        ),
        remediation="No remediation required.",
    )


VALIDATION_ERRORS = validate_release_schema_catalog()
