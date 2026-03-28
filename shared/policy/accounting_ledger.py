"""Append-only accounting ledger contracts and booked-versus-reconciled close reports."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum, unique
from typing import Iterable


SUPPORTED_LEDGER_SCHEMA_VERSION = 1
ZERO = Decimal("0")


def _decimal(value: Decimal | str | int | float | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        parsed = value
    else:
        if isinstance(value, bool):
            raise ValueError("decimal fields must be finite decimal-compatible values")
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("decimal fields must be finite decimal-compatible values") from exc
    if not parsed.is_finite():
        raise ValueError("decimal fields must be finite decimal-compatible values")
    return parsed


def _decimal_or_none(value: Decimal | str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value)


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise ValueError(f"{label}: invalid JSON payload: {exc}") from exc
    if not isinstance(decoded, dict):  # pragma: no cover
        raise ValueError(f"{label}: expected a JSON object payload")
    return decoded


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_present(
    payload: dict[str, object],
    key: str,
    *,
    field_name: str,
) -> object:
    if key not in payload:
        raise ValueError(f"{field_name} missing required field")
    return payload[key]


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of non-empty strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _require_mapping_sequence(value: object, *, field_name: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of objects")
    return tuple(
        _require_mapping(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _require_string_mapping(value: object, *, field_name: str) -> dict[str, str]:
    mapping = _require_mapping(value, field_name=field_name)
    normalized: dict[str, str] = {}
    for key, item in mapping.items():
        normalized_key = _require_non_empty_string(key, field_name=f"{field_name}.key")
        if not isinstance(item, str):
            raise ValueError(f"{field_name}.{normalized_key} must be a string")
        normalized[normalized_key] = item
    return normalized


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_schema_version(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label}: schema_version must be an integer")
    if value != SUPPORTED_LEDGER_SCHEMA_VERSION:
        raise ValueError(f"{label}: unsupported schema_version")
    return value


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _require_close_status(value: object) -> str:
    if isinstance(value, LedgerCloseStatus):
        return value.value
    if not isinstance(value, str):
        raise ValueError("status must be a valid ledger close status")
    try:
        return LedgerCloseStatus(value).value
    except ValueError as exc:
        raise ValueError("status must be a valid ledger close status") from exc


def _require_event_class(value: object, *, field_name: str) -> str:
    if isinstance(value, LedgerEventClass):
        return value.value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a valid ledger event class")
    try:
        return LedgerEventClass(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ledger event class") from exc


@unique
class LedgerCloseStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    REVIEW_REQUIRED = "review_required"
    VIOLATION = "violation"


@unique
class LedgerEventClass(str, Enum):
    BOOKED_FILL = "booked_fill"
    BOOKED_FEE = "booked_fee"
    BOOKED_COMMISSION = "booked_commission"
    BOOKED_CASH_MOVEMENT = "booked_cash_movement"
    BROKER_EOD_POSITION = "broker_eod_position"
    BROKER_EOD_MARGIN_SNAPSHOT = "broker_eod_margin_snapshot"
    RECONCILIATION_ADJUSTMENT = "reconciliation_adjustment"
    RESTATEMENT = "restatement"
    UNRESOLVED_DISCREPANCY = "unresolved_discrepancy"


BOOKED_EVENT_CLASSES = frozenset(
    {
        LedgerEventClass.BOOKED_FILL,
        LedgerEventClass.BOOKED_FEE,
        LedgerEventClass.BOOKED_COMMISSION,
        LedgerEventClass.BOOKED_CASH_MOVEMENT,
    }
)
RECONCILING_EVENT_CLASSES = frozenset(
    {
        LedgerEventClass.RECONCILIATION_ADJUSTMENT,
        LedgerEventClass.RESTATEMENT,
    }
)


def ledger_event_class_ids() -> tuple[str, ...]:
    return tuple(event_class.value for event_class in LedgerEventClass)


@dataclass(frozen=True)
class LedgerEvent:
    sequence_id: int
    event_id: str
    event_class: LedgerEventClass
    account_id: str
    symbol: str
    occurred_at: str
    description: str
    correlation_id: str = ""
    reference_event_id: str | None = None
    discrepancy_id: str | None = None
    position_delta_contracts: Decimal = ZERO
    cash_delta_usd: Decimal = ZERO
    realized_pnl_delta_usd: Decimal = ZERO
    fee_delta_usd: Decimal = ZERO
    commission_delta_usd: Decimal = ZERO
    authoritative_position_contracts: Decimal | None = None
    authoritative_initial_margin_requirement_usd: Decimal | None = None
    authoritative_maintenance_margin_requirement_usd: Decimal | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    schema_version: int = SUPPORTED_LEDGER_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence_id": self.sequence_id,
            "event_id": self.event_id,
            "event_class": self.event_class.value,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "occurred_at": self.occurred_at,
            "description": self.description,
            "correlation_id": self.correlation_id,
            "reference_event_id": self.reference_event_id,
            "discrepancy_id": self.discrepancy_id,
            "position_delta_contracts": _decimal_text(self.position_delta_contracts),
            "cash_delta_usd": _decimal_text(self.cash_delta_usd),
            "realized_pnl_delta_usd": _decimal_text(self.realized_pnl_delta_usd),
            "fee_delta_usd": _decimal_text(self.fee_delta_usd),
            "commission_delta_usd": _decimal_text(self.commission_delta_usd),
            "authoritative_position_contracts": _decimal_text(
                self.authoritative_position_contracts
            ),
            "authoritative_initial_margin_requirement_usd": _decimal_text(
                self.authoritative_initial_margin_requirement_usd
            ),
            "authoritative_maintenance_margin_requirement_usd": _decimal_text(
                self.authoritative_maintenance_margin_requirement_usd
            ),
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LedgerEvent":
        payload = _require_mapping(payload, field_name="ledger_event")
        return cls(
            sequence_id=_require_int(
                _require_present(payload, "sequence_id", field_name="sequence_id"),
                field_name="sequence_id",
            ),
            event_id=_require_non_empty_string(
                _require_present(payload, "event_id", field_name="event_id"),
                field_name="event_id",
            ),
            event_class=LedgerEventClass(
                _require_event_class(
                    _require_present(payload, "event_class", field_name="event_class"),
                    field_name="event_class",
                )
            ),
            account_id=_require_non_empty_string(
                _require_present(payload, "account_id", field_name="account_id"),
                field_name="account_id",
            ),
            symbol=_require_non_empty_string(
                _require_present(payload, "symbol", field_name="symbol"),
                field_name="symbol",
            ),
            occurred_at=_normalize_utc_timestamp(
                _require_present(payload, "occurred_at", field_name="occurred_at"),
                field_name="occurred_at",
            ),
            description=_require_non_empty_string(
                _require_present(payload, "description", field_name="description"),
                field_name="description",
            ),
            correlation_id=_require_string(
                _require_present(payload, "correlation_id", field_name="correlation_id"),
                field_name="correlation_id",
            ),
            reference_event_id=_optional_non_empty_string(
                _require_present(payload, "reference_event_id", field_name="reference_event_id"),
                field_name="reference_event_id",
            ),
            discrepancy_id=_optional_non_empty_string(
                _require_present(payload, "discrepancy_id", field_name="discrepancy_id"),
                field_name="discrepancy_id",
            ),
            position_delta_contracts=_decimal(
                _require_present(
                    payload,
                    "position_delta_contracts",
                    field_name="position_delta_contracts",
                )
            ),
            cash_delta_usd=_decimal(
                _require_present(payload, "cash_delta_usd", field_name="cash_delta_usd")
            ),
            realized_pnl_delta_usd=_decimal(
                _require_present(
                    payload,
                    "realized_pnl_delta_usd",
                    field_name="realized_pnl_delta_usd",
                )
            ),
            fee_delta_usd=_decimal(
                _require_present(payload, "fee_delta_usd", field_name="fee_delta_usd")
            ),
            commission_delta_usd=_decimal(
                _require_present(
                    payload,
                    "commission_delta_usd",
                    field_name="commission_delta_usd",
                )
            ),
            authoritative_position_contracts=_decimal_or_none(
                _require_present(
                    payload,
                    "authoritative_position_contracts",
                    field_name="authoritative_position_contracts",
                )
            ),
            authoritative_initial_margin_requirement_usd=_decimal_or_none(
                _require_present(
                    payload,
                    "authoritative_initial_margin_requirement_usd",
                    field_name="authoritative_initial_margin_requirement_usd",
                )
            ),
            authoritative_maintenance_margin_requirement_usd=_decimal_or_none(
                _require_present(
                    payload,
                    "authoritative_maintenance_margin_requirement_usd",
                    field_name="authoritative_maintenance_margin_requirement_usd",
                )
            ),
            metadata=_require_string_mapping(
                _require_present(payload, "metadata", field_name="metadata"),
                field_name="metadata",
            ),
            schema_version=_require_schema_version(
                _require_present(payload, "schema_version", field_name="schema_version"),
                label="ledger_event",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "LedgerEvent":
        return cls.from_dict(_decode_json_object(payload, "ledger_event"))


@dataclass(frozen=True)
class LedgerTotals:
    position_contracts: Decimal = ZERO
    cash_balance_usd: Decimal = ZERO
    realized_pnl_usd: Decimal = ZERO
    fee_total_usd: Decimal = ZERO
    commission_total_usd: Decimal = ZERO

    def to_dict(self) -> dict[str, str]:
        return {
            "position_contracts": _decimal_text(self.position_contracts) or "0",
            "cash_balance_usd": _decimal_text(self.cash_balance_usd) or "0",
            "realized_pnl_usd": _decimal_text(self.realized_pnl_usd) or "0",
            "fee_total_usd": _decimal_text(self.fee_total_usd) or "0",
            "commission_total_usd": _decimal_text(self.commission_total_usd) or "0",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LedgerTotals":
        payload = _require_mapping(payload, field_name="ledger_totals")
        return cls(
            position_contracts=_decimal(
                _require_present(
                    payload,
                    "position_contracts",
                    field_name="position_contracts",
                )
            ),
            cash_balance_usd=_decimal(
                _require_present(
                    payload,
                    "cash_balance_usd",
                    field_name="cash_balance_usd",
                )
            ),
            realized_pnl_usd=_decimal(
                _require_present(
                    payload,
                    "realized_pnl_usd",
                    field_name="realized_pnl_usd",
                )
            ),
            fee_total_usd=_decimal(
                _require_present(
                    payload,
                    "fee_total_usd",
                    field_name="fee_total_usd",
                )
            ),
            commission_total_usd=_decimal(
                _require_present(
                    payload,
                    "commission_total_usd",
                    field_name="commission_total_usd",
                )
            ),
        )


@dataclass(frozen=True)
class BrokerAuthoritativeSnapshot:
    position_contracts: Decimal | None
    initial_margin_requirement_usd: Decimal | None
    maintenance_margin_requirement_usd: Decimal | None
    position_event_id: str | None
    margin_event_id: str | None
    source_timestamp: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "position_contracts": _decimal_text(self.position_contracts),
            "initial_margin_requirement_usd": _decimal_text(
                self.initial_margin_requirement_usd
            ),
            "maintenance_margin_requirement_usd": _decimal_text(
                self.maintenance_margin_requirement_usd
            ),
            "position_event_id": self.position_event_id,
            "margin_event_id": self.margin_event_id,
            "source_timestamp": self.source_timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "BrokerAuthoritativeSnapshot":
        payload = _require_mapping(payload, field_name="broker_authoritative_snapshot")
        return cls(
            position_contracts=_decimal_or_none(
                _require_present(payload, "position_contracts", field_name="position_contracts")
            ),
            initial_margin_requirement_usd=_decimal_or_none(
                _require_present(
                    payload,
                    "initial_margin_requirement_usd",
                    field_name="initial_margin_requirement_usd",
                )
            ),
            maintenance_margin_requirement_usd=_decimal_or_none(
                _require_present(
                    payload,
                    "maintenance_margin_requirement_usd",
                    field_name="maintenance_margin_requirement_usd",
                )
            ),
            position_event_id=_optional_non_empty_string(
                _require_present(payload, "position_event_id", field_name="position_event_id"),
                field_name="position_event_id",
            ),
            margin_event_id=_optional_non_empty_string(
                _require_present(payload, "margin_event_id", field_name="margin_event_id"),
                field_name="margin_event_id",
            ),
            source_timestamp=(
                None
                if _require_present(payload, "source_timestamp", field_name="source_timestamp")
                is None
                else _normalize_utc_timestamp(
                    payload["source_timestamp"],
                    field_name="source_timestamp",
                )
            ),
        )


@dataclass(frozen=True)
class LedgerDifference:
    metric: str
    as_booked: Decimal | None
    as_reconciled: Decimal | None
    authoritative: Decimal | None
    booked_vs_reconciled_delta: Decimal | None
    reconciled_vs_authoritative_delta: Decimal | None
    explanation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "as_booked": _decimal_text(self.as_booked),
            "as_reconciled": _decimal_text(self.as_reconciled),
            "authoritative": _decimal_text(self.authoritative),
            "booked_vs_reconciled_delta": _decimal_text(self.booked_vs_reconciled_delta),
            "reconciled_vs_authoritative_delta": _decimal_text(
                self.reconciled_vs_authoritative_delta
            ),
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LedgerDifference":
        payload = _require_mapping(payload, field_name="ledger_difference")
        return cls(
            metric=_require_non_empty_string(
                _require_present(payload, "metric", field_name="metric"),
                field_name="metric",
            ),
            as_booked=_decimal_or_none(
                _require_present(payload, "as_booked", field_name="as_booked")
            ),
            as_reconciled=_decimal_or_none(
                _require_present(payload, "as_reconciled", field_name="as_reconciled")
            ),
            authoritative=_decimal_or_none(
                _require_present(payload, "authoritative", field_name="authoritative")
            ),
            booked_vs_reconciled_delta=_decimal_or_none(
                _require_present(
                    payload,
                    "booked_vs_reconciled_delta",
                    field_name="booked_vs_reconciled_delta",
                )
            ),
            reconciled_vs_authoritative_delta=_decimal_or_none(
                _require_present(
                    payload,
                    "reconciled_vs_authoritative_delta",
                    field_name="reconciled_vs_authoritative_delta",
                )
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, "explanation", field_name="explanation"),
                field_name="explanation",
            ),
        )


@dataclass(frozen=True)
class AppendOnlyIntegrityReport:
    valid: bool
    reason_code: str
    explanation: str
    duplicate_event_id: str | None = None
    violating_sequence_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "duplicate_event_id": self.duplicate_event_id,
            "violating_sequence_id": self.violating_sequence_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AppendOnlyIntegrityReport":
        payload = _require_mapping(payload, field_name="append_only_integrity")
        return cls(
            valid=_require_bool(
                _require_present(payload, "valid", field_name="valid"),
                field_name="valid",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, "reason_code", field_name="reason_code"),
                field_name="reason_code",
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, "explanation", field_name="explanation"),
                field_name="explanation",
            ),
            duplicate_event_id=_optional_non_empty_string(
                _require_present(payload, "duplicate_event_id", field_name="duplicate_event_id"),
                field_name="duplicate_event_id",
            ),
            violating_sequence_id=(
                None
                if _require_present(
                    payload,
                    "violating_sequence_id",
                    field_name="violating_sequence_id",
                )
                is None
                else _require_int(
                    payload["violating_sequence_id"],
                    field_name="violating_sequence_id",
                )
            ),
        )


@dataclass(frozen=True)
class LedgerCloseArtifact:
    close_id: str
    account_id: str
    symbol: str
    status: str
    reason_code: str
    append_only_integrity: AppendOnlyIntegrityReport
    event_classes_present: tuple[str, ...]
    trace_event_ids: tuple[str, ...]
    as_booked_totals: LedgerTotals
    as_reconciled_totals: LedgerTotals
    broker_authoritative_snapshot: BrokerAuthoritativeSnapshot
    differences: tuple[LedgerDifference, ...]
    unresolved_discrepancy_ids: tuple[str, ...]
    restatement_event_ids: tuple[str, ...]
    explanation: str
    timestamp: str = field(default_factory=_utc_now)
    schema_version: int = SUPPORTED_LEDGER_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "close_id": self.close_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "status": self.status,
            "reason_code": self.reason_code,
            "append_only_integrity": self.append_only_integrity.to_dict(),
            "event_classes_present": list(self.event_classes_present),
            "trace_event_ids": list(self.trace_event_ids),
            "as_booked_totals": self.as_booked_totals.to_dict(),
            "as_reconciled_totals": self.as_reconciled_totals.to_dict(),
            "broker_authoritative_snapshot": self.broker_authoritative_snapshot.to_dict(),
            "differences": [difference.to_dict() for difference in self.differences],
            "unresolved_discrepancy_ids": list(self.unresolved_discrepancy_ids),
            "restatement_event_ids": list(self.restatement_event_ids),
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LedgerCloseArtifact":
        payload = _require_mapping(payload, field_name="ledger_close_artifact")
        return cls(
            close_id=_require_non_empty_string(
                _require_present(payload, "close_id", field_name="close_id"),
                field_name="close_id",
            ),
            account_id=_require_non_empty_string(
                _require_present(payload, "account_id", field_name="account_id"),
                field_name="account_id",
            ),
            symbol=_require_non_empty_string(
                _require_present(payload, "symbol", field_name="symbol"),
                field_name="symbol",
            ),
            status=_require_close_status(
                _require_present(payload, "status", field_name="status")
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, "reason_code", field_name="reason_code"),
                field_name="reason_code",
            ),
            append_only_integrity=AppendOnlyIntegrityReport.from_dict(
                _require_mapping(
                    _require_present(
                        payload,
                        "append_only_integrity",
                        field_name="append_only_integrity",
                    ),
                    field_name="append_only_integrity",
                )
            ),
            event_classes_present=tuple(
                _require_event_class(item, field_name=f"event_classes_present[{index}]")
                for index, item in enumerate(
                    _require_string_sequence(
                        _require_present(
                            payload,
                            "event_classes_present",
                            field_name="event_classes_present",
                        ),
                        field_name="event_classes_present",
                    )
                )
            ),
            trace_event_ids=_require_string_sequence(
                _require_present(payload, "trace_event_ids", field_name="trace_event_ids"),
                field_name="trace_event_ids",
            ),
            as_booked_totals=LedgerTotals.from_dict(
                _require_mapping(
                    _require_present(
                        payload,
                        "as_booked_totals",
                        field_name="as_booked_totals",
                    ),
                    field_name="as_booked_totals",
                )
            ),
            as_reconciled_totals=LedgerTotals.from_dict(
                _require_mapping(
                    _require_present(
                        payload,
                        "as_reconciled_totals",
                        field_name="as_reconciled_totals",
                    ),
                    field_name="as_reconciled_totals",
                )
            ),
            broker_authoritative_snapshot=BrokerAuthoritativeSnapshot.from_dict(
                _require_mapping(
                    _require_present(
                        payload,
                        "broker_authoritative_snapshot",
                        field_name="broker_authoritative_snapshot",
                    ),
                    field_name="broker_authoritative_snapshot",
                )
            ),
            differences=tuple(
                LedgerDifference.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(payload, "differences", field_name="differences"),
                    field_name="differences",
                )
            ),
            unresolved_discrepancy_ids=_require_string_sequence(
                _require_present(
                    payload,
                    "unresolved_discrepancy_ids",
                    field_name="unresolved_discrepancy_ids",
                ),
                field_name="unresolved_discrepancy_ids",
            ),
            restatement_event_ids=_require_string_sequence(
                _require_present(
                    payload,
                    "restatement_event_ids",
                    field_name="restatement_event_ids",
                ),
                field_name="restatement_event_ids",
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, "explanation", field_name="explanation"),
                field_name="explanation",
            ),
            timestamp=_normalize_utc_timestamp(
                _require_present(payload, "timestamp", field_name="timestamp"),
                field_name="timestamp",
            ),
            schema_version=_require_schema_version(
                _require_present(payload, "schema_version", field_name="schema_version"),
                label="ledger_close_artifact",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "LedgerCloseArtifact":
        return cls.from_dict(_decode_json_object(payload, "ledger_close_artifact"))


def validate_append_only_ledger(
    events: Iterable[LedgerEvent],
    *,
    account_id: str | None = None,
    symbol: str | None = None,
) -> AppendOnlyIntegrityReport:
    previous_sequence: int | None = None
    seen_event_ids: set[str] = set()
    for event in events:
        if previous_sequence is not None and event.sequence_id <= previous_sequence:
            return AppendOnlyIntegrityReport(
                valid=False,
                reason_code="LEDGER_SEQUENCE_OUT_OF_ORDER",
                explanation=(
                    "Append-only ledger sequence must be strictly increasing to preserve "
                    "booked-versus-reconciled traceability."
                ),
                violating_sequence_id=event.sequence_id,
            )
        if event.event_id in seen_event_ids:
            return AppendOnlyIntegrityReport(
                valid=False,
                reason_code="LEDGER_EVENT_ID_DUPLICATE",
                explanation="Append-only ledger event identifiers must be unique.",
                duplicate_event_id=event.event_id,
                violating_sequence_id=event.sequence_id,
            )
        if account_id is not None and event.account_id != account_id:
            return AppendOnlyIntegrityReport(
                valid=False,
                reason_code="LEDGER_ACCOUNT_SCOPE_MISMATCH",
                explanation="Ledger close scope mixes events from different accounts.",
                violating_sequence_id=event.sequence_id,
            )
        if symbol is not None and event.symbol != symbol:
            return AppendOnlyIntegrityReport(
                valid=False,
                reason_code="LEDGER_SYMBOL_SCOPE_MISMATCH",
                explanation="Ledger close scope mixes events from different execution symbols.",
                violating_sequence_id=event.sequence_id,
            )
        previous_sequence = event.sequence_id
        seen_event_ids.add(event.event_id)
    return AppendOnlyIntegrityReport(
        valid=True,
        reason_code="LEDGER_APPEND_ONLY_VALID",
        explanation="Ledger sequence is append-only and uniquely identified.",
    )


def _aggregate_totals(
    events: Iterable[LedgerEvent],
    allowed_classes: frozenset[LedgerEventClass],
) -> LedgerTotals:
    position_contracts = ZERO
    cash_balance_usd = ZERO
    realized_pnl_usd = ZERO
    fee_total_usd = ZERO
    commission_total_usd = ZERO
    for event in events:
        if event.event_class not in allowed_classes:
            continue
        position_contracts += event.position_delta_contracts
        cash_balance_usd += event.cash_delta_usd
        realized_pnl_usd += event.realized_pnl_delta_usd
        fee_total_usd += event.fee_delta_usd
        commission_total_usd += event.commission_delta_usd
    return LedgerTotals(
        position_contracts=position_contracts,
        cash_balance_usd=cash_balance_usd,
        realized_pnl_usd=realized_pnl_usd,
        fee_total_usd=fee_total_usd,
        commission_total_usd=commission_total_usd,
    )


def _latest_broker_snapshot(events: Iterable[LedgerEvent]) -> BrokerAuthoritativeSnapshot:
    position_contracts: Decimal | None = None
    initial_margin_requirement_usd: Decimal | None = None
    maintenance_margin_requirement_usd: Decimal | None = None
    position_event_id: str | None = None
    margin_event_id: str | None = None
    source_timestamp: str | None = None
    for event in events:
        if event.event_class == LedgerEventClass.BROKER_EOD_POSITION:
            position_contracts = event.authoritative_position_contracts
            position_event_id = event.event_id
            source_timestamp = event.occurred_at
        if event.event_class == LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT:
            initial_margin_requirement_usd = event.authoritative_initial_margin_requirement_usd
            maintenance_margin_requirement_usd = (
                event.authoritative_maintenance_margin_requirement_usd
            )
            margin_event_id = event.event_id
            source_timestamp = event.occurred_at
    return BrokerAuthoritativeSnapshot(
        position_contracts=position_contracts,
        initial_margin_requirement_usd=initial_margin_requirement_usd,
        maintenance_margin_requirement_usd=maintenance_margin_requirement_usd,
        position_event_id=position_event_id,
        margin_event_id=margin_event_id,
        source_timestamp=source_timestamp,
    )


def _unresolved_discrepancy_ids(events: Iterable[LedgerEvent]) -> tuple[str, ...]:
    opened: list[str] = []
    resolved: set[str] = set()
    for event in events:
        if event.discrepancy_id is None:
            continue
        if event.event_class == LedgerEventClass.UNRESOLVED_DISCREPANCY:
            opened.append(event.discrepancy_id)
        if event.event_class in RECONCILING_EVENT_CLASSES:
            resolved.add(event.discrepancy_id)
    return tuple(discrepancy_id for discrepancy_id in opened if discrepancy_id not in resolved)


def _difference(
    metric: str,
    *,
    as_booked: Decimal | None,
    as_reconciled: Decimal | None,
    authoritative: Decimal | None,
    explanation: str,
) -> LedgerDifference:
    booked_vs_reconciled_delta = None
    reconciled_vs_authoritative_delta = None
    if as_booked is not None and as_reconciled is not None:
        booked_vs_reconciled_delta = as_reconciled - as_booked
    if as_reconciled is not None and authoritative is not None:
        reconciled_vs_authoritative_delta = as_reconciled - authoritative
    return LedgerDifference(
        metric=metric,
        as_booked=as_booked,
        as_reconciled=as_reconciled,
        authoritative=authoritative,
        booked_vs_reconciled_delta=booked_vs_reconciled_delta,
        reconciled_vs_authoritative_delta=reconciled_vs_authoritative_delta,
        explanation=explanation,
    )


def _build_differences(
    as_booked: LedgerTotals,
    as_reconciled: LedgerTotals,
    broker_snapshot: BrokerAuthoritativeSnapshot,
) -> tuple[LedgerDifference, ...]:
    return (
        _difference(
            "position_contracts",
            as_booked=as_booked.position_contracts,
            as_reconciled=as_reconciled.position_contracts,
            authoritative=broker_snapshot.position_contracts,
            explanation="Open-contract count must reconcile to the broker EOD position snapshot.",
        ),
        _difference(
            "cash_balance_usd",
            as_booked=as_booked.cash_balance_usd,
            as_reconciled=as_reconciled.cash_balance_usd,
            authoritative=None,
            explanation="Cash balance captures booked cash movements plus reconciliation or restatement deltas.",
        ),
        _difference(
            "realized_pnl_usd",
            as_booked=as_booked.realized_pnl_usd,
            as_reconciled=as_reconciled.realized_pnl_usd,
            authoritative=None,
            explanation="Realized P&L remains distinguishable from later reconciliation or restatement corrections.",
        ),
        _difference(
            "fee_total_usd",
            as_booked=as_booked.fee_total_usd,
            as_reconciled=as_reconciled.fee_total_usd,
            authoritative=None,
            explanation="Exchange or clearing fees remain explicit ledger lines instead of hiding in net P&L.",
        ),
        _difference(
            "commission_total_usd",
            as_booked=as_booked.commission_total_usd,
            as_reconciled=as_reconciled.commission_total_usd,
            authoritative=None,
            explanation="Commission restatements stay visible as booked-versus-reconciled deltas.",
        ),
        _difference(
            "broker_initial_margin_requirement_usd",
            as_booked=None,
            as_reconciled=None,
            authoritative=broker_snapshot.initial_margin_requirement_usd,
            explanation="Broker initial margin remains an authoritative reference snapshot, not a booked cash event.",
        ),
        _difference(
            "broker_maintenance_margin_requirement_usd",
            as_booked=None,
            as_reconciled=None,
            authoritative=broker_snapshot.maintenance_margin_requirement_usd,
            explanation="Broker maintenance margin remains an authoritative reference snapshot, not a booked cash event.",
        ),
    )


def _close_status(
    integrity: AppendOnlyIntegrityReport,
    broker_snapshot: BrokerAuthoritativeSnapshot,
    as_reconciled: LedgerTotals,
    unresolved_discrepancy_ids: tuple[str, ...],
) -> tuple[str, str, str]:
    if not integrity.valid:
        return (
            LedgerCloseStatus.VIOLATION.value,
            integrity.reason_code,
            integrity.explanation,
        )
    if not broker_snapshot.position_event_id or not broker_snapshot.margin_event_id:
        return (
            LedgerCloseStatus.REVIEW_REQUIRED.value,
            "LEDGER_BROKER_EOD_EVIDENCE_MISSING",
            "Ledger close requires both broker EOD position and broker EOD margin snapshots.",
        )
    if unresolved_discrepancy_ids:
        return (
            LedgerCloseStatus.REVIEW_REQUIRED.value,
            "LEDGER_UNRESOLVED_DISCREPANCY",
            "Ledger close remains review-required until every broker discrepancy is resolved.",
        )
    if (
        broker_snapshot.position_contracts is not None
        and as_reconciled.position_contracts != broker_snapshot.position_contracts
    ):
        return (
            LedgerCloseStatus.REVIEW_REQUIRED.value,
            "LEDGER_POSITION_NOT_RECONCILED",
            "Reconciled position does not match the authoritative broker EOD position.",
        )
    return (
        LedgerCloseStatus.PASS.value,
        "LEDGER_CLOSE_READY",
        "Ledger close is append-only, fully reconciled, and backed by broker EOD evidence.",
    )


def evaluate_accounting_ledger_close(
    close_id: str,
    account_id: str,
    symbol: str,
    events: Iterable[LedgerEvent],
) -> LedgerCloseArtifact:
    ordered_events = tuple(events)
    integrity = validate_append_only_ledger(
        ordered_events,
        account_id=account_id,
        symbol=symbol,
    )
    as_booked = _aggregate_totals(ordered_events, BOOKED_EVENT_CLASSES)
    as_reconciled = _aggregate_totals(
        ordered_events,
        BOOKED_EVENT_CLASSES | RECONCILING_EVENT_CLASSES,
    )
    broker_snapshot = _latest_broker_snapshot(ordered_events)
    unresolved_discrepancy_ids = _unresolved_discrepancy_ids(ordered_events)
    status, reason_code, explanation = _close_status(
        integrity,
        broker_snapshot,
        as_reconciled,
        unresolved_discrepancy_ids,
    )
    return LedgerCloseArtifact(
        close_id=close_id,
        account_id=account_id,
        symbol=symbol,
        status=status,
        reason_code=reason_code,
        append_only_integrity=integrity,
        event_classes_present=tuple(sorted({event.event_class.value for event in ordered_events})),
        trace_event_ids=tuple(event.event_id for event in ordered_events),
        as_booked_totals=as_booked,
        as_reconciled_totals=as_reconciled,
        broker_authoritative_snapshot=broker_snapshot,
        differences=_build_differences(as_booked, as_reconciled, broker_snapshot),
        unresolved_discrepancy_ids=unresolved_discrepancy_ids,
        restatement_event_ids=tuple(
            event.event_id
            for event in ordered_events
            if event.event_class == LedgerEventClass.RESTATEMENT
        ),
        explanation=explanation,
    )
