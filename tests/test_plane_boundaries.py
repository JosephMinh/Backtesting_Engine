"""Contract tests for plane separation and shared contract boundaries."""

from __future__ import annotations

import unittest

from shared.policy.plane_boundaries import (
    PLANE_DEFINITIONS,
    SHARED_CONTRACT_SURFACES,
    ImportEdge,
    PlaneId,
    evaluate_import_edge,
    shared_contract_compile_reports,
    validate_import_boundaries,
)


class TestPlaneRegistry(unittest.TestCase):
    def test_plane_registry_has_explicit_ownership(self):
        self.assertEqual(5, len(PLANE_DEFINITIONS))
        for definition in PLANE_DEFINITIONS:
            self.assertTrue(definition.owned_path_prefixes)
            self.assertTrue(definition.responsibilities)
            self.assertEqual("3.1", definition.plan_section)

    def test_plane_ids_are_unique(self):
        plane_ids = [definition.plane_id for definition in PLANE_DEFINITIONS]
        self.assertEqual(len(plane_ids), len(set(plane_ids)))

    def test_shared_contracts_have_no_runtime_plane_dependencies(self):
        shared_contracts = next(
            definition
            for definition in PLANE_DEFINITIONS
            if definition.plane_id == PlaneId.SHARED_CONTRACTS
        )
        self.assertEqual((), shared_contracts.allowed_dependencies)

    def test_research_plane_only_depends_on_shared_or_bindings(self):
        research = next(
            definition
            for definition in PLANE_DEFINITIONS
            if definition.plane_id == PlaneId.PYTHON_RESEARCH
        )
        self.assertEqual(
            {
                PlaneId.SHARED_CONTRACTS,
                PlaneId.PYTHON_BINDINGS,
            },
            set(research.allowed_dependencies),
        )


class TestImportBoundaryChecks(unittest.TestCase):
    def test_current_repo_imports_respect_plane_boundaries(self):
        reports = validate_import_boundaries()
        self.assertTrue(reports)
        violations = [report for report in reports if report.status == "violation"]
        self.assertEqual([], violations)

    def test_violation_report_is_structured_and_operator_readable(self):
        report = evaluate_import_edge(
            ImportEdge(
                source_path="shared/policy/example.py",
                source_line=12,
                importer_module="shared.policy.example",
                importer_plane=PlaneId.SHARED_CONTRACTS.value,
                imported_module="python.research.charter.posture",
                imported_plane=PlaneId.PYTHON_RESEARCH.value,
            )
        )

        self.assertEqual("violation", report.status)
        self.assertEqual("shared_contracts->python_research", report.boundary_crossed)
        self.assertEqual(
            "ARCH_BOUNDARY_VIOLATION_SHARED_CONTRACTS_TO_PYTHON_RESEARCH",
            report.reason_code,
        )
        self.assertIn("shared interfaces", report.explanation.lower())
        self.assertIn(
            "owns this dependency surface",
            report.expected_ownership_assignment,
        )

        payload = report.to_dict()
        required_fields = {
            "source_path",
            "source_line",
            "importer_module",
            "importer_plane",
            "imported_module",
            "imported_plane",
            "boundary_crossed",
            "status",
            "reason_code",
            "expected_ownership_assignment",
            "explanation",
            "timestamp",
        }
        self.assertTrue(required_fields.issubset(payload.keys()))

    def test_allowed_dependency_report_is_structured(self):
        report = evaluate_import_edge(
            ImportEdge(
                source_path="python/research/example.py",
                source_line=5,
                importer_module="python.research.example",
                importer_plane=PlaneId.PYTHON_RESEARCH.value,
                imported_module="shared.policy.scope",
                imported_plane=PlaneId.SHARED_CONTRACTS.value,
            )
        )

        self.assertEqual("pass", report.status)
        self.assertEqual("python_research->shared_contracts", report.boundary_crossed)
        self.assertEqual(
            "ARCH_BOUNDARY_ALLOWED_PYTHON_RESEARCH_TO_SHARED_CONTRACTS",
            report.reason_code,
        )


class TestSharedContractCompatibility(unittest.TestCase):
    def test_shared_contract_surfaces_are_declared(self):
        self.assertGreaterEqual(len(SHARED_CONTRACT_SURFACES), 9)
        surface_ids = [surface.surface_id for surface in SHARED_CONTRACT_SURFACES]
        self.assertEqual(len(surface_ids), len(set(surface_ids)))
        self.assertIn("clock_discipline_contract", surface_ids)
        self.assertIn("metadata_vs_telemetry_contract", surface_ids)
        self.assertIn("product_and_account_profiles", surface_ids)
        self.assertIn("storage_tiers_and_point_in_time_binding", surface_ids)

    def test_shared_contract_surfaces_compile(self):
        reports = shared_contract_compile_reports()
        self.assertTrue(reports)
        self.assertTrue(all(report.compiled for report in reports))

    def test_shared_contracts_cover_all_consumer_planes(self):
        reports = shared_contract_compile_reports()
        consumer_planes = {
            consumer_plane
            for report in reports
            for consumer_plane in report.consumer_planes
        }
        self.assertIn(PlaneId.PYTHON_RESEARCH.value, consumer_planes)
        self.assertIn(PlaneId.RUST_KERNELS.value, consumer_planes)
        self.assertIn(PlaneId.RUST_OPERATIONS.value, consumer_planes)

    def test_contract_reports_are_structured(self):
        report = shared_contract_compile_reports()[0]
        payload = report.to_dict()
        required_fields = {
            "surface_id",
            "module",
            "source_path",
            "owned_by",
            "consumer_planes",
            "compiled",
            "reason_code",
            "explanation",
            "timestamp",
        }
        self.assertTrue(required_fields.issubset(payload.keys()))


if __name__ == "__main__":
    unittest.main()
