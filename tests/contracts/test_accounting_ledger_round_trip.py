from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.accounting_ledger import (
    LedgerCloseArtifact,
    LedgerEvent,
    evaluate_accounting_ledger_close,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "fixtures"
    / "policy"
    / "accounting_ledger_round_trip.json"
)


def load_cases() -> list[dict[str, object]]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)["stage_cases"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"accounting ledger fixture failed to load: {exc}") from exc


def build_events(payload: list[dict[str, object]]) -> tuple[LedgerEvent, ...]:
    return tuple(LedgerEvent.from_dict(item) for item in payload)


def difference_index(report: LedgerCloseArtifact) -> dict[str, dict[str, object]]:
    return {item.metric: item.to_dict() for item in report.differences}


class AccountingLedgerFixtureContractTests(unittest.TestCase):
    def test_fixture_stages_cover_initial_booking_through_restatement(self) -> None:
        expected_stage_ids = {
            "initial_booked_close",
            "open_discrepancy_requires_review",
            "restated_close_is_explicitly_reconciled",
        }
        self.assertEqual(expected_stage_ids, {item["case_id"] for item in load_cases()})

    def test_stage_cases_emit_expected_close_reports(self) -> None:
        for payload in load_cases():
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_accounting_ledger_close(
                    str(payload["close_id"]),
                    str(payload["account_id"]),
                    str(payload["symbol"]),
                    build_events(payload["events"]),
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected_unresolved_discrepancy_ids"]),
                    report.unresolved_discrepancy_ids,
                )
                self.assertEqual(
                    tuple(payload["expected_trace_event_ids"]),
                    report.trace_event_ids,
                )
                self.assertEqual(
                    payload["expected_as_booked_totals"],
                    report.as_booked_totals.to_dict(),
                )
                self.assertEqual(
                    payload["expected_as_reconciled_totals"],
                    report.as_reconciled_totals.to_dict(),
                )

                indexed_differences = difference_index(report)
                for metric, expected in payload["expected_differences"].items():
                    for key, value in expected.items():
                        self.assertEqual(value, indexed_differences[metric][key])

    def test_round_trip_close_artifact_remains_stable_for_fixture_cases(self) -> None:
        for payload in load_cases():
            with self.subTest(case_id=payload["case_id"]):
                report = evaluate_accounting_ledger_close(
                    str(payload["close_id"]),
                    str(payload["account_id"]),
                    str(payload["symbol"]),
                    build_events(payload["events"]),
                )
                self.assertEqual(report, LedgerCloseArtifact.from_json(report.to_json()))


if __name__ == "__main__":
    unittest.main()
