from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.bar_parity import (
    VALIDATION_ERRORS,
    BarParityCertificationRequest,
    BarParityCertificationReport,
    BarParityDimensionID,
    BarParityStatus,
    check_anchor_timing,
    check_bar_availability_timing,
    check_event_window_labeling,
    check_ohlcv_construction,
    check_session_boundaries,
    evaluate_databento_ibkr_bar_parity,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "bar_parity_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"bar parity fixture failed to load: {exc}") from exc


def build_dimension(payload: dict[str, object]):
    kind = payload["kind"]
    if kind == "session_boundaries":
        return check_session_boundaries(
            boundary_alignment_ratio=float(payload["boundary_alignment_ratio"]),
            min_boundary_alignment_ratio=float(payload["min_boundary_alignment_ratio"]),
            boundary_mismatch_count=int(payload["boundary_mismatch_count"]),
            max_boundary_mismatch_count=int(payload["max_boundary_mismatch_count"]),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "ohlcv_construction":
        return check_ohlcv_construction(
            ohlc_diff_ticks=int(payload["ohlc_diff_ticks"]),
            max_allowed_ohlc_diff_ticks=int(payload["max_allowed_ohlc_diff_ticks"]),
            volume_diff_ratio=float(payload["volume_diff_ratio"]),
            max_allowed_volume_diff_ratio=float(
                payload["max_allowed_volume_diff_ratio"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "anchor_timing":
        return check_anchor_timing(
            max_anchor_drift_seconds=float(payload["max_anchor_drift_seconds"]),
            max_allowed_anchor_drift_seconds=float(
                payload["max_allowed_anchor_drift_seconds"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "event_window_labeling":
        return check_event_window_labeling(
            mislabeled_window_count=int(payload["mislabeled_window_count"]),
            max_allowed_mislabeled_window_count=int(
                payload["max_allowed_mislabeled_window_count"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    if kind == "bar_availability_timing":
        return check_bar_availability_timing(
            max_availability_lag_seconds=float(payload["max_availability_lag_seconds"]),
            max_allowed_availability_lag_seconds=float(
                payload["max_allowed_availability_lag_seconds"]
            ),
            research_artifact_reference=str(payload["research_artifact_reference"]),
            live_artifact_reference=str(payload["live_artifact_reference"]),
        )
    raise AssertionError(f"unexpected bar parity dimension kind: {kind}")


def build_request(payload: dict[str, object]) -> BarParityCertificationRequest:
    return BarParityCertificationRequest(
        case_id=str(payload["case_id"]),
        data_profile_release_id=str(payload["data_profile_release_id"]),
        approved_bar_construction_semantics_id=str(
            payload["approved_bar_construction_semantics_id"]
        ),
        research_feed=str(payload["research_feed"]),
        live_feed=str(payload["live_feed"]),
        certified_at_utc=str(payload["certified_at_utc"]),
        freshness_expires_at_utc=str(payload["freshness_expires_at_utc"]),
        evaluation_time_utc=str(payload["evaluation_time_utc"]),
        parity_expectations=tuple(str(item) for item in payload["parity_expectations"]),
        mismatch_histogram_artifact_ids=tuple(
            str(item) for item in payload["mismatch_histogram_artifact_ids"]
        ),
        sampled_drilldown_artifact_ids=tuple(
            str(item) for item in payload["sampled_drilldown_artifact_ids"]
        ),
        dimensions=tuple(
            build_dimension(dimension_payload)
            for dimension_payload in payload["dimensions"]
        ),
    )


class BarParityContractTests(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_payload(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][0])
        self.assertEqual(request, BarParityCertificationRequest.from_json(request.to_json()))

    def test_report_round_trip_preserves_payload(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][0])
        report = evaluate_databento_ibkr_bar_parity(request)
        self.assertEqual(report, BarParityCertificationReport.from_json(report.to_json()))

    def test_dimension_checks_cover_all_required_ids(self) -> None:
        checks = (
            check_session_boundaries(
                boundary_alignment_ratio=0.999,
                min_boundary_alignment_ratio=0.995,
                boundary_mismatch_count=0,
                max_boundary_mismatch_count=1,
                research_artifact_reference="artifact://research/session",
                live_artifact_reference="artifact://live/session",
            ),
            check_ohlcv_construction(
                ohlc_diff_ticks=0,
                max_allowed_ohlc_diff_ticks=1,
                volume_diff_ratio=0.001,
                max_allowed_volume_diff_ratio=0.01,
                research_artifact_reference="artifact://research/ohlcv",
                live_artifact_reference="artifact://live/ohlcv",
            ),
            check_anchor_timing(
                max_anchor_drift_seconds=0.2,
                max_allowed_anchor_drift_seconds=1.0,
                research_artifact_reference="artifact://research/anchor",
                live_artifact_reference="artifact://live/anchor",
            ),
            check_event_window_labeling(
                mislabeled_window_count=0,
                max_allowed_mislabeled_window_count=0,
                research_artifact_reference="artifact://research/window",
                live_artifact_reference="artifact://live/window",
            ),
            check_bar_availability_timing(
                max_availability_lag_seconds=0.5,
                max_allowed_availability_lag_seconds=1.0,
                research_artifact_reference="artifact://research/availability",
                live_artifact_reference="artifact://live/availability",
            ),
        )

        self.assertEqual(
            {dimension.value for dimension in BarParityDimensionID},
            {check.dimension_id for check in checks},
        )
        self.assertTrue(all(check.passed for check in checks))

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["bar_parity_cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = build_request(case)
                report = evaluate_databento_ibkr_bar_parity(request)

                self.assertEqual(case["expected"]["status"], report.status)
                self.assertEqual(case["expected"]["reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected"]["freshness_valid"],
                    report.freshness_valid,
                )
                self.assertEqual(
                    case["expected"]["parity_passed"],
                    report.parity_passed,
                )

    def test_incomplete_dimension_set_is_rejected(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][0])
        invalid_request = BarParityCertificationRequest(
            case_id=request.case_id,
            data_profile_release_id=request.data_profile_release_id,
            approved_bar_construction_semantics_id=request.approved_bar_construction_semantics_id,
            research_feed=request.research_feed,
            live_feed=request.live_feed,
            certified_at_utc=request.certified_at_utc,
            freshness_expires_at_utc=request.freshness_expires_at_utc,
            evaluation_time_utc=request.evaluation_time_utc,
            parity_expectations=request.parity_expectations,
            mismatch_histogram_artifact_ids=request.mismatch_histogram_artifact_ids,
            sampled_drilldown_artifact_ids=request.sampled_drilldown_artifact_ids,
            dimensions=request.dimensions + (request.dimensions[0],),
        )

        report = evaluate_databento_ibkr_bar_parity(invalid_request)

        self.assertEqual(BarParityStatus.INVALID.value, report.status)
        self.assertEqual("BAR_PARITY_DIMENSIONS_INCOMPLETE", report.reason_code)
        self.assertIn("Duplicates:", report.explanation)

    def test_report_is_structured_and_operator_readable(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][1])
        report = evaluate_databento_ibkr_bar_parity(request)
        payload = report.to_dict()

        self.assertTrue(
            {
                "case_id",
                "data_profile_release_id",
                "status",
                "reason_code",
                "artifact_id",
                "freshness_valid",
                "parity_passed",
                "drifted_dimensions",
                "mismatch_histogram_artifact_ids",
                "sampled_drilldown_artifact_ids",
                "compared_dimensions",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertEqual(BarParityStatus.VIOLATION.value, report.status)
        self.assertIn("semantic dimensions", report.explanation.lower())
        self.assertEqual(
            ["session_boundaries", "ohlcv_construction", "event_window_labeling"],
            list(report.drifted_dimensions),
        )

    def test_dimension_loader_rejects_truthy_boolean_and_naive_timestamp(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][0])
        dimension_payload = request.dimensions[0].to_dict()

        payload_with_truthy_bool = dict(dimension_payload)
        payload_with_truthy_bool["passed"] = "true"
        with self.assertRaisesRegex(ValueError, "passed must be a boolean"):
            type(request.dimensions[0]).from_dict(payload_with_truthy_bool)

        payload_with_naive_timestamp = dict(dimension_payload)
        payload_with_naive_timestamp["timestamp"] = "2026-03-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "timestamp must be timezone-aware"):
            type(request.dimensions[0]).from_dict(payload_with_naive_timestamp)

        payload_without_timestamp = dict(dimension_payload)
        payload_without_timestamp.pop("timestamp")
        with self.assertRaises(KeyError):
            type(request.dimensions[0]).from_dict(payload_without_timestamp)

    def test_request_loader_requires_explicit_integer_schema_version_and_aware_times(self) -> None:
        payload = build_request(load_cases()["bar_parity_cases"][0]).to_dict()

        payload_without_schema = dict(payload)
        payload_without_schema.pop("schema_version")
        with self.assertRaisesRegex(
            ValueError,
            "bar_parity_request: schema_version must be an integer",
        ):
            BarParityCertificationRequest.from_dict(payload_without_schema)

        payload_with_bool_schema = dict(payload)
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(
            ValueError,
            "bar_parity_request: schema_version must be an integer",
        ):
            BarParityCertificationRequest.from_dict(payload_with_bool_schema)

        payload_with_naive_time = dict(payload)
        payload_with_naive_time["evaluation_time_utc"] = "2026-03-02T00:00:00"
        with self.assertRaisesRegex(ValueError, "evaluation_time_utc must be timezone-aware"):
            BarParityCertificationRequest.from_dict(payload_with_naive_time)

    def test_report_loader_rejects_truthy_flags_and_naive_timestamp(self) -> None:
        request = build_request(load_cases()["bar_parity_cases"][0])
        report = evaluate_databento_ibkr_bar_parity(request)
        payload = report.to_dict()

        payload_with_truthy_flag = dict(payload)
        payload_with_truthy_flag["freshness_valid"] = "false"
        with self.assertRaisesRegex(ValueError, "freshness_valid must be a boolean"):
            BarParityCertificationReport.from_dict(payload_with_truthy_flag)

        payload_with_truthy_parity = dict(payload)
        payload_with_truthy_parity["parity_passed"] = 1
        with self.assertRaisesRegex(ValueError, "parity_passed must be a boolean"):
            BarParityCertificationReport.from_dict(payload_with_truthy_parity)

        payload_with_naive_timestamp = dict(payload)
        payload_with_naive_timestamp["timestamp"] = "2026-03-02T00:00:00"
        with self.assertRaisesRegex(ValueError, "timestamp must be timezone-aware"):
            BarParityCertificationReport.from_dict(payload_with_naive_timestamp)

        payload_with_invalid_status = dict(payload)
        payload_with_invalid_status["status"] = "done"
        with self.assertRaisesRegex(
            ValueError,
            "status must be a valid bar parity status",
        ):
            BarParityCertificationReport.from_dict(payload_with_invalid_status)

        payload_without_timestamp = dict(payload)
        payload_without_timestamp.pop("timestamp")
        with self.assertRaises(KeyError):
            BarParityCertificationReport.from_dict(payload_without_timestamp)


if __name__ == "__main__":
    unittest.main()
