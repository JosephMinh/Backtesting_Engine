import json
import unittest
from pathlib import Path

from shared.policy.release_schemas import (
    AnalyticRelease,
    DataProfileRelease,
    DatasetRelease,
    ReleaseLifecycleState,
    ReleaseStatus,
    VALIDATION_ERRORS,
    PromotableSurfaceBindingRequest,
    evaluate_release_compatibility,
    release_definitions_by_kind,
    validate_analytic_release,
    validate_data_profile_release,
    validate_dataset_release,
    validate_promotable_surface_binding,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "release_schemas.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, KeyError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"release schema fixture failed to load: {exc}") from exc


def build_release(release_kind: str, payload: dict[str, object]):
    if release_kind == "dataset_release":
        return DatasetRelease.from_dict(payload)
    if release_kind == "analytic_release":
        return AnalyticRelease.from_dict(payload)
    if release_kind == "data_profile_release":
        return DataProfileRelease.from_dict(payload)
    raise AssertionError(f"unexpected release kind in fixture: {release_kind}")


def validate_release(case_id: str, release_kind: str, release):
    if release_kind == "dataset_release":
        return validate_dataset_release(case_id, release)
    if release_kind == "analytic_release":
        return validate_analytic_release(case_id, release)
    if release_kind == "data_profile_release":
        return validate_data_profile_release(case_id, release)
    raise AssertionError(f"unexpected release kind in fixture: {release_kind}")


class ReleaseSchemaContractTest(unittest.TestCase):
    def test_release_catalog_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_release_catalog_defines_three_explicit_release_kinds(self) -> None:
        self.assertEqual(
            {"dataset_release", "analytic_release", "data_profile_release"},
            set(release_definitions_by_kind()),
        )

    def test_release_fixture_publication_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["publication_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                release = build_release(payload["release_kind"], payload["payload"])
                report = validate_release(
                    payload["case_id"],
                    payload["release_kind"],
                    release,
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_round_trip_serialization_preserves_release_payloads(self) -> None:
        dataset_release = DatasetRelease(
            release_id="dataset_release_roundtrip_v1",
            raw_input_hashes=("raw_sha256_a", "raw_sha256_b"),
            reference_version_hashes=("calendar_sha256_v3",),
            observation_cutoff_utc="2026-03-01T00:00:00+00:00",
            validation_rules_version="validation_rules_v7",
            catalog_version="catalog_v4",
            protocol_versions={"ingestion_protocol": "ingest_v2"},
            vendor_revision_watermark="databento_revision_2026-03-01",
            correction_horizon="t_plus_2_business_days",
            certification_report_hash="cert_report_sha256_001",
            policy_bundle_hash="policy_bundle_sha256_001",
            lifecycle_state=ReleaseLifecycleState.APPROVED,
        )
        analytic_release = AnalyticRelease(
            release_id="analytic_release_roundtrip_v1",
            dataset_release_id="dataset_release_roundtrip_v1",
            feature_version="feature_defs_v9",
            analytic_series_version="analytic_series_v3",
            feature_block_manifests=("manifest://feature_block/core_v9",),
            feature_availability_contracts=("availability://gold/core_v9",),
            slice_manifests=("slice://training_2026q1",),
            artifact_root_hash="artifact_root_sha256_001",
            lifecycle_state=ReleaseLifecycleState.PUBLISHED,
        )
        data_profile_release = DataProfileRelease(
            release_id="ibkr_1oz_comex_bars_1m_roundtrip_v1",
            source_feeds=("ibkr_historical_bars", "ibkr_live_bars"),
            venue_dataset_ids=("ibkr:comex:1oz:bars:1m",),
            schema_selection_rules=("prefer_ibkr_trade_bar_schema_v2",),
            timestamp_precedence_rule="exchange_end_timestamp_then_vendor_arrival",
            bar_construction_rules=("one_minute_session_anchored_bars",),
            session_anchor_rule="comex_metals_globex_v1",
            trade_quote_precedence_rule="trade_first_then_quote_fallback",
            zero_volume_bar_policy="emit_with_explicit_zero_volume_flag",
            late_print_policy="quarantine_for_recertification_review",
            correction_policy="apply_vendor_corrections_via_delta_release",
            gap_policy="preserve_gaps_explicitly",
            forward_fill_policy="never_forward_fill_prices",
            symbology_mapping_rules=("bind_to_resolved_context_bundle_symbology_v4",),
            live_historical_parity_expectations=("same_session_anchor_and_close_rule",),
            lifecycle_state=ReleaseLifecycleState.APPROVED,
        )

        self.assertEqual(dataset_release, DatasetRelease.from_json(dataset_release.to_json()))
        self.assertEqual(analytic_release, AnalyticRelease.from_json(analytic_release.to_json()))
        self.assertEqual(
            data_profile_release,
            DataProfileRelease.from_json(data_profile_release.to_json()),
        )

    def test_compatibility_report_rejects_unknown_schema_version(self) -> None:
        report = evaluate_release_compatibility(
            "analytic_release",
            {
                "release_id": "analytic_release_unknown_version_v2",
                "schema_version": 2,
            },
        )
        self.assertEqual(ReleaseStatus.INCOMPATIBLE.value, report.status)
        self.assertFalse(report.compatible)
        self.assertEqual("RELEASE_SCHEMA_VERSION_UNSUPPORTED", report.reason_code)

    def test_compatibility_report_rejects_boolean_schema_version(self) -> None:
        report = evaluate_release_compatibility(
            "analytic_release",
            {
                "release_id": "analytic_release_boolean_version_v1",
                "schema_version": True,
            },
        )
        self.assertEqual(ReleaseStatus.INVALID.value, report.status)
        self.assertFalse(report.compatible)
        self.assertEqual("RELEASE_SCHEMA_VERSION_MISSING", report.reason_code)

    def test_dataset_release_normalizes_observation_cutoff_to_utc(self) -> None:
        release = DatasetRelease(
            release_id="dataset_release_cutoff_normalized_v1",
            raw_input_hashes=("raw_sha256_a",),
            reference_version_hashes=("calendar_sha256_v3",),
            observation_cutoff_utc="2026-03-01T01:00:00+01:00",
            validation_rules_version="validation_rules_v7",
            catalog_version="catalog_v4",
            protocol_versions={"ingestion_protocol": "ingest_v2"},
            vendor_revision_watermark="databento_revision_2026-03-01",
            correction_horizon="t_plus_2_business_days",
            certification_report_hash="cert_report_sha256_001",
            policy_bundle_hash="policy_bundle_sha256_001",
            lifecycle_state=ReleaseLifecycleState.APPROVED,
        )
        self.assertEqual("2026-03-01T00:00:00+00:00", release.observation_cutoff_utc)

    def test_release_loaders_require_explicit_integer_schema_version(self) -> None:
        for release_kind, payload in (
            (
                "dataset_release",
                {
                    "release_id": "dataset_release_missing_schema_v1",
                    "raw_input_hashes": ["raw_sha256_a"],
                    "reference_version_hashes": ["calendar_sha256_v3"],
                    "observation_cutoff_utc": "2026-03-01T00:00:00+00:00",
                    "validation_rules_version": "validation_rules_v7",
                    "catalog_version": "catalog_v4",
                    "protocol_versions": {"ingestion_protocol": "ingest_v2"},
                    "vendor_revision_watermark": "databento_revision_2026-03-01",
                    "correction_horizon": "t_plus_2_business_days",
                    "certification_report_hash": "cert_report_sha256_001",
                    "policy_bundle_hash": "policy_bundle_sha256_001",
                    "lifecycle_state": "approved",
                },
            ),
            (
                "analytic_release",
                {
                    "release_id": "analytic_release_missing_schema_v1",
                    "dataset_release_id": "dataset_release_roundtrip_v1",
                    "feature_version": "feature_defs_v9",
                    "analytic_series_version": "analytic_series_v3",
                    "feature_block_manifests": ["manifest://feature_block/core_v9"],
                    "feature_availability_contracts": ["availability://gold/core_v9"],
                    "slice_manifests": [],
                    "artifact_root_hash": "artifact_root_sha256_001",
                    "lifecycle_state": "published",
                },
            ),
            (
                "data_profile_release",
                {
                    "release_id": "ibkr_1oz_comex_bars_1m_missing_schema_v1",
                    "source_feeds": ["ibkr_historical_bars", "ibkr_live_bars"],
                    "venue_dataset_ids": ["ibkr:comex:1oz:bars:1m"],
                    "schema_selection_rules": ["prefer_ibkr_trade_bar_schema_v2"],
                    "timestamp_precedence_rule": "exchange_end_timestamp_then_vendor_arrival",
                    "bar_construction_rules": ["one_minute_session_anchored_bars"],
                    "session_anchor_rule": "comex_metals_globex_v1",
                    "trade_quote_precedence_rule": "trade_first_then_quote_fallback",
                    "zero_volume_bar_policy": "emit_with_explicit_zero_volume_flag",
                    "late_print_policy": "quarantine_for_recertification_review",
                    "correction_policy": "apply_vendor_corrections_via_delta_release",
                    "gap_policy": "preserve_gaps_explicitly",
                    "forward_fill_policy": "never_forward_fill_prices",
                    "symbology_mapping_rules": ["bind_to_resolved_context_bundle_symbology_v4"],
                    "live_historical_parity_expectations": ["same_session_anchor_and_close_rule"],
                    "lifecycle_state": "approved",
                },
            ),
        ):
            with self.subTest(release_kind=release_kind):
                with self.assertRaisesRegex(
                    ValueError,
                    f"{release_kind}: schema_version must be an integer",
                ):
                    build_release(release_kind, payload)

    def test_from_json_rejects_invalid_json_payloads_with_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "dataset_release: invalid JSON payload"):
            DatasetRelease.from_json("{not valid json")

    def test_promotable_surface_binding_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["binding_cases"]:
            with self.subTest(case_id=payload["case_id"]):
                report = validate_promotable_surface_binding(
                    PromotableSurfaceBindingRequest(
                        case_id=payload["case_id"],
                        surface_name=payload["surface_name"],
                        requested_data_profile_release_id=payload[
                            "requested_data_profile_release_id"
                        ],
                        approved_data_profile_release_ids=tuple(
                            payload["approved_data_profile_release_ids"]
                        ),
                        mutable_feed_semantics=tuple(payload["mutable_feed_semantics"]),
                    )
                )
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)

    def test_publication_reports_are_structured_and_diagnostic(self) -> None:
        report = validate_dataset_release(
            "diagnostic-shape",
            DatasetRelease(
                release_id="dataset_release_gold_2026q1_v1",
                raw_input_hashes=("raw_sha256_a",),
                reference_version_hashes=("calendar_sha256_v3",),
                observation_cutoff_utc="2026-03-01T00:00:00+00:00",
                validation_rules_version="validation_rules_v7",
                catalog_version="catalog_v4",
                protocol_versions={"ingestion_protocol": "ingest_v2"},
                vendor_revision_watermark="databento_revision_2026-03-01",
                correction_horizon="t_plus_2_business_days",
                certification_report_hash="cert_report_sha256_001",
                policy_bundle_hash="policy_bundle_sha256_001",
                lifecycle_state=ReleaseLifecycleState.APPROVED,
            ),
        )
        payload = report.to_dict()
        self.assertEqual(ReleaseStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "release_kind",
                "release_id",
                "status",
                "reason_code",
                "schema_version",
                "lifecycle_state",
                "missing_fields",
                "field_errors",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("publishable", report.explanation.lower())


if __name__ == "__main__":
    unittest.main()
