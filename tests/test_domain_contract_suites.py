"""Contract tests for the shared domain verification suite registry."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from shared.policy.verification.domain_contract_suites import (
    VALIDATION_ERRORS,
    DomainContractSuiteReport,
    DomainContractSuiteStatus,
    build_sample_domain_contract_suite_run,
    domain_contract_suite_ids,
    domain_contract_suite_specs_by_id,
    evaluate_domain_contract_suite_run,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "verification"
    / "domain_contract_suite_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(
            f"domain contract suite fixture failed to load: {exc}"
        ) from exc


def build_case_run(case: dict[str, object]):
    run = build_sample_domain_contract_suite_run(
        str(case["suite_id"]),
        run_id=str(case["run_id"]),
        fixture_case_id=str(case["fixture_case_id"]),
    )
    mutation = str(case["mutation"])

    if mutation == "valid":
        return run
    if mutation == "missing_expected_diff":
        return replace(run, expected_vs_actual_diff_artifact_ids=())
    if mutation == "log_linkage_mismatch":
        log_payload = dict(run.structured_log)
        log_payload["correlation_id"] = "corr_mismatch"
        return replace(run, structured_log=log_payload)
    if mutation == "missing_fixture_source":
        return replace(run, fixture_sources=run.fixture_sources[:-1])
    if mutation == "missing_test_module":
        return replace(run, test_modules=run.test_modules[:-1])
    if mutation == "unknown_suite":
        return replace(run, suite_id="unknown_domain_suite")
    raise AssertionError(f"unexpected mutation in fixture: {mutation}")


class DomainContractSuiteRegistryTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_catalog_covers_expected_suites_beads_and_planes(self) -> None:
        expectations = load_cases()["catalog_expectations"]
        specs = domain_contract_suite_specs_by_id()

        self.assertEqual(
            tuple(expectations["expected_suite_ids"]),
            domain_contract_suite_ids(),
        )
        self.assertEqual(
            set(expectations["expected_related_beads"]),
            {
                bead
                for spec in specs.values()
                for bead in spec.related_beads
            },
        )
        self.assertEqual(
            dict(expectations["expected_trace_planes"]),
            {
                suite_id: spec.trace_plane.value
                for suite_id, spec in specs.items()
            },
        )

    def test_sample_run_round_trip_preserves_shape(self) -> None:
        run = build_sample_domain_contract_suite_run(
            "broker_semantics_contracts",
            run_id="broker_semantics_suite_round_trip",
            fixture_case_id="broker_semantics_round_trip",
        )
        self.assertEqual(run, run.from_json(run.to_json()))

    def test_sample_run_uses_catalog_modules_fixture_sources_and_artifacts(self) -> None:
        run = build_sample_domain_contract_suite_run(
            "policy_engine_decision_traces",
            run_id="policy_engine_suite_shape",
            fixture_case_id="policy_engine_shape",
        )
        spec = domain_contract_suite_specs_by_id()["policy_engine_decision_traces"]

        self.assertEqual(spec.required_test_modules, run.test_modules)
        self.assertEqual(spec.required_fixture_sources, run.fixture_sources)
        self.assertEqual(
            {"fixture_manifest", "structured_log", "expected_vs_actual_diff"},
            {artifact.artifact_role for artifact in run.artifacts},
        )
        self.assertEqual(
            run.fixture_manifest_id,
            run.structured_log["artifact_manifest"]["manifest_id"],
        )

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["run_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_domain_contract_suite_run(
                    str(case["case_id"]),
                    build_case_run(case),
                )
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

    def test_pass_report_is_structured_and_trace_linked(self) -> None:
        report = evaluate_domain_contract_suite_run(
            "structured-pass",
            build_sample_domain_contract_suite_run(
                "release_schema_and_artifact_lifecycle",
                run_id="release_schema_suite_structured",
                fixture_case_id="release_schema_structured",
            ),
        )
        payload = report.to_dict()

        self.assertEqual(DomainContractSuiteStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "suite_id",
                "run_id",
                "status",
                "reason_code",
                "missing_fields",
                "context",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("trace-linked", report.explanation.lower())
        self.assertEqual(
            "release",
            payload["context"]["trace_plane"],
        )

    def test_report_round_trip_preserves_payload(self) -> None:
        report = evaluate_domain_contract_suite_run(
            "report-round-trip",
            build_sample_domain_contract_suite_run(
                "strategy_contract_contracts",
                run_id="strategy_contract_suite_round_trip",
                fixture_case_id="strategy_contract_round_trip",
            ),
        )
        self.assertEqual(report, DomainContractSuiteReport.from_json(report.to_json()))


if __name__ == "__main__":
    unittest.main()
