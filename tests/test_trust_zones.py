"""Contract tests for trust-zone isolation and secret-delivery boundaries."""

from __future__ import annotations

import unittest

from shared.policy.trust_zones import (
    SECRET_DELIVERY_SURFACES,
    TRUST_ZONES,
    evaluate_break_glass_access,
    evaluate_dashboard_access,
    evaluate_opsd_artifact_permissions,
    evaluate_secret_delivery,
    evaluate_storage_access,
    evaluate_trust_zone_policy,
    evaluate_zone_secret_inventory,
    evaluate_zone_workloads,
    secret_delivery_surface_keys,
    trust_zone_ids,
)


def healthy_zone_workloads() -> dict[str, list[str]]:
    return {
        "research": ["notebook", "experiment", "tuning_job", "reporting"],
        "release": [
            "artifact_publication",
            "signed_promotion_tooling",
            "certification",
        ],
        "operations": [
            "opsd",
            "broker_connectivity",
            "reconciliation",
            "live_control",
        ],
    }


def healthy_zone_secret_inventory() -> dict[str, list[str]]:
    return {
        "research": ["research_credential"],
        "release": ["release_credential", "release_signing_key"],
        "operations": [
            "operations_runtime_credential",
            "broker_runtime_credential",
            "storage_prefix_credential",
        ],
    }


def healthy_secret_delivery_observations() -> list[dict[str, object]]:
    return [
        {
            "zone": "operations",
            "secret_type": "broker_runtime_credential",
            "surface": "runtime_secret_path",
        },
        {
            "zone": "operations",
            "secret_type": "break_glass_credential",
            "surface": "root_only_encrypted_file",
            "root_only_permissions": True,
        },
    ]


def healthy_break_glass_state() -> dict[str, bool]:
    return {
        "accessed": True,
        "stored_separately": True,
        "mounted_into_standard_process": False,
        "incident_recorded": True,
        "rotated_after_use": True,
        "reviewed_before_next_live": True,
    }


class TestTrustZoneRegistry(unittest.TestCase):
    def test_trust_zone_registry_is_explicit(self):
        self.assertEqual(len(TRUST_ZONES), 3)
        self.assertEqual(trust_zone_ids(), ["research", "release", "operations"])
        self.assertTrue(all(zone.plan_section == "3.4" for zone in TRUST_ZONES))

    def test_secret_delivery_surfaces_are_explicit(self):
        self.assertEqual(len(SECRET_DELIVERY_SURFACES), 11)
        self.assertEqual(
            secret_delivery_surface_keys(),
            [
                "runtime_secret_path",
                "root_only_encrypted_file",
                "secret_service",
                "source_code",
                "notebook",
                "manifest",
                "candidate_bundle",
                "promotion_packet",
                "log",
                "shell_history",
                "systemd_unit_file",
            ],
        )


class TestTrustZoneChecks(unittest.TestCase):
    def test_operations_zone_rejects_notebooks(self):
        diagnostic = evaluate_zone_workloads("operations", ["opsd", "notebook"])
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_WORKLOAD_MISPLACED_OPERATIONS",
        )
        self.assertEqual(diagnostic.boundary_crossed, "trust_zone_workload")
        self.assertEqual(diagnostic.surface, "host_workload")

    def test_research_zone_rejects_broker_credentials(self):
        diagnostics = evaluate_zone_secret_inventory(
            "research",
            ["research_credential", "broker_runtime_credential"],
        )
        violations = [item for item in diagnostics if item.status == "violation"]
        self.assertEqual(len(violations), 1)
        self.assertEqual(
            violations[0].reason_code,
            "TRUST_ZONE_SECRET_EXPOSURE_RESEARCH",
        )
        self.assertEqual(violations[0].secret_type, "broker_runtime_credential")
        self.assertEqual(violations[0].boundary_crossed, "credential_domain")
        self.assertEqual(violations[0].surface, "zone_secret_inventory")

    def test_opsd_cannot_mutate_archives_or_releases(self):
        diagnostic = evaluate_opsd_artifact_permissions(
            reads_approved_artifacts=True,
            writes_evidence=True,
            mutates_raw_archives=True,
            mutates_releases=False,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_OPSD_BOUNDARY_VIOLATION",
        )

    def test_dashboards_must_be_read_only(self):
        diagnostic = evaluate_dashboard_access("editor")
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_DASHBOARD_ROLE_NOT_READ_ONLY",
        )
        self.assertEqual(diagnostic.secret_type, "dashboard_credential")

    def test_storage_credentials_must_be_least_privilege(self):
        diagnostic = evaluate_storage_access(
            credential_scope="account_admin",
            least_privilege=False,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_STORAGE_NOT_LEAST_PRIVILEGE",
        )
        self.assertEqual(diagnostic.secret_type, "storage_prefix_credential")


class TestSecretDeliveryChecks(unittest.TestCase):
    def test_runtime_secret_path_passes_for_baseline_delivery(self):
        diagnostic = evaluate_secret_delivery(
            secret_type="broker_runtime_credential",
            surface="runtime_secret_path",
        )
        self.assertEqual(diagnostic.status, "pass")
        self.assertIsNone(diagnostic.reason_code)

    def test_manifest_embedded_secret_is_rejected(self):
        diagnostic = evaluate_secret_delivery(
            secret_type="operations_runtime_credential",
            surface="manifest",
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_SECRET_EMBEDDED_MANIFEST",
        )
        self.assertEqual(diagnostic.surface, "manifest")
        self.assertEqual(diagnostic.secret_type, "operations_runtime_credential")

    def test_root_only_file_requires_root_permissions(self):
        diagnostic = evaluate_secret_delivery(
            secret_type="break_glass_credential",
            surface="root_only_encrypted_file",
            root_only_permissions=False,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_SECRET_FILE_NOT_ROOT_ONLY",
        )

    def test_credential_domain_growth_requires_heavier_secret_service(self):
        diagnostic = evaluate_secret_delivery(
            secret_type="broker_runtime_credential",
            surface="runtime_secret_path",
            credential_domain_growth=True,
        )
        self.assertEqual(diagnostic.status, "violation")
        self.assertEqual(
            diagnostic.reason_code,
            "TRUST_ZONE_SECRET_DELIVERY_INSUFFICIENT",
        )


class TestBreakGlassWorkflow(unittest.TestCase):
    def test_break_glass_access_requires_incident_rotation_and_review(self):
        diagnostics = evaluate_break_glass_access(**healthy_break_glass_state())
        self.assertTrue(all(item.status == "pass" for item in diagnostics))
        self.assertEqual(len(diagnostics), 4)

    def test_break_glass_access_without_incident_record_is_rejected(self):
        state = healthy_break_glass_state()
        state["incident_recorded"] = False

        diagnostics = evaluate_break_glass_access(**state)
        violations = [item for item in diagnostics if item.status == "violation"]
        self.assertEqual(len(violations), 1)
        self.assertEqual(
            violations[0].reason_code,
            "TRUST_ZONE_BREAK_GLASS_INCIDENT_MISSING",
        )
        self.assertEqual(violations[0].surface, "incident_record")
        self.assertEqual(violations[0].secret_type, "break_glass_credential")


class TestAggregatePolicyEvaluation(unittest.TestCase):
    def test_healthy_trust_zone_policy_passes(self):
        result = evaluate_trust_zone_policy(
            zone_workloads=healthy_zone_workloads(),
            zone_secret_inventory=healthy_zone_secret_inventory(),
            opsd_capabilities={
                "reads_approved_artifacts": True,
                "writes_evidence": True,
                "mutates_raw_archives": False,
                "mutates_releases": False,
            },
            dashboard_role="read_only",
            storage_access={
                "credential_scope": "prefix_scoped",
                "least_privilege": True,
                "zone": "operations",
            },
            secret_delivery_observations=healthy_secret_delivery_observations(),
            break_glass_state=healthy_break_glass_state(),
        )
        self.assertTrue(result["allowed"])
        self.assertTrue(
            all(item["status"] == "pass" for item in result["diagnostics"])
        )

    def test_policy_evaluation_collects_secret_and_break_glass_violations(self):
        workloads = healthy_zone_workloads()
        workloads["operations"].append("notebook")

        inventory = healthy_zone_secret_inventory()
        inventory["research"].append("break_glass_credential")

        deliveries = healthy_secret_delivery_observations()
        deliveries.append(
            {
                "zone": "operations",
                "secret_type": "operations_runtime_credential",
                "surface": "manifest",
            }
        )

        break_glass_state = healthy_break_glass_state()
        break_glass_state["reviewed_before_next_live"] = False

        result = evaluate_trust_zone_policy(
            zone_workloads=workloads,
            zone_secret_inventory=inventory,
            opsd_capabilities={
                "reads_approved_artifacts": True,
                "writes_evidence": True,
                "mutates_raw_archives": False,
                "mutates_releases": False,
            },
            dashboard_role="read_only",
            storage_access={
                "credential_scope": "prefix_scoped",
                "least_privilege": True,
                "zone": "operations",
            },
            secret_delivery_observations=deliveries,
            break_glass_state=break_glass_state,
        )

        self.assertFalse(result["allowed"])
        reason_codes = {item["reason_code"] for item in result["diagnostics"]}
        self.assertIn("TRUST_ZONE_WORKLOAD_MISPLACED_OPERATIONS", reason_codes)
        self.assertIn("TRUST_ZONE_SECRET_EXPOSURE_RESEARCH", reason_codes)
        self.assertIn("TRUST_ZONE_SECRET_EMBEDDED_MANIFEST", reason_codes)
        self.assertIn("TRUST_ZONE_BREAK_GLASS_REVIEW_MISSING", reason_codes)
