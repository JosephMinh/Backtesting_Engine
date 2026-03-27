"""Operating-envelope profiles and session-conditioned risk envelopes."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.product_profiles import OperatingPosture


SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION = 1
REQUIRED_OPERATING_ENVELOPE_DIMENSIONS = (
    "spread_regime",
    "stale_quote_rate",
    "live_bar_parity_degradation",
    "realized_volatility_bucket",
    "session_or_event_class",
    "freshness_watermark_lag",
    "broker_round_trip_latency",
)
OPTIONAL_OPERATING_ENVELOPE_DIMENSIONS = ("signal_score_drift",)
REQUIRED_SESSION_CLASSES = (
    "overnight",
    "regular_comex",
    "maintenance_adjacent",
    "macro_event",
    "degraded_data",
)
OPERATING_ENVELOPE_ACTIONS = (
    "maintain",
    "size_reduction",
    "passive_entry_suppression",
    "no_new_overnight_carry",
    "lower_max_trades",
    "entry_suppression",
    "exit_only",
    "forced_flatten",
)
_STATUS_SEVERITY = {
    "green": 0,
    "yellow": 1,
    "red": 2,
    "invalid": 3,
}
_ACTION_SEVERITY = {
    "maintain": 0,
    "size_reduction": 1,
    "lower_max_trades": 1,
    "passive_entry_suppression": 2,
    "no_new_overnight_carry": 2,
    "entry_suppression": 3,
    "exit_only": 4,
    "forced_flatten": 5,
}
_ACTION_SIZE_MULTIPLIERS = {
    "maintain": 1.0,
    "size_reduction": 0.5,
    "passive_entry_suppression": 1.0,
    "no_new_overnight_carry": 1.0,
    "lower_max_trades": 1.0,
    "entry_suppression": 0.0,
    "exit_only": 0.0,
    "forced_flatten": 0.0,
}
_ACTION_MAX_TRADE_MULTIPLIERS = {
    "maintain": 1.0,
    "size_reduction": 1.0,
    "passive_entry_suppression": 1.0,
    "no_new_overnight_carry": 1.0,
    "lower_max_trades": 0.5,
    "entry_suppression": 0.0,
    "exit_only": 0.0,
    "forced_flatten": 0.0,
}


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _sorted_unique_actions(actions: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    ordered = sorted(set(actions), key=lambda item: (_ACTION_SEVERITY[item], item))
    return tuple(ordered)


@unique
class OperatingEnvelopeStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    INVALID = "invalid"


@unique
class EnvelopeValueKind(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


@unique
class OperatingEnvelopeAction(str, Enum):
    MAINTAIN = "maintain"
    SIZE_REDUCTION = "size_reduction"
    PASSIVE_ENTRY_SUPPRESSION = "passive_entry_suppression"
    NO_NEW_OVERNIGHT_CARRY = "no_new_overnight_carry"
    LOWER_MAX_TRADES = "lower_max_trades"
    ENTRY_SUPPRESSION = "entry_suppression"
    EXIT_ONLY = "exit_only"
    FORCED_FLATTEN = "forced_flatten"


@unique
class SessionClass(str, Enum):
    OVERNIGHT = "overnight"
    REGULAR_COMEX = "regular_comex"
    MAINTENANCE_ADJACENT = "maintenance_adjacent"
    MACRO_EVENT = "macro_event"
    DEGRADED_DATA = "degraded_data"


@unique
class EntryMode(str, Enum):
    NORMAL = "normal"
    PASSIVE_ONLY = "passive_only"
    NO_NEW_ENTRIES = "no_new_entries"
    EXIT_ONLY = "exit_only"
    FORCED_FLATTEN = "forced_flatten"


@dataclass(frozen=True)
class OperatingEnvelopeBand:
    band: str
    actions: tuple[str, ...]
    diagnostic: str
    remediation: str
    minimum_value: float | None = None
    maximum_value: float | None = None
    categorical_values: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatingEnvelopeBand":
        return cls(
            band=str(payload["band"]),
            actions=tuple(str(item) for item in payload.get("actions", ())),
            diagnostic=str(payload["diagnostic"]),
            remediation=str(payload["remediation"]),
            minimum_value=(
                float(payload["minimum_value"])
                if payload.get("minimum_value") is not None
                else None
            ),
            maximum_value=(
                float(payload["maximum_value"])
                if payload.get("maximum_value") is not None
                else None
            ),
            categorical_values=tuple(
                str(item) for item in payload.get("categorical_values", ())
            ),
        )


@dataclass(frozen=True)
class OperatingEnvelopeDimension:
    dimension_id: str
    title: str
    value_kind: str
    bands: tuple[OperatingEnvelopeBand, ...]
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bands"] = [band.to_dict() for band in self.bands]
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatingEnvelopeDimension":
        return cls(
            dimension_id=str(payload["dimension_id"]),
            title=str(payload["title"]),
            value_kind=str(payload["value_kind"]),
            bands=tuple(
                OperatingEnvelopeBand.from_dict(dict(item))
                for item in payload.get("bands", ())
            ),
            unit=str(payload["unit"]) if payload.get("unit") not in (None, "") else None,
        )


@dataclass(frozen=True)
class OperatingEnvelopeProfile:
    profile_id: str
    strategy_family_id: str
    product_profile_id: str
    account_profile_id: str
    execution_symbol: str
    default_operating_posture: str
    signal_score_drift_relevant: bool
    dimensions: tuple[OperatingEnvelopeDimension, ...]
    schema_version: int = SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["dimensions"] = [dimension.to_dict() for dimension in self.dimensions]
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatingEnvelopeProfile":
        return cls(
            profile_id=str(payload["profile_id"]),
            strategy_family_id=str(payload["strategy_family_id"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_profile_id=str(payload["account_profile_id"]),
            execution_symbol=str(payload["execution_symbol"]),
            default_operating_posture=str(payload["default_operating_posture"]),
            signal_score_drift_relevant=bool(payload["signal_score_drift_relevant"]),
            dimensions=tuple(
                OperatingEnvelopeDimension.from_dict(dict(item))
                for item in payload.get("dimensions", ())
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OperatingEnvelopeProfile":
        return cls.from_dict(
            _decode_json_object(payload, label="operating_envelope_profile")
        )


@dataclass(frozen=True)
class SessionConditionedRiskRule:
    session_class: str
    band: str
    actions: tuple[str, ...]
    size_multiplier: float
    max_trade_count_multiplier: float
    required_operating_posture: str
    overnight_carry_allowed: bool
    diagnostic: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionConditionedRiskRule":
        return cls(
            session_class=str(payload["session_class"]),
            band=str(payload["band"]),
            actions=tuple(str(item) for item in payload.get("actions", ())),
            size_multiplier=float(payload["size_multiplier"]),
            max_trade_count_multiplier=float(payload["max_trade_count_multiplier"]),
            required_operating_posture=str(payload["required_operating_posture"]),
            overnight_carry_allowed=bool(payload["overnight_carry_allowed"]),
            diagnostic=str(payload["diagnostic"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class SessionConditionedRiskProfile:
    profile_id: str
    operating_envelope_profile_id: str
    rules: tuple[SessionConditionedRiskRule, ...]
    schema_version: int = SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rules"] = [rule.to_dict() for rule in self.rules]
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionConditionedRiskProfile":
        return cls(
            profile_id=str(payload["profile_id"]),
            operating_envelope_profile_id=str(payload["operating_envelope_profile_id"]),
            rules=tuple(
                SessionConditionedRiskRule.from_dict(dict(item))
                for item in payload.get("rules", ())
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "SessionConditionedRiskProfile":
        return cls.from_dict(
            _decode_json_object(payload, label="session_conditioned_risk_profile")
        )


@dataclass(frozen=True)
class OperatingEnvelopeEvaluationRequest:
    case_id: str
    operating_envelope_profile: OperatingEnvelopeProfile
    session_conditioned_risk_profile: SessionConditionedRiskProfile | None
    observed_values: dict[str, Any]
    current_session_class: str
    current_operating_posture: str
    schema_version: int = SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "operating_envelope_profile": self.operating_envelope_profile.to_dict(),
            "session_conditioned_risk_profile": (
                self.session_conditioned_risk_profile.to_dict()
                if self.session_conditioned_risk_profile is not None
                else None
            ),
            "observed_values": _jsonable(self.observed_values),
            "current_session_class": self.current_session_class,
            "current_operating_posture": self.current_operating_posture,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatingEnvelopeEvaluationRequest":
        return cls(
            case_id=str(payload["case_id"]),
            operating_envelope_profile=OperatingEnvelopeProfile.from_dict(
                dict(payload["operating_envelope_profile"])
            ),
            session_conditioned_risk_profile=(
                SessionConditionedRiskProfile.from_dict(
                    dict(payload["session_conditioned_risk_profile"])
                )
                if payload.get("session_conditioned_risk_profile") is not None
                else None
            ),
            observed_values=dict(payload["observed_values"]),
            current_session_class=str(payload["current_session_class"]),
            current_operating_posture=str(payload["current_operating_posture"]),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OperatingEnvelopeEvaluationRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="operating_envelope_request")
        )


@dataclass(frozen=True)
class EnvelopeDimensionResult:
    dimension_id: str
    title: str
    observed_value: float | str | None
    band: str
    actions: tuple[str, ...]
    reason_code: str | None
    diagnostic: str
    remediation: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EnvelopeDimensionResult":
        observed = payload.get("observed_value")
        return cls(
            dimension_id=str(payload["dimension_id"]),
            title=str(payload["title"]),
            observed_value=(
                float(observed) if isinstance(observed, int | float) else observed
            ),
            band=str(payload["band"]),
            actions=tuple(str(item) for item in payload.get("actions", ())),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            remediation=str(payload["remediation"]),
            context=dict(payload.get("context", {})),
        )


@dataclass(frozen=True)
class SessionRiskResult:
    session_class: str
    band: str
    actions: tuple[str, ...]
    reason_code: str | None
    size_multiplier: float
    max_trade_count_multiplier: float
    required_operating_posture: str
    overnight_carry_allowed: bool
    diagnostic: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionRiskResult":
        return cls(
            session_class=str(payload["session_class"]),
            band=str(payload["band"]),
            actions=tuple(str(item) for item in payload.get("actions", ())),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            size_multiplier=float(payload["size_multiplier"]),
            max_trade_count_multiplier=float(payload["max_trade_count_multiplier"]),
            required_operating_posture=str(payload["required_operating_posture"]),
            overnight_carry_allowed=bool(payload["overnight_carry_allowed"]),
            diagnostic=str(payload["diagnostic"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class OperatingEnvelopeEvaluationReport:
    case_id: str
    status: str
    reason_code: str
    operating_envelope_profile_id: str
    session_conditioned_risk_profile_id: str | None
    current_session_class: str
    current_operating_posture: str
    triggered_dimension_ids: tuple[str, ...]
    triggered_actions: tuple[str, ...]
    effective_size_multiplier: float
    effective_max_trade_count_multiplier: float
    resulting_entry_mode: str
    overnight_carry_allowed: bool
    required_operating_posture: str
    dimension_results: tuple[EnvelopeDimensionResult, ...]
    session_overlay: SessionRiskResult | None
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "operating_envelope_profile_id": self.operating_envelope_profile_id,
            "session_conditioned_risk_profile_id": self.session_conditioned_risk_profile_id,
            "current_session_class": self.current_session_class,
            "current_operating_posture": self.current_operating_posture,
            "triggered_dimension_ids": list(self.triggered_dimension_ids),
            "triggered_actions": list(self.triggered_actions),
            "effective_size_multiplier": self.effective_size_multiplier,
            "effective_max_trade_count_multiplier": self.effective_max_trade_count_multiplier,
            "resulting_entry_mode": self.resulting_entry_mode,
            "overnight_carry_allowed": self.overnight_carry_allowed,
            "required_operating_posture": self.required_operating_posture,
            "dimension_results": [result.to_dict() for result in self.dimension_results],
            "session_overlay": (
                self.session_overlay.to_dict() if self.session_overlay is not None else None
            ),
            "explanation": self.explanation,
            "remediation": self.remediation,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatingEnvelopeEvaluationReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            operating_envelope_profile_id=str(payload["operating_envelope_profile_id"]),
            session_conditioned_risk_profile_id=(
                str(payload["session_conditioned_risk_profile_id"])
                if payload.get("session_conditioned_risk_profile_id") not in (None, "")
                else None
            ),
            current_session_class=str(payload["current_session_class"]),
            current_operating_posture=str(payload["current_operating_posture"]),
            triggered_dimension_ids=tuple(
                str(item) for item in payload.get("triggered_dimension_ids", ())
            ),
            triggered_actions=tuple(
                str(item) for item in payload.get("triggered_actions", ())
            ),
            effective_size_multiplier=float(payload["effective_size_multiplier"]),
            effective_max_trade_count_multiplier=float(
                payload["effective_max_trade_count_multiplier"]
            ),
            resulting_entry_mode=str(payload["resulting_entry_mode"]),
            overnight_carry_allowed=bool(payload["overnight_carry_allowed"]),
            required_operating_posture=str(payload["required_operating_posture"]),
            dimension_results=tuple(
                EnvelopeDimensionResult.from_dict(dict(item))
                for item in payload.get("dimension_results", ())
            ),
            session_overlay=(
                SessionRiskResult.from_dict(dict(payload["session_overlay"]))
                if payload.get("session_overlay") is not None
                else None
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OperatingEnvelopeEvaluationReport":
        return cls.from_dict(
            _decode_json_object(payload, label="operating_envelope_report")
        )


def _band_reason_code(prefix: str, band: str) -> str:
    return f"{prefix}_{band.upper()}"


def _validate_band_spec(dimension: OperatingEnvelopeDimension) -> list[str]:
    errors: list[str] = []
    band_ids = [band.band for band in dimension.bands]
    if set(band_ids) != {
        OperatingEnvelopeStatus.GREEN.value,
        OperatingEnvelopeStatus.YELLOW.value,
        OperatingEnvelopeStatus.RED.value,
    }:
        errors.append(f"{dimension.dimension_id}: bands must cover green/yellow/red")

    for band in dimension.bands:
        invalid_actions = set(band.actions).difference(OPERATING_ENVELOPE_ACTIONS)
        if invalid_actions:
            names = ", ".join(sorted(invalid_actions))
            errors.append(f"{dimension.dimension_id}: invalid actions: {names}")
        if dimension.value_kind == EnvelopeValueKind.NUMERIC.value:
            if band.categorical_values:
                errors.append(
                    f"{dimension.dimension_id}: numeric dimensions must not use categorical_values"
                )
        elif dimension.value_kind == EnvelopeValueKind.CATEGORICAL.value:
            if not band.categorical_values:
                errors.append(
                    f"{dimension.dimension_id}: categorical dimensions must declare categorical_values"
                )
        else:
            errors.append(f"{dimension.dimension_id}: unknown value_kind {dimension.value_kind}")

    if dimension.value_kind == EnvelopeValueKind.NUMERIC.value:
        ordered = sorted(
            dimension.bands,
            key=lambda item: _STATUS_SEVERITY[item.band],
        )
        previous_maximum: float | None = None
        for band in ordered:
            if band.maximum_value is None and band.band != OperatingEnvelopeStatus.RED.value:
                errors.append(
                    f"{dimension.dimension_id}: only the red band may omit maximum_value"
                )
            if (
                previous_maximum is not None
                and band.minimum_value is not None
                and band.minimum_value < previous_maximum
            ):
                errors.append(
                    f"{dimension.dimension_id}: numeric bands must be monotonic and non-overlapping"
                )
            if band.maximum_value is not None:
                previous_maximum = band.maximum_value

    if dimension.value_kind == EnvelopeValueKind.CATEGORICAL.value:
        seen_values: set[str] = set()
        for band in dimension.bands:
            overlap = seen_values.intersection(set(band.categorical_values))
            if overlap:
                names = ", ".join(sorted(overlap))
                errors.append(
                    f"{dimension.dimension_id}: categorical band values must not overlap ({names})"
                )
            seen_values.update(band.categorical_values)

    return errors


def validate_operating_envelope_profile(
    profile: OperatingEnvelopeProfile,
    session_profile: SessionConditionedRiskProfile | None = None,
) -> list[str]:
    errors: list[str] = []
    if profile.schema_version != SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION:
        errors.append("operating envelope profile: unsupported schema version")
    if profile.default_operating_posture not in {posture.value for posture in OperatingPosture}:
        errors.append("operating envelope profile: unsupported default operating posture")

    dimension_ids = [dimension.dimension_id for dimension in profile.dimensions]
    if len(dimension_ids) != len(set(dimension_ids)):
        errors.append("operating envelope profile: dimension identifiers must be unique")

    required_dimensions = set(REQUIRED_OPERATING_ENVELOPE_DIMENSIONS)
    if profile.signal_score_drift_relevant:
        required_dimensions.add("signal_score_drift")

    missing_dimensions = required_dimensions.difference(dimension_ids)
    if missing_dimensions:
        names = ", ".join(sorted(missing_dimensions))
        errors.append(f"operating envelope profile: missing required dimensions: {names}")

    unexpected_dimensions = set(dimension_ids).difference(
        set(REQUIRED_OPERATING_ENVELOPE_DIMENSIONS).union(OPTIONAL_OPERATING_ENVELOPE_DIMENSIONS)
    )
    if unexpected_dimensions:
        names = ", ".join(sorted(unexpected_dimensions))
        errors.append(f"operating envelope profile: unsupported dimensions: {names}")

    for dimension in profile.dimensions:
        errors.extend(_validate_band_spec(dimension))

    if session_profile is None:
        return errors

    if session_profile.schema_version != SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION:
        errors.append("session-conditioned risk profile: unsupported schema version")
    if session_profile.operating_envelope_profile_id != profile.profile_id:
        errors.append(
            "session-conditioned risk profile: operating envelope binding must match profile_id"
        )

    rule_ids = [rule.session_class for rule in session_profile.rules]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append("session-conditioned risk profile: session classes must be unique")

    missing_classes = set(REQUIRED_SESSION_CLASSES).difference(rule_ids)
    if missing_classes:
        names = ", ".join(sorted(missing_classes))
        errors.append(f"session-conditioned risk profile: missing required classes: {names}")

    for rule in session_profile.rules:
        if rule.session_class not in REQUIRED_SESSION_CLASSES:
            errors.append(
                f"session-conditioned risk profile: unsupported session class {rule.session_class}"
            )
        if rule.band not in {
            OperatingEnvelopeStatus.GREEN.value,
            OperatingEnvelopeStatus.YELLOW.value,
            OperatingEnvelopeStatus.RED.value,
        }:
            errors.append(
                f"session-conditioned risk profile: invalid band for {rule.session_class}"
            )
        invalid_actions = set(rule.actions).difference(OPERATING_ENVELOPE_ACTIONS)
        if invalid_actions:
            names = ", ".join(sorted(invalid_actions))
            errors.append(
                f"session-conditioned risk profile: invalid actions for {rule.session_class}: {names}"
            )
        if not 0.0 <= rule.size_multiplier <= 1.0:
            errors.append(
                f"session-conditioned risk profile: size_multiplier must be within [0, 1] for {rule.session_class}"
            )
        if not 0.0 <= rule.max_trade_count_multiplier <= 1.0:
            errors.append(
                f"session-conditioned risk profile: max_trade_count_multiplier must be within [0, 1] for {rule.session_class}"
            )
        if rule.required_operating_posture not in {
            posture.value for posture in OperatingPosture
        }:
            errors.append(
                f"session-conditioned risk profile: invalid operating posture for {rule.session_class}"
            )

    return errors


def _invalid_report(
    request: OperatingEnvelopeEvaluationRequest,
    *,
    reason_code: str,
    explanation: str,
    remediation: str,
) -> OperatingEnvelopeEvaluationReport:
    return OperatingEnvelopeEvaluationReport(
        case_id=request.case_id,
        status=OperatingEnvelopeStatus.INVALID.value,
        reason_code=reason_code,
        operating_envelope_profile_id=request.operating_envelope_profile.profile_id,
        session_conditioned_risk_profile_id=(
            request.session_conditioned_risk_profile.profile_id
            if request.session_conditioned_risk_profile is not None
            else None
        ),
        current_session_class=request.current_session_class,
        current_operating_posture=request.current_operating_posture,
        triggered_dimension_ids=(),
        triggered_actions=(),
        effective_size_multiplier=0.0,
        effective_max_trade_count_multiplier=0.0,
        resulting_entry_mode=EntryMode.NO_NEW_ENTRIES.value,
        overnight_carry_allowed=False,
        required_operating_posture=request.current_operating_posture,
        dimension_results=(),
        session_overlay=None,
        explanation=explanation,
        remediation=remediation,
    )


def _matches_numeric_band(
    numeric_value: float,
    band: OperatingEnvelopeBand,
) -> bool:
    if band.minimum_value is not None and numeric_value < band.minimum_value:
        return False
    if band.maximum_value is not None and numeric_value >= band.maximum_value:
        return False
    return True


def _evaluate_dimension(
    dimension: OperatingEnvelopeDimension,
    observed_value: Any,
) -> EnvelopeDimensionResult:
    if dimension.value_kind == EnvelopeValueKind.NUMERIC.value:
        try:
            numeric_value = float(observed_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{dimension.dimension_id}: expected numeric observed value") from exc
        for band in sorted(dimension.bands, key=lambda item: _STATUS_SEVERITY[item.band]):
            if _matches_numeric_band(numeric_value, band):
                return EnvelopeDimensionResult(
                    dimension_id=dimension.dimension_id,
                    title=dimension.title,
                    observed_value=numeric_value,
                    band=band.band,
                    actions=band.actions,
                    reason_code=(
                        None
                        if band.band == OperatingEnvelopeStatus.GREEN.value
                        else _band_reason_code(
                            f"OPERATING_ENVELOPE_{dimension.dimension_id.upper()}",
                            band.band,
                        )
                    ),
                    diagnostic=band.diagnostic,
                    remediation=band.remediation,
                    context={
                        "dimension_id": dimension.dimension_id,
                        "unit": dimension.unit,
                    },
                )
        raise ValueError(f"{dimension.dimension_id}: no matching numeric band for {numeric_value}")

    categorical_value = str(observed_value)
    for band in sorted(dimension.bands, key=lambda item: _STATUS_SEVERITY[item.band]):
        if categorical_value in band.categorical_values:
            return EnvelopeDimensionResult(
                dimension_id=dimension.dimension_id,
                title=dimension.title,
                observed_value=categorical_value,
                band=band.band,
                actions=band.actions,
                reason_code=(
                    None
                    if band.band == OperatingEnvelopeStatus.GREEN.value
                    else _band_reason_code(
                        f"OPERATING_ENVELOPE_{dimension.dimension_id.upper()}",
                        band.band,
                    )
                ),
                diagnostic=band.diagnostic,
                remediation=band.remediation,
                context={
                    "dimension_id": dimension.dimension_id,
                    "unit": dimension.unit,
                },
            )
    raise ValueError(
        f"{dimension.dimension_id}: no matching categorical band for {categorical_value}"
    )


def _derive_entry_mode(actions: tuple[str, ...]) -> str:
    action_set = set(actions)
    if OperatingEnvelopeAction.FORCED_FLATTEN.value in action_set:
        return EntryMode.FORCED_FLATTEN.value
    if OperatingEnvelopeAction.EXIT_ONLY.value in action_set:
        return EntryMode.EXIT_ONLY.value
    if OperatingEnvelopeAction.ENTRY_SUPPRESSION.value in action_set:
        return EntryMode.NO_NEW_ENTRIES.value
    if OperatingEnvelopeAction.PASSIVE_ENTRY_SUPPRESSION.value in action_set:
        return EntryMode.PASSIVE_ONLY.value
    return EntryMode.NORMAL.value


def evaluate_operating_envelope(
    request: OperatingEnvelopeEvaluationRequest,
) -> OperatingEnvelopeEvaluationReport:
    if request.schema_version != SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_SCHEMA_VERSION_UNSUPPORTED",
            explanation="The operating-envelope request uses an unsupported schema version.",
            remediation="Rebuild the request using the supported operating-envelope schema version.",
        )

    validation_errors = validate_operating_envelope_profile(
        request.operating_envelope_profile,
        request.session_conditioned_risk_profile,
    )
    if validation_errors:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_PROFILE_INVALID",
            explanation=(
                "The operating-envelope or session-conditioned risk profile failed "
                f"validation: {validation_errors}."
            ),
            remediation=(
                "Repair the profile definition before using it in runtime or session-readiness "
                "workflows."
            ),
        )

    if request.current_session_class not in REQUIRED_SESSION_CLASSES:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_SESSION_CLASS_UNSUPPORTED",
            explanation="The request named an unsupported current session class.",
            remediation="Use one of the canonical session classes defined by the profile.",
        )

    missing_observed_dimensions = [
        dimension.dimension_id
        for dimension in request.operating_envelope_profile.dimensions
        if dimension.dimension_id not in request.observed_values
    ]
    if missing_observed_dimensions:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_OBSERVED_VALUES_MISSING",
            explanation=(
                "The operating-envelope request did not include all observed regime values: "
                f"{missing_observed_dimensions}."
            ),
            remediation="Populate each dimension with the current observed value before evaluation.",
        )

    if request.current_operating_posture not in {posture.value for posture in OperatingPosture}:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_POSTURE_UNSUPPORTED",
            explanation="The request named an unsupported current operating posture.",
            remediation="Use one of the canonical operating postures.",
        )

    dimension_results: list[EnvelopeDimensionResult] = []
    try:
        for dimension in request.operating_envelope_profile.dimensions:
            dimension_results.append(
                _evaluate_dimension(
                    dimension,
                    request.observed_values[dimension.dimension_id],
                )
            )
    except ValueError as exc:
        return _invalid_report(
            request,
            reason_code="OPERATING_ENVELOPE_DIMENSION_UNMATCHED",
            explanation=str(exc),
            remediation="Repair the observed values or band definitions so each dimension resolves.",
        )

    session_overlay: SessionRiskResult | None = None
    if request.session_conditioned_risk_profile is not None:
        matching_rule = next(
            (
                rule
                for rule in request.session_conditioned_risk_profile.rules
                if rule.session_class == request.current_session_class
            ),
            None,
        )
        if matching_rule is None:
            return _invalid_report(
                request,
                reason_code="SESSION_RISK_PROFILE_RULE_MISSING",
                explanation="The session-conditioned risk profile has no rule for this session class.",
                remediation="Add a canonical rule for the current session class.",
            )
        session_overlay = SessionRiskResult(
            session_class=matching_rule.session_class,
            band=matching_rule.band,
            actions=matching_rule.actions,
            reason_code=(
                None
                if matching_rule.band == OperatingEnvelopeStatus.GREEN.value
                else _band_reason_code(
                    f"SESSION_RISK_PROFILE_{matching_rule.session_class.upper()}",
                    matching_rule.band,
                )
            ),
            size_multiplier=matching_rule.size_multiplier,
            max_trade_count_multiplier=matching_rule.max_trade_count_multiplier,
            required_operating_posture=matching_rule.required_operating_posture,
            overnight_carry_allowed=matching_rule.overnight_carry_allowed,
            diagnostic=matching_rule.diagnostic,
            remediation=matching_rule.remediation,
        )

    all_results: list[EnvelopeDimensionResult | SessionRiskResult] = list(dimension_results)
    if session_overlay is not None:
        all_results.append(session_overlay)

    _, dominant_result = max(
        enumerate(all_results),
        key=lambda item: (
            _STATUS_SEVERITY[item[1].band],
            max((_ACTION_SEVERITY[action] for action in item[1].actions), default=0),
            item[0],
        ),
    )
    overall_status = dominant_result.band

    triggered_dimension_ids = tuple(
        result.dimension_id
        for result in dimension_results
        if result.band != OperatingEnvelopeStatus.GREEN.value
    )
    triggered_actions = _sorted_unique_actions(
        [
            action
            for result in dimension_results
            if result.band != OperatingEnvelopeStatus.GREEN.value
            for action in result.actions
        ]
        + (
            list(session_overlay.actions)
            if session_overlay is not None
            and session_overlay.band != OperatingEnvelopeStatus.GREEN.value
            else []
        )
    )

    effective_size_multiplier = session_overlay.size_multiplier if session_overlay else 1.0
    effective_max_trade_count_multiplier = (
        session_overlay.max_trade_count_multiplier if session_overlay else 1.0
    )
    overnight_carry_allowed = session_overlay.overnight_carry_allowed if session_overlay else True
    required_operating_posture = (
        session_overlay.required_operating_posture
        if session_overlay is not None
        else request.operating_envelope_profile.default_operating_posture
    )

    for action in triggered_actions:
        effective_size_multiplier = min(
            effective_size_multiplier,
            _ACTION_SIZE_MULTIPLIERS[action],
        )
        effective_max_trade_count_multiplier = min(
            effective_max_trade_count_multiplier,
            _ACTION_MAX_TRADE_MULTIPLIERS[action],
        )
    if OperatingEnvelopeAction.NO_NEW_OVERNIGHT_CARRY.value in triggered_actions:
        overnight_carry_allowed = False

    resulting_entry_mode = _derive_entry_mode(triggered_actions)
    reason_code = (
        dominant_result.reason_code
        if dominant_result.reason_code is not None
        else "OPERATING_ENVELOPE_GREEN"
    )

    if overall_status == OperatingEnvelopeStatus.GREEN.value:
        explanation = (
            "All operating-envelope dimensions and the session-conditioned overlay remained "
            "within the green band."
        )
        remediation = "No remediation required."
    else:
        explanation = (
            "Operating-envelope evaluation changed posture because "
            f"{triggered_dimension_ids or ('session_overlay',)} crossed into the {overall_status} band."
        )
        remediation = dominant_result.remediation

    return OperatingEnvelopeEvaluationReport(
        case_id=request.case_id,
        status=overall_status,
        reason_code=reason_code,
        operating_envelope_profile_id=request.operating_envelope_profile.profile_id,
        session_conditioned_risk_profile_id=(
            request.session_conditioned_risk_profile.profile_id
            if request.session_conditioned_risk_profile is not None
            else None
        ),
        current_session_class=request.current_session_class,
        current_operating_posture=request.current_operating_posture,
        triggered_dimension_ids=triggered_dimension_ids,
        triggered_actions=triggered_actions,
        effective_size_multiplier=effective_size_multiplier,
        effective_max_trade_count_multiplier=effective_max_trade_count_multiplier,
        resulting_entry_mode=resulting_entry_mode,
        overnight_carry_allowed=overnight_carry_allowed,
        required_operating_posture=required_operating_posture,
        dimension_results=tuple(dimension_results),
        session_overlay=session_overlay,
        explanation=explanation,
        remediation=remediation,
    )


def validate_operating_envelope_catalog() -> list[str]:
    errors: list[str] = []
    if len(REQUIRED_OPERATING_ENVELOPE_DIMENSIONS) != len(
        set(REQUIRED_OPERATING_ENVELOPE_DIMENSIONS)
    ):
        errors.append("required operating-envelope dimensions must be unique")
    if len(REQUIRED_SESSION_CLASSES) != len(set(REQUIRED_SESSION_CLASSES)):
        errors.append("required session classes must be unique")
    if len(OPERATING_ENVELOPE_ACTIONS) != len(set(OPERATING_ENVELOPE_ACTIONS)):
        errors.append("operating-envelope actions must be unique")
    if SUPPORTED_OPERATING_ENVELOPE_SCHEMA_VERSION < 1:
        errors.append("operating-envelope schema version must remain positive")
    return errors


VALIDATION_ERRORS = validate_operating_envelope_catalog()
