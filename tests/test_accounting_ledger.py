import unittest
from decimal import Decimal

from shared.policy.accounting_ledger import (
    LedgerCloseArtifact,
    LedgerCloseStatus,
    LedgerEvent,
    LedgerEventClass,
    evaluate_accounting_ledger_close,
    ledger_event_class_ids,
    validate_append_only_ledger,
)


def ledger_event(
    sequence_id: int,
    event_id: str,
    event_class: LedgerEventClass,
    **overrides: object,
) -> LedgerEvent:
    payload: dict[str, object] = {
        "sequence_id": sequence_id,
        "event_id": event_id,
        "event_class": event_class,
        "account_id": "acct_live_oneoz",
        "symbol": "1OZ",
        "occurred_at": f"2026-03-12T00:{sequence_id:02d}:00+00:00",
        "description": event_id,
    }
    payload.update(overrides)
    return LedgerEvent(**payload)


class LedgerCatalogTests(unittest.TestCase):
    def test_event_classes_match_plan_contract(self) -> None:
        self.assertEqual(
            (
                "booked_fill",
                "booked_fee",
                "booked_commission",
                "booked_cash_movement",
                "broker_eod_position",
                "broker_eod_margin_snapshot",
                "reconciliation_adjustment",
                "restatement",
                "unresolved_discrepancy",
            ),
            ledger_event_class_ids(),
        )


class AppendOnlyLedgerTests(unittest.TestCase):
    def test_append_only_validator_rejects_duplicate_event_ids(self) -> None:
        report = validate_append_only_ledger(
            (
                ledger_event(1, "evt_dup", LedgerEventClass.BOOKED_FILL),
                ledger_event(2, "evt_dup", LedgerEventClass.BOOKED_FEE),
            ),
            account_id="acct_live_oneoz",
            symbol="1OZ",
        )
        self.assertFalse(report.valid)
        self.assertEqual("LEDGER_EVENT_ID_DUPLICATE", report.reason_code)
        self.assertEqual("evt_dup", report.duplicate_event_id)

    def test_append_only_validator_rejects_non_monotonic_sequence(self) -> None:
        report = validate_append_only_ledger(
            (
                ledger_event(2, "evt_002", LedgerEventClass.BOOKED_FILL),
                ledger_event(1, "evt_001", LedgerEventClass.BOOKED_FEE),
            ),
            account_id="acct_live_oneoz",
            symbol="1OZ",
        )
        self.assertFalse(report.valid)
        self.assertEqual("LEDGER_SEQUENCE_OUT_OF_ORDER", report.reason_code)
        self.assertEqual(1, report.violating_sequence_id)

    def test_integrity_report_loader_rejects_truthy_flags(self) -> None:
        report = validate_append_only_ledger(
            (ledger_event(1, "evt_ok", LedgerEventClass.BOOKED_FILL),),
            account_id="acct_live_oneoz",
            symbol="1OZ",
        )
        payload = report.to_dict()
        payload["valid"] = "true"
        with self.assertRaisesRegex(ValueError, "valid must be a boolean"):
            type(report).from_dict(payload)

    def test_integrity_report_loader_rejects_boolean_sequence_id(self) -> None:
        report = validate_append_only_ledger(
            (
                ledger_event(2, "evt_002", LedgerEventClass.BOOKED_FILL),
                ledger_event(1, "evt_001", LedgerEventClass.BOOKED_FEE),
            ),
            account_id="acct_live_oneoz",
            symbol="1OZ",
        )
        payload = report.to_dict()
        payload["violating_sequence_id"] = True
        with self.assertRaisesRegex(ValueError, "violating_sequence_id must be an integer"):
            type(report).from_dict(payload)


class LedgerCloseTests(unittest.TestCase):
    def test_close_distinguishes_as_booked_from_as_reconciled(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_001",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_commission",
                    LedgerEventClass.BOOKED_COMMISSION,
                    cash_delta_usd=Decimal("-1.105"),
                    commission_delta_usd=Decimal("1.105"),
                ),
                ledger_event(
                    3,
                    "evt_cash",
                    LedgerEventClass.BOOKED_CASH_MOVEMENT,
                    cash_delta_usd=Decimal("12.345"),
                    realized_pnl_delta_usd=Decimal("12.345"),
                ),
                ledger_event(
                    4,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    5,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
                ledger_event(
                    6,
                    "evt_discrepancy",
                    LedgerEventClass.UNRESOLVED_DISCREPANCY,
                    discrepancy_id="disc_001",
                ),
                ledger_event(
                    7,
                    "evt_adjustment",
                    LedgerEventClass.RECONCILIATION_ADJUSTMENT,
                    discrepancy_id="disc_001",
                    cash_delta_usd=Decimal("-0.010"),
                    commission_delta_usd=Decimal("0.010"),
                ),
                ledger_event(
                    8,
                    "evt_restatement",
                    LedgerEventClass.RESTATEMENT,
                    discrepancy_id="disc_001",
                    cash_delta_usd=Decimal("0.005"),
                    realized_pnl_delta_usd=Decimal("0.005"),
                ),
            ),
        )

        self.assertEqual(LedgerCloseStatus.PASS.value, artifact.status)
        self.assertEqual("LEDGER_CLOSE_READY", artifact.reason_code)
        self.assertEqual(Decimal("11.240"), artifact.as_booked_totals.cash_balance_usd)
        self.assertEqual(Decimal("11.235"), artifact.as_reconciled_totals.cash_balance_usd)
        self.assertEqual(
            Decimal("0.010"),
            next(
                difference.booked_vs_reconciled_delta
                for difference in artifact.differences
                if difference.metric == "commission_total_usd"
            ),
        )
        self.assertEqual((), artifact.unresolved_discrepancy_ids)

    def test_decimal_precision_survives_rounding_boundaries(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_precision",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_fee_a",
                    LedgerEventClass.BOOKED_FEE,
                    cash_delta_usd=Decimal("-0.105"),
                    fee_delta_usd=Decimal("0.105"),
                ),
                ledger_event(
                    3,
                    "evt_fee_b",
                    LedgerEventClass.BOOKED_FEE,
                    cash_delta_usd=Decimal("-0.205"),
                    fee_delta_usd=Decimal("0.205"),
                ),
                ledger_event(
                    4,
                    "evt_cash",
                    LedgerEventClass.BOOKED_CASH_MOVEMENT,
                    cash_delta_usd=Decimal("0.310"),
                    realized_pnl_delta_usd=Decimal("0.310"),
                ),
                ledger_event(
                    5,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    6,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
            ),
        )

        self.assertEqual(LedgerCloseStatus.PASS.value, artifact.status)
        self.assertEqual(Decimal("0.000"), artifact.as_booked_totals.cash_balance_usd)
        self.assertEqual(Decimal("0.310"), artifact.as_booked_totals.realized_pnl_usd)
        self.assertEqual(Decimal("0.310"), artifact.as_booked_totals.fee_total_usd)

    def test_close_artifact_round_trip_preserves_decimal_fields(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_roundtrip",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    3,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
            ),
        )

        parsed = LedgerCloseArtifact.from_json(artifact.to_json())
        self.assertEqual(artifact, parsed)
        serialized = artifact.to_dict()
        self.assertEqual("1400.000", serialized["broker_authoritative_snapshot"]["initial_margin_requirement_usd"])

    def test_ledger_event_loader_requires_explicit_integer_schema_version(self) -> None:
        payload = ledger_event(1, "evt_schema", LedgerEventClass.BOOKED_FILL).to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "ledger_event: schema_version must be an integer"):
            LedgerEvent.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "ledger_event: schema_version must be an integer"):
            LedgerEvent.from_dict(payload_with_bool_schema)

    def test_ledger_event_loader_rejects_boolean_sequence_id(self) -> None:
        payload = ledger_event(1, "evt_sequence", LedgerEventClass.BOOKED_FILL).to_dict()
        payload["sequence_id"] = False
        with self.assertRaisesRegex(ValueError, "sequence_id must be an integer"):
            LedgerEvent.from_dict(payload)

    def test_ledger_event_loader_rejects_naive_occurred_at(self) -> None:
        payload = ledger_event(1, "evt_time", LedgerEventClass.BOOKED_FILL).to_dict()
        payload["occurred_at"] = "2026-03-12T00:01:00"
        with self.assertRaisesRegex(
            ValueError,
            "occurred_at must be a timezone-aware ISO-8601 timestamp",
        ):
            LedgerEvent.from_dict(payload)

    def test_close_artifact_loader_requires_explicit_integer_schema_version(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_schema",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    3,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
            ),
        )
        payload = artifact.to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "ledger_close_artifact: schema_version must be an integer",
        ):
            LedgerCloseArtifact.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(
            ValueError,
            "ledger_close_artifact: schema_version must be an integer",
        ):
            LedgerCloseArtifact.from_dict(payload_with_bool_schema)

    def test_close_artifact_loader_rejects_invalid_status(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_status",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    3,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
            ),
        )
        payload = artifact.to_dict()
        payload["status"] = "done"
        with self.assertRaisesRegex(
            ValueError,
            "status must be a valid ledger close status",
        ):
            LedgerCloseArtifact.from_dict(payload)

    def test_close_artifact_loader_rejects_naive_timestamps(self) -> None:
        artifact = evaluate_accounting_ledger_close(
            "ledger_close_timestamp",
            "acct_live_oneoz",
            "1OZ",
            (
                ledger_event(
                    1,
                    "evt_fill",
                    LedgerEventClass.BOOKED_FILL,
                    position_delta_contracts=Decimal("1"),
                ),
                ledger_event(
                    2,
                    "evt_position",
                    LedgerEventClass.BROKER_EOD_POSITION,
                    authoritative_position_contracts=Decimal("1"),
                ),
                ledger_event(
                    3,
                    "evt_margin",
                    LedgerEventClass.BROKER_EOD_MARGIN_SNAPSHOT,
                    authoritative_initial_margin_requirement_usd=Decimal("1400.000"),
                    authoritative_maintenance_margin_requirement_usd=Decimal("1275.000"),
                ),
            ),
        )
        payload = artifact.to_dict()
        payload["timestamp"] = "2026-03-12T00:03:00"
        with self.assertRaisesRegex(
            ValueError,
            "timestamp must be a timezone-aware ISO-8601 timestamp",
        ):
            LedgerCloseArtifact.from_dict(payload)

        payload = artifact.to_dict()
        payload["broker_authoritative_snapshot"]["source_timestamp"] = "2026-03-12T00:03:00"
        with self.assertRaisesRegex(
            ValueError,
            "source_timestamp must be a timezone-aware ISO-8601 timestamp",
        ):
            LedgerCloseArtifact.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
