import datetime
import json
import unittest
from pathlib import Path

from shared.policy.clock_discipline import (
    ClockAction,
    CompiledSessionBoundary,
    DEFAULT_TIME_DISCIPLINE_POLICY,
    SynchronizationState,
    VALIDATION_ERRORS,
    canonicalize_persisted_timestamp,
    evaluate_clock_skew,
    resolve_session_boundary,
    validate_compiled_session_boundaries,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "clock_discipline_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - fixture bootstrap
        raise AssertionError(f"clock discipline fixture failed to load: {exc}") from exc


class ClockDisciplineContractTest(unittest.TestCase):
    def test_clock_policy_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_utc_persistence_and_monotonic_defaults_are_explicit(self) -> None:
        policy = DEFAULT_TIME_DISCIPLINE_POLICY
        self.assertEqual("3.5", policy.plan_section)
        self.assertEqual("UTC", policy.persisted_timestamp_timezone)
        self.assertEqual("compiled_exchange_calendars", policy.exchange_calendar_source)
        self.assertEqual("resolved_context_bundles", policy.session_boundary_source)
        self.assertEqual(
            "durable_sequence_numbers_and_monotonic_clocks",
            policy.ordering_basis,
        )
        self.assertTrue(policy.durable_sequence_numbers_required)
        self.assertTrue(policy.monotonic_clocks_required)
        self.assertEqual("chrony_or_ntp_equivalent", policy.synchronization_service)
        self.assertTrue(policy.sync_health_visible_to_policy)
        self.assertTrue(policy.sync_health_visible_to_observability)

    def test_persisted_timestamps_are_normalized_to_utc(self) -> None:
        eastern = datetime.timezone(datetime.timedelta(hours=-4))
        persisted = canonicalize_persisted_timestamp(
            datetime.datetime(2026, 3, 9, 9, 30, tzinfo=eastern)
        )
        self.assertEqual(datetime.timezone.utc, persisted.tzinfo)
        self.assertEqual("2026-03-09T13:30:00+00:00", persisted.isoformat())

    def test_naive_timestamps_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_persisted_timestamp(datetime.datetime(2026, 3, 9, 9, 30))

    def test_compiled_boundaries_validate_and_match_expected_timestamps(self) -> None:
        session_boundaries = tuple(
            CompiledSessionBoundary(**payload)
            for payload in load_cases()["session_boundaries"]
        )
        self.assertEqual([], validate_compiled_session_boundaries(session_boundaries))

        for payload in load_cases()["session_boundaries"]:
            with self.subTest(case_id=payload["case_id"]):
                resolution = resolve_session_boundary(
                    session_boundaries,
                    venue=payload["venue"],
                    trading_day=payload["trading_day"],
                    session_name=payload["session_name"],
                )
                self.assertEqual(payload["calendar_id"], resolution.calendar_id)
                self.assertEqual(payload["context_bundle_id"], resolution.context_bundle_id)
                self.assertEqual("compiled_exchange_calendars", resolution.source)
                self.assertEqual(payload["utc_start"], resolution.utc_start)
                self.assertEqual(payload["utc_end"], resolution.utc_end)
                self.assertEqual(payload["exchange_local_start"], resolution.exchange_local_start)
                self.assertEqual(payload["exchange_local_end"], resolution.exchange_local_end)
                self.assertEqual(
                    0,
                    int(
                        (
                            datetime.datetime.fromisoformat(resolution.utc_start)
                            - datetime.datetime.fromisoformat(payload["utc_start"])
                        ).total_seconds()
                    ),
                )
                self.assertEqual(
                    0,
                    int(
                        (
                            datetime.datetime.fromisoformat(resolution.utc_end)
                            - datetime.datetime.fromisoformat(payload["utc_end"])
                        ).total_seconds()
                    ),
                )

    def test_skew_policy_enforces_warn_restrict_and_block_thresholds(self) -> None:
        required_fields = {
            "status",
            "reason_code",
            "synchronization_state",
            "measured_skew_ms",
            "configured_threshold_ms",
            "corrective_action",
            "explanation",
            "timestamp",
        }

        for payload in load_cases()["skew_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                diagnostic = evaluate_clock_skew(
                    payload["measured_skew_ms"],
                    SynchronizationState(payload["sync_state"]),
                )
                self.assertEqual(payload["expected_action"], diagnostic.status)
                self.assertEqual(payload["expected_reason_code"], diagnostic.reason_code)
                self.assertEqual(
                    payload["expected_threshold_ms"],
                    diagnostic.configured_threshold_ms,
                )
                self.assertIn(
                    payload["expected_corrective_phrase"],
                    diagnostic.corrective_action.lower(),
                )
                self.assertTrue(required_fields.issubset(diagnostic.to_dict().keys()))

    def test_clock_actions_cover_full_escalation_ladder(self) -> None:
        actions = {payload["expected_action"] for payload in load_cases()["skew_cases"]}
        self.assertEqual(
            {
                ClockAction.PASS.value,
                ClockAction.WARN.value,
                ClockAction.RESTRICT.value,
                ClockAction.BLOCK.value,
            },
            actions,
        )


if __name__ == "__main__":
    unittest.main()
