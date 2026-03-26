"""Contract tests for observability dashboards, alerts, and operator targets."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.observability import (
    OBSERVABILITY_ALERTS,
    OBSERVABILITY_DASHBOARDS,
    OBSERVABILITY_PANELS,
    REQUIRED_ALERT_CONTEXT_FIELDS,
    REQUIRED_ALERT_IDS,
    REQUIRED_METRIC_CATEGORIES,
    VALIDATION_ERRORS,
    alert_ids,
    dashboard_ids,
    evaluate_observability_coverage,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "observability_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"observability fixture failed to load: {exc}") from exc


class ObservabilityContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_required_categories_and_alerts_are_fully_covered(self) -> None:
        self.assertEqual(set(REQUIRED_METRIC_CATEGORIES), {panel.category_id for panel in OBSERVABILITY_PANELS})
        self.assertEqual(set(REQUIRED_ALERT_IDS), set(alert_ids()))

    def test_dashboard_fixture_expectations_match_declared_panels(self) -> None:
        dashboards = {dashboard.dashboard_id: dashboard for dashboard in OBSERVABILITY_DASHBOARDS}
        panels = {panel.panel_id: panel for panel in OBSERVABILITY_PANELS}

        for payload in load_cases()["dashboard_expectations"]:
            dashboard_id = payload["dashboard_id"]
            with self.subTest(dashboard_id=dashboard_id):
                dashboard = dashboards[dashboard_id]
                self.assertEqual(tuple(payload["expected_panel_ids"]), dashboard.panel_ids)
                self.assertEqual(
                    set(payload["expected_categories"]),
                    {panels[panel_id].category_id for panel_id in dashboard.panel_ids},
                )

    def test_alert_fixture_expectations_match_response_targets(self) -> None:
        alerts = {alert.alert_id: alert for alert in OBSERVABILITY_ALERTS}

        for payload in load_cases()["alert_expectations"]:
            alert_id = payload["alert_id"]
            with self.subTest(alert_id=alert_id):
                alert = alerts[alert_id]
                self.assertEqual(
                    payload["expected_response_target_minutes"],
                    alert.response_target_minutes,
                )
                self.assertEqual(
                    payload["expected_explain_surface"],
                    alert.explain_surface,
                )
                self.assertEqual(
                    tuple(payload["expected_related_panel_ids"]),
                    alert.related_panel_ids,
                )
                self.assertTrue(
                    set(REQUIRED_ALERT_CONTEXT_FIELDS).issubset(alert.required_context_fields)
                )
                self.assertTrue(alert.artifact_reference_fields)
                self.assertTrue(alert.supporting_metric_keys)

    def test_panels_keep_explain_and_artifact_links(self) -> None:
        for panel in OBSERVABILITY_PANELS:
            with self.subTest(panel_id=panel.panel_id):
                self.assertTrue(panel.explain_surface)
                self.assertTrue(panel.retained_artifact_fields)
                self.assertTrue(panel.freshness_fields)
                self.assertTrue(panel.metric_keys)

    def test_coverage_report_matches_fixture_summary(self) -> None:
        report = evaluate_observability_coverage()
        payload = load_cases()["coverage_case"]

        self.assertEqual(payload["expected_status"], report.status)
        self.assertEqual(payload["expected_reason_code"], report.reason_code)
        self.assertEqual(tuple(payload["expected_dashboard_ids"]), report.dashboard_ids)
        self.assertEqual(payload["expected_panel_count"], report.panel_count)
        self.assertEqual(payload["expected_alert_count"], report.alert_count)
        self.assertEqual((), report.missing_metric_categories)
        self.assertEqual((), report.missing_alert_ids)
        self.assertEqual((), report.panels_missing_explain_links)
        self.assertEqual((), report.panels_missing_artifact_links)
        self.assertEqual((), report.panels_missing_freshness_fields)
        self.assertEqual((), report.alerts_missing_context)
        self.assertEqual((), report.alerts_missing_artifact_links)
        self.assertEqual((), report.alerts_with_invalid_targets)
        self.assertIn("freshness", report.explanation.lower())

    def test_dashboard_ids_are_sorted_for_operator_consumers(self) -> None:
        self.assertEqual(sorted(dashboard_ids()), dashboard_ids())


if __name__ == "__main__":
    unittest.main()
