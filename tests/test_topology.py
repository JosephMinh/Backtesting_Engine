"""Contract tests for the one-host baseline topology and startup checks."""

from __future__ import annotations

import unittest

from shared.policy.topology import (
    BASELINE_COMPONENTS,
    baseline_component_keys,
    evaluate_component_startup,
    evaluate_startup_checks,
    evaluate_topology,
)


def healthy_component_status() -> dict[str, dict[str, object]]:
    return {
        "linux_host": {"present": True, "connectable": True, "healthy": True},
        "postgresql16": {"present": True, "connectable": True, "healthy": True},
        "off_host_object_storage": {"present": True, "connectable": True, "healthy": True},
        "prometheus": {"present": True, "connectable": True, "healthy": True},
        "grafana": {"present": True, "connectable": True, "healthy": True},
        "loki": {"present": True, "connectable": True, "healthy": True},
        "ib_gateway": {"present": True, "connectable": True, "healthy": True},
        "opsd": {"present": True, "connectable": True, "healthy": True},
        "guardian": {"present": True, "connectable": True, "healthy": True},
        "watchdog": {"present": True, "connectable": True, "healthy": True},
    }


QUIET_TRIGGER_EVIDENCE: dict[str, object] = {
    "hot_path_hosts_required": 1,
    "durable_external_consumers": 0,
    "telemetry_degrades_metadata_latency": False,
    "secret_delivery_insufficient": False,  # nosec B105 - trigger flag, not a credential
    "repeated_infra_slo_misses": False,
}


class TestBaselineTopologyRegistry(unittest.TestCase):
    def test_required_component_registry_is_explicit(self):
        self.assertEqual(len(BASELINE_COMPONENTS), 10)
        self.assertEqual(
            baseline_component_keys(),
            [
                "linux_host",
                "postgresql16",
                "off_host_object_storage",
                "prometheus",
                "grafana",
                "loki",
                "ib_gateway",
                "opsd",
                "guardian",
                "watchdog",
            ],
        )

    def test_component_keys_are_unique(self):
        keys = [component.key for component in BASELINE_COMPONENTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_all_components_are_plan_bound_to_section_3_2(self):
        for component in BASELINE_COMPONENTS:
            self.assertEqual(component.plan_section, "3.2")
            self.assertTrue(component.resolution_guidance)


class TestStartupChecks(unittest.TestCase):
    def test_healthy_baseline_passes_all_component_checks(self):
        diagnostics = evaluate_startup_checks(healthy_component_status())
        self.assertTrue(all(diagnostic.status == "pass" for diagnostic in diagnostics))

    def test_missing_component_emits_structured_resolution_guidance(self):
        component_status = healthy_component_status()
        component_status["guardian"] = {
            "present": False,
            "connectable": False,
            "healthy": False,
        }

        diagnostic = evaluate_component_startup("guardian", component_status)
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(diagnostic.reason_code, "TOPOLOGY_COMPONENT_MISSING_GUARDIAN")
        self.assertIn("guardian", diagnostic.explanation.lower())
        self.assertIn(
            "independently available",
            diagnostic.resolution_guidance.lower(),
        )

        payload = diagnostic.to_dict()
        self.assertEqual(payload["component"], "guardian")
        self.assertEqual(payload["status"], "violation")
        self.assertEqual(payload["reason_code"], "TOPOLOGY_COMPONENT_MISSING_GUARDIAN")

    def test_dependency_failure_is_reported_before_component_health(self):
        component_status = healthy_component_status()
        component_status["ib_gateway"]["healthy"] = False

        diagnostic = evaluate_component_startup("guardian", component_status)
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TOPOLOGY_DEPENDENCY_UNHEALTHY_GUARDIAN",
        )
        self.assertEqual(diagnostic.dependency_status["ib_gateway"], "unhealthy")

    def test_unconnectable_component_is_reported(self):
        component_status = healthy_component_status()
        component_status["postgresql16"]["connectable"] = False

        diagnostic = evaluate_component_startup("postgresql16", component_status)
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TOPOLOGY_COMPONENT_NOT_CONNECTABLE_POSTGRESQL16",
        )

    def test_unhealthy_component_is_reported(self):
        component_status = healthy_component_status()
        component_status["loki"]["healthy"] = False

        diagnostic = evaluate_component_startup("loki", component_status)
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(diagnostic.reason_code, "TOPOLOGY_COMPONENT_UNHEALTHY_LOKI")


class TestTopologyEvaluation(unittest.TestCase):
    def test_one_host_baseline_is_sufficient_when_quiet_and_healthy(self):
        result = evaluate_topology(
            host_count=1,
            component_status=healthy_component_status(),
            upgrade_trigger_evidence=QUIET_TRIGGER_EVIDENCE,
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["baseline_trace"]["status"], "pass")
        self.assertTrue(
            all(item["status"] == "pass" for item in result["startup_diagnostics"])
        )

    def test_upgrade_trigger_rejects_baseline_sufficiency(self):
        trigger_evidence = dict(QUIET_TRIGGER_EVIDENCE)
        trigger_evidence["repeated_infra_slo_misses"] = True

        result = evaluate_topology(
            host_count=1,
            component_status=healthy_component_status(),
            upgrade_trigger_evidence=trigger_evidence,
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(
            result["baseline_trace"]["reason_code"],
            "TOPOLOGY_ONE_HOST_BASELINE_NO_LONGER_SUFFICIENT",
        )
        self.assertTrue(any(trigger["triggered"] for trigger in result["upgrade_triggers"]))

    def test_host_count_drift_rejects_baseline(self):
        result = evaluate_topology(
            host_count=2,
            component_status=healthy_component_status(),
            upgrade_trigger_evidence=QUIET_TRIGGER_EVIDENCE,
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["baseline_trace"]["status"], "violation")

    def test_startup_violation_blocks_topology_even_when_one_host_holds(self):
        component_status = healthy_component_status()
        component_status["watchdog"]["present"] = False

        result = evaluate_topology(
            host_count=1,
            component_status=component_status,
            upgrade_trigger_evidence=QUIET_TRIGGER_EVIDENCE,
        )

        self.assertFalse(result["allowed"])
        violations = [
            item for item in result["startup_diagnostics"] if item["status"] == "violation"
        ]
        self.assertEqual(len(violations), 1)
        self.assertEqual(
            violations[0]["reason_code"],
            "TOPOLOGY_COMPONENT_MISSING_WATCHDOG",
        )
