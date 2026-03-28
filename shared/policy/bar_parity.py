"""Databento-to-IBKR bar-parity certification contracts."""

from __future__ import annotations

import datetime
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.artifact_classes import ArtifactClass, get_artifact_definition

SUPPORTED_BAR_PARITY_SCHEMA_VERSION = 1
PARITY_ARTIFACT_ID = "databento_ibkr_bar_parity_study"
PARITY_ARTIFACT = get_artifact_definition(PARITY_ARTIFACT_ID)
REQUIRED_PARITY_EXPECTATIONS = (
    "same_session_anchor_and_close_rule",
    "same_ohlcv_construction",
    "same_anchor_timing",
    "same_event_window_labeling",
    "same_bar_availability_timing",
)

VALIDATION_ERRORS: list[str] = []
if PARITY_ARTIFACT.artifact_class != ArtifactClass.FRESHNESS_BOUND:
    VALIDATION_ERRORS.append(
        f"{PARITY_ARTIFACT_ID}: expected freshness-bound artifact class, "
        f"found {PARITY_ARTIFACT.artifact_class.value}"
    )
if set(PARITY_ARTIFACT.used_by) != {"promotion", "readiness"}:
    VALIDATION_ERRORS.append(
        f"{PARITY_ARTIFACT_ID}: expected promotion/readiness usage, "
        f"found {PARITY_ARTIFACT.used_by}"
    )


def _parse_utc(timestamp: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp string")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp string") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_schema_version(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label}: schema_version must be an integer")
    return value


def _require_status(value: object, *, field_name: str) -> str:
    if isinstance(value, BarParityStatus):
        return value.value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a valid bar parity status")
    try:
        return BarParityStatus(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid bar parity status") from exc


@unique
class BarParityStatus(str, Enum):
    PASS = "pass"
    INVALID = "invalid"
    VIOLATION = "violation"
    STALE = "stale"


@unique
class BarParityDimensionID(str, Enum):
    SESSION_BOUNDARIES = "BP01"
    OHLCV_CONSTRUCTION = "BP02"
    ANCHOR_TIMING = "BP03"
    EVENT_WINDOW_LABELING = "BP04"
    BAR_AVAILABILITY_TIMING = "BP05"


@dataclass(frozen=True)
class BarParityDimensionResult:
    dimension_id: str
    dimension_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    research_value: dict[str, Any]
    live_value: dict[str, Any]
    tolerance: dict[str, Any]
    research_artifact_reference: str
    live_artifact_reference: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BarParityDimensionResult":
        return cls(
            dimension_id=str(payload["dimension_id"]),
            dimension_name=str(payload["dimension_name"]),
            passed=_require_bool(payload["passed"], field_name="passed"),
            reason_code=str(payload["reason_code"]),
            diagnostic=str(payload["diagnostic"]),
            research_value=dict(payload["research_value"]),
            live_value=dict(payload["live_value"]),
            tolerance=dict(payload["tolerance"]),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BarParityDimensionResult":
        return cls.from_dict(_decode_json_object(payload, label="bar_parity_dimension"))


@dataclass(frozen=True)
class BarParityCertificationRequest:
    case_id: str
    data_profile_release_id: str
    approved_bar_construction_semantics_id: str
    research_feed: str
    live_feed: str
    certified_at_utc: str
    freshness_expires_at_utc: str
    evaluation_time_utc: str
    parity_expectations: tuple[str, ...]
    mismatch_histogram_artifact_ids: tuple[str, ...]
    sampled_drilldown_artifact_ids: tuple[str, ...]
    dimensions: tuple[BarParityDimensionResult, ...]
    schema_version: int = SUPPORTED_BAR_PARITY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["dimensions"] = [dimension.to_dict() for dimension in self.dimensions]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BarParityCertificationRequest":
        return cls(
            case_id=str(payload["case_id"]),
            data_profile_release_id=str(payload["data_profile_release_id"]),
            approved_bar_construction_semantics_id=str(
                payload["approved_bar_construction_semantics_id"]
            ),
            research_feed=str(payload["research_feed"]),
            live_feed=str(payload["live_feed"]),
            certified_at_utc=_normalize_utc_timestamp(
                payload["certified_at_utc"],
                field_name="certified_at_utc",
            ),
            freshness_expires_at_utc=_normalize_utc_timestamp(
                payload["freshness_expires_at_utc"],
                field_name="freshness_expires_at_utc",
            ),
            evaluation_time_utc=_normalize_utc_timestamp(
                payload["evaluation_time_utc"],
                field_name="evaluation_time_utc",
            ),
            parity_expectations=tuple(str(item) for item in payload["parity_expectations"]),
            mismatch_histogram_artifact_ids=tuple(
                str(item) for item in payload["mismatch_histogram_artifact_ids"]
            ),
            sampled_drilldown_artifact_ids=tuple(
                str(item) for item in payload["sampled_drilldown_artifact_ids"]
            ),
            dimensions=tuple(
                BarParityDimensionResult.from_dict(dimension_payload)
                for dimension_payload in payload["dimensions"]
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                label="bar_parity_request",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BarParityCertificationRequest":
        return cls.from_dict(_decode_json_object(payload, label="bar_parity_request"))


@dataclass(frozen=True)
class BarParityCertificationReport:
    case_id: str
    data_profile_release_id: str | None
    status: str
    reason_code: str
    artifact_id: str
    freshness_valid: bool
    parity_passed: bool
    drifted_dimensions: tuple[str, ...]
    mismatch_histogram_artifact_ids: tuple[str, ...]
    sampled_drilldown_artifact_ids: tuple[str, ...]
    compared_dimensions: list[dict[str, Any]]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BarParityCertificationReport":
        return cls(
            case_id=str(payload["case_id"]),
            data_profile_release_id=payload.get("data_profile_release_id"),
            status=_require_status(payload["status"], field_name="status"),
            reason_code=str(payload["reason_code"]),
            artifact_id=str(payload["artifact_id"]),
            freshness_valid=_require_bool(
                payload["freshness_valid"],
                field_name="freshness_valid",
            ),
            parity_passed=_require_bool(
                payload["parity_passed"],
                field_name="parity_passed",
            ),
            drifted_dimensions=tuple(str(item) for item in payload["drifted_dimensions"]),
            mismatch_histogram_artifact_ids=tuple(
                str(item) for item in payload["mismatch_histogram_artifact_ids"]
            ),
            sampled_drilldown_artifact_ids=tuple(
                str(item) for item in payload["sampled_drilldown_artifact_ids"]
            ),
            compared_dimensions=[
                dict(item) for item in payload.get("compared_dimensions", [])
            ],
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BarParityCertificationReport":
        return cls.from_dict(_decode_json_object(payload, label="bar_parity_report"))


def _dimension_result(
    *,
    dimension_id: BarParityDimensionID,
    dimension_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    research_value: dict[str, Any],
    live_value: dict[str, Any],
    tolerance: dict[str, Any],
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    return BarParityDimensionResult(
        dimension_id=dimension_id.value,
        dimension_name=dimension_name,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        research_value=research_value,
        live_value=live_value,
        tolerance=tolerance,
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def check_session_boundaries(
    *,
    boundary_alignment_ratio: float,
    min_boundary_alignment_ratio: float,
    boundary_mismatch_count: int,
    max_boundary_mismatch_count: int,
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    passed = (
        boundary_alignment_ratio >= min_boundary_alignment_ratio
        and boundary_mismatch_count <= max_boundary_mismatch_count
    )
    failing = [
        key
        for key, ok in {
            "boundary_alignment_ratio": boundary_alignment_ratio >= min_boundary_alignment_ratio,
            "boundary_mismatch_count": boundary_mismatch_count <= max_boundary_mismatch_count,
        }.items()
        if not ok
    ]
    return _dimension_result(
        dimension_id=BarParityDimensionID.SESSION_BOUNDARIES,
        dimension_name="session_boundaries",
        passed=passed,
        reason_code="BAR_PARITY_BP01_SESSION_BOUNDARIES",
        diagnostic=(
            "Session boundaries match between Databento research bars and IBKR live bars"
            if passed
            else f"Session-boundary parity drifted: {failing}"
        ),
        research_value={
            "boundary_alignment_ratio": boundary_alignment_ratio,
            "boundary_mismatch_count": boundary_mismatch_count,
        },
        live_value={
            "boundary_alignment_ratio": boundary_alignment_ratio,
            "boundary_mismatch_count": boundary_mismatch_count,
        },
        tolerance={
            "min_boundary_alignment_ratio": min_boundary_alignment_ratio,
            "max_boundary_mismatch_count": max_boundary_mismatch_count,
        },
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def check_ohlcv_construction(
    *,
    ohlc_diff_ticks: int,
    max_allowed_ohlc_diff_ticks: int,
    volume_diff_ratio: float,
    max_allowed_volume_diff_ratio: float,
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    passed = (
        ohlc_diff_ticks <= max_allowed_ohlc_diff_ticks
        and volume_diff_ratio <= max_allowed_volume_diff_ratio
    )
    failing = [
        key
        for key, ok in {
            "ohlc_diff_ticks": ohlc_diff_ticks <= max_allowed_ohlc_diff_ticks,
            "volume_diff_ratio": volume_diff_ratio <= max_allowed_volume_diff_ratio,
        }.items()
        if not ok
    ]
    return _dimension_result(
        dimension_id=BarParityDimensionID.OHLCV_CONSTRUCTION,
        dimension_name="ohlcv_construction",
        passed=passed,
        reason_code="BAR_PARITY_BP02_OHLCV_CONSTRUCTION",
        diagnostic=(
            "OHLCV construction matches within approved parity tolerances"
            if passed
            else f"OHLCV parity drifted: {failing}"
        ),
        research_value={
            "ohlc_diff_ticks": ohlc_diff_ticks,
            "volume_diff_ratio": volume_diff_ratio,
        },
        live_value={
            "ohlc_diff_ticks": ohlc_diff_ticks,
            "volume_diff_ratio": volume_diff_ratio,
        },
        tolerance={
            "max_allowed_ohlc_diff_ticks": max_allowed_ohlc_diff_ticks,
            "max_allowed_volume_diff_ratio": max_allowed_volume_diff_ratio,
        },
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def check_anchor_timing(
    *,
    max_anchor_drift_seconds: float,
    max_allowed_anchor_drift_seconds: float,
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    passed = max_anchor_drift_seconds <= max_allowed_anchor_drift_seconds
    return _dimension_result(
        dimension_id=BarParityDimensionID.ANCHOR_TIMING,
        dimension_name="anchor_timing",
        passed=passed,
        reason_code="BAR_PARITY_BP03_ANCHOR_TIMING",
        diagnostic=(
            "Anchor timing matches within approved tolerance"
            if passed
            else (
                "Anchor timing drift exceeded tolerance: "
                f"{max_anchor_drift_seconds} > {max_allowed_anchor_drift_seconds}"
            )
        ),
        research_value={"max_anchor_drift_seconds": max_anchor_drift_seconds},
        live_value={"max_anchor_drift_seconds": max_anchor_drift_seconds},
        tolerance={"max_allowed_anchor_drift_seconds": max_allowed_anchor_drift_seconds},
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def check_event_window_labeling(
    *,
    mislabeled_window_count: int,
    max_allowed_mislabeled_window_count: int,
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    passed = mislabeled_window_count <= max_allowed_mislabeled_window_count
    return _dimension_result(
        dimension_id=BarParityDimensionID.EVENT_WINDOW_LABELING,
        dimension_name="event_window_labeling",
        passed=passed,
        reason_code="BAR_PARITY_BP04_EVENT_WINDOW_LABELING",
        diagnostic=(
            "Event-window labeling matches between research and IBKR bars"
            if passed
            else (
                "Event-window labeling drift exceeded tolerance: "
                f"{mislabeled_window_count} > {max_allowed_mislabeled_window_count}"
            )
        ),
        research_value={"mislabeled_window_count": mislabeled_window_count},
        live_value={"mislabeled_window_count": mislabeled_window_count},
        tolerance={
            "max_allowed_mislabeled_window_count": max_allowed_mislabeled_window_count,
        },
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def check_bar_availability_timing(
    *,
    max_availability_lag_seconds: float,
    max_allowed_availability_lag_seconds: float,
    research_artifact_reference: str,
    live_artifact_reference: str,
) -> BarParityDimensionResult:
    passed = max_availability_lag_seconds <= max_allowed_availability_lag_seconds
    return _dimension_result(
        dimension_id=BarParityDimensionID.BAR_AVAILABILITY_TIMING,
        dimension_name="bar_availability_timing",
        passed=passed,
        reason_code="BAR_PARITY_BP05_AVAILABILITY_TIMING",
        diagnostic=(
            "Bar-availability timing matches within approved tolerance"
            if passed
            else (
                "Bar-availability timing drift exceeded tolerance: "
                f"{max_availability_lag_seconds} > {max_allowed_availability_lag_seconds}"
            )
        ),
        research_value={"max_availability_lag_seconds": max_availability_lag_seconds},
        live_value={"max_availability_lag_seconds": max_availability_lag_seconds},
        tolerance={
            "max_allowed_availability_lag_seconds": max_allowed_availability_lag_seconds,
        },
        research_artifact_reference=research_artifact_reference,
        live_artifact_reference=live_artifact_reference,
    )


def evaluate_databento_ibkr_bar_parity(
    request: BarParityCertificationRequest,
) -> BarParityCertificationReport:
    if request.schema_version != SUPPORTED_BAR_PARITY_SCHEMA_VERSION:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id or None,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_SCHEMA_VERSION_UNSUPPORTED",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation="The bar-parity request uses an unsupported schema version.",
            remediation="Regenerate the request with the current bar-parity schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "data_profile_release_id": request.data_profile_release_id,
            "approved_bar_construction_semantics_id": request.approved_bar_construction_semantics_id,
            "research_feed": request.research_feed,
            "live_feed": request.live_feed,
            "certified_at_utc": request.certified_at_utc,
            "freshness_expires_at_utc": request.freshness_expires_at_utc,
            "evaluation_time_utc": request.evaluation_time_utc,
        }.items()
        if not field_value
    )
    if missing_fields:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id or None,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_MISSING_REQUIRED_FIELDS",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=f"The bar-parity request is missing required fields: {missing_fields}.",
            remediation="Populate all required release, feed, and freshness fields.",
        )

    if request.research_feed != "Databento" or request.live_feed != "IBKR":
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_UNAPPROVED_FEEDS",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "The parity harness only certifies approved Databento research bars against "
                "approved IBKR live bars."
            ),
            remediation="Use Databento as the research feed and IBKR as the live feed.",
        )

    dimension_ids = tuple(dimension.dimension_id for dimension in request.dimensions)
    required_dimension_ids = {dimension.value for dimension in BarParityDimensionID}
    duplicate_dimension_ids = tuple(
        sorted(
            dimension_id
            for dimension_id, count in Counter(dimension_ids).items()
            if count > 1
        )
    )
    missing_dimension_ids = tuple(sorted(required_dimension_ids - set(dimension_ids)))
    unexpected_dimension_ids = tuple(sorted(set(dimension_ids) - required_dimension_ids))
    if (
        len(request.dimensions) != len(required_dimension_ids)
        or missing_dimension_ids
        or unexpected_dimension_ids
        or duplicate_dimension_ids
    ):
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_DIMENSIONS_INCOMPLETE",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "The parity harness must cover session boundaries, OHLCV construction, anchor "
                "timing, event-window labeling, and bar-availability timing. "
                f"Missing: {missing_dimension_ids}. "
                f"Unexpected: {unexpected_dimension_ids}. "
                f"Duplicates: {duplicate_dimension_ids}."
            ),
            remediation="Provide results for all five required parity dimensions.",
        )

    missing_expectations = tuple(
        expectation
        for expectation in REQUIRED_PARITY_EXPECTATIONS
        if expectation not in request.parity_expectations
    )
    if missing_expectations:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_EXPECTATIONS_INCOMPLETE",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "The bound data-profile release does not spell out all required parity "
                f"expectations: {missing_expectations}."
            ),
            remediation="Bind a data-profile release that enumerates all required parity semantics.",
        )

    if not request.mismatch_histogram_artifact_ids or not request.sampled_drilldown_artifact_ids:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.INVALID.value,
            reason_code="BAR_PARITY_ARTIFACTS_INCOMPLETE",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "Parity certification must retain mismatch histograms and sampled drill-down "
                "artifacts for review."
            ),
            remediation="Retain histogram and drill-down artifact references in the certification.",
        )

    freshness_valid = _parse_utc(request.evaluation_time_utc) <= _parse_utc(
        request.freshness_expires_at_utc
    )
    if not freshness_valid:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.STALE.value,
            reason_code="BAR_PARITY_CERTIFICATION_STALE",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=False,
            parity_passed=False,
            drifted_dimensions=(),
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "The Databento-to-IBKR bar-parity study has expired and is no longer admissible "
                "for promotion or readiness."
            ),
            remediation="Re-run parity certification against the current approved data profile.",
        )

    drifted_dimensions = tuple(
        dimension.dimension_name for dimension in request.dimensions if not dimension.passed
    )
    if drifted_dimensions:
        return BarParityCertificationReport(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            status=BarParityStatus.VIOLATION.value,
            reason_code="BAR_PARITY_DIMENSION_DRIFT",
            artifact_id=PARITY_ARTIFACT_ID,
            freshness_valid=True,
            parity_passed=False,
            drifted_dimensions=drifted_dimensions,
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
            explanation=(
                "Bar-parity certification found drift in the following semantic dimensions: "
                f"{drifted_dimensions}."
            ),
            remediation=(
                "Inspect the retained mismatch histograms and drill-down artifacts to reconcile "
                "the drift before paper, shadow-live, or live."
            ),
        )

    return BarParityCertificationReport(
        case_id=request.case_id,
        data_profile_release_id=request.data_profile_release_id,
        status=BarParityStatus.PASS.value,
        reason_code="BAR_PARITY_CERTIFIED",
        artifact_id=PARITY_ARTIFACT_ID,
        freshness_valid=True,
        parity_passed=True,
        drifted_dimensions=(),
        mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
        sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
        compared_dimensions=[dimension.to_dict() for dimension in request.dimensions],
        explanation=(
            "Databento research bars and IBKR live bars remain parity-certified across session "
            "boundaries, OHLCV construction, anchor timing, event-window labeling, and "
            "bar-availability timing."
        ),
        remediation="No remediation required.",
    )
