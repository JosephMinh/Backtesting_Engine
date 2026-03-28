from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.strategy_contract import (
    REQUIRED_ORDER_INTENT_FIELDS,
    VALIDATION_ERRORS,
    StrategyContract,
    StrategyContractCompatibilityReport,
    StrategyContractReport,
    StrategyContractStatus,
    evaluate_strategy_contract,
    evaluate_strategy_contract_compatibility,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "strategy_contract_cases.json"
)


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


class StrategyContractCatalogTests(unittest.TestCase):
    def test_strategy_contract_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


class StrategyContractEvaluationTests(unittest.TestCase):
    def test_fixture_cases_match_expected_contract_reports(self) -> None:
        payload = load_fixture()
        for case in payload["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                contract = StrategyContract.from_dict(dict(case["contract"]))
                report = evaluate_strategy_contract(contract)
                expected = case["expected"]
                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    expected["stable_contract_complete"],
                    report.stable_contract_complete,
                )
                self.assertEqual(
                    expected["canonical_kernel_rule_satisfied"],
                    report.canonical_kernel_rule_satisfied,
                )
                self.assertEqual(
                    expected["equivalence_certification_required"],
                    report.equivalence_certification_required,
                )
                self.assertEqual(
                    expected["equivalence_certification_ready"],
                    report.equivalence_certification_ready,
                )

    def test_contract_round_trip_preserves_nested_structures(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        contract = StrategyContract.from_dict(dict(case["contract"]))
        reparsed = StrategyContract.from_json(contract.to_json())

        self.assertEqual(contract.contract_id, reparsed.contract_id)
        self.assertEqual(contract.decision_cadence, reparsed.decision_cadence)
        self.assertEqual(contract.order_intent_schema, reparsed.order_intent_schema)
        self.assertEqual(contract.signal_kernel, reparsed.signal_kernel)

    def test_contract_loader_rejects_invalid_boundary_values(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        base_payload = deepcopy(case["contract"])
        invalid_cases = (
            (
                "dependency_node_id_bool",
                lambda payload: payload["dependency_dag"][0].__setitem__("node_id", False),
                "node_id: must be a non-empty string",
            ),
            (
                "decision_basis_invalid",
                lambda payload: payload["decision_cadence"].__setitem__("decision_basis", "tick"),
                "decision_basis: must be a valid decision basis",
            ),
            (
                "requires_state_seed_truthy_string",
                lambda payload: payload["warmup"].__setitem__("requires_state_seed", "true"),
                "requires_state_seed: must be boolean",
            ),
            (
                "kernel_kind_invalid",
                lambda payload: payload["signal_kernel"].__setitem__(
                    "canonical_implementation_kind",
                    "cpp",
                ),
                "canonical_implementation_kind: must be a valid kernel implementation kind",
            ),
            (
                "candidate_freeze_ready_truthy_string",
                lambda payload: payload.__setitem__("candidate_freeze_ready", "true"),
                "candidate_freeze_ready: must be boolean",
            ),
            (
                "schema_version_unsupported",
                lambda payload: payload.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    StrategyContract.from_dict(payload)

    def test_direct_from_dict_loaders_reject_non_object_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "strategy_contract: must be an object"):
            StrategyContract.from_dict([])  # type: ignore[arg-type]

        with self.assertRaisesRegex(
            ValueError,
            "strategy_contract_report: must be an object",
        ):
            StrategyContractReport.from_dict([])  # type: ignore[arg-type]

        with self.assertRaisesRegex(
            ValueError,
            "strategy_contract_compatibility_report: must be an object",
        ):
            StrategyContractCompatibilityReport.from_dict([])  # type: ignore[arg-type]

    def test_missing_required_order_intent_fields_invalidates_contract(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        for required_field in REQUIRED_ORDER_INTENT_FIELDS:
            with self.subTest(required_field=required_field):
                contract_payload = dict(case["contract"])
                order_intent_schema = dict(contract_payload["order_intent_schema"])
                order_intent_schema["required_fields"] = [
                    field_name
                    for field_name in order_intent_schema["required_fields"]
                    if field_name != required_field
                ]
                contract_payload["order_intent_schema"] = order_intent_schema

                contract = StrategyContract.from_dict(contract_payload)
                report = evaluate_strategy_contract(contract)

                self.assertEqual(StrategyContractStatus.INVALID.value, report.status)
                self.assertIn(
                    "order_intent_schema.required_fields",
                    report.missing_fields,
                )

    def test_dependency_cycle_is_reported_as_a_violation(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        contract_payload = dict(case["contract"])
        contract_payload["dependency_dag"] = [
            {"node_id": "features", "depends_on": ["orders"]},
            {"node_id": "signal", "depends_on": ["features"]},
            {"node_id": "risk", "depends_on": ["signal"]},
            {"node_id": "orders", "depends_on": ["risk"]},
        ]

        contract = StrategyContract.from_dict(contract_payload)
        report = evaluate_strategy_contract(contract)

        self.assertEqual(StrategyContractStatus.VIOLATION.value, report.status)
        self.assertFalse(report.dependency_dag_acyclic)
        self.assertIn("dependency_dag.cycle", report.violated_guarantees)

    def test_contract_report_round_trip_preserves_emitted_shape(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        contract = StrategyContract.from_dict(dict(case["contract"]))
        report = evaluate_strategy_contract(contract)

        self.assertEqual(
            report.to_dict(),
            StrategyContractReport.from_json(report.to_json()).to_dict(),
        )

    def test_contract_report_loader_rejects_invalid_boundary_values(self) -> None:
        case = load_fixture()["evaluation_cases"][1]
        contract = StrategyContract.from_dict(dict(case["contract"]))
        base_payload = evaluate_strategy_contract(contract).to_dict()
        invalid_cases = (
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ship"),
                "status: must be a valid strategy contract status",
            ),
            (
                "stable_contract_complete_truthy_string",
                lambda payload: payload.__setitem__("stable_contract_complete", "true"),
                "stable_contract_complete: must be boolean",
            ),
            (
                "missing_fields_string",
                lambda payload: payload.__setitem__("missing_fields", "field"),
                "missing_fields: must be a list of strings",
            ),
            (
                "timestamp_naive",
                lambda payload: payload.__setitem__("timestamp", "2026-03-28T00:00:00"),
                "timestamp: must be timezone-aware",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    StrategyContractReport.from_dict(payload)


class StrategyContractCompatibilityTests(unittest.TestCase):
    def test_fixture_cases_match_expected_compatibility_reports(self) -> None:
        payload = load_fixture()
        for case in payload["compatibility_cases"]:
            with self.subTest(case_id=case["case_id"]):
                previous = StrategyContract.from_dict(dict(case["previous"]))
                current = StrategyContract.from_dict(dict(case["current"]))
                report = evaluate_strategy_contract_compatibility(previous, current)
                expected = case["expected"]
                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(expected["compatible"], report.compatible)
                self.assertEqual(
                    expected["requires_recertification"],
                    report.requires_recertification,
                )
                if "changed_fields" in expected:
                    self.assertEqual(tuple(expected["changed_fields"]), report.changed_fields)
                if "broken_guarantees" in expected:
                    self.assertEqual(
                        tuple(expected["broken_guarantees"]),
                        report.broken_guarantees,
                    )

    def test_semver_regression_is_invalid(self) -> None:
        case = load_fixture()["compatibility_cases"][0]
        previous = StrategyContract.from_dict(dict(case["previous"]))
        current_payload = dict(case["current"])
        signal_kernel = dict(current_payload["signal_kernel"])
        signal_kernel["semantic_version"] = "1.2.0"
        current_payload["signal_kernel"] = signal_kernel
        current = StrategyContract.from_dict(current_payload)

        report = evaluate_strategy_contract_compatibility(previous, current)

        self.assertEqual(StrategyContractStatus.INVALID.value, report.status)
        self.assertEqual("STRATEGY_CONTRACT_SEMVER_REGRESSION", report.reason_code)

    def test_compatibility_report_round_trip_preserves_emitted_shape(self) -> None:
        case = load_fixture()["compatibility_cases"][0]
        previous = StrategyContract.from_dict(dict(case["previous"]))
        current = StrategyContract.from_dict(dict(case["current"]))
        report = evaluate_strategy_contract_compatibility(previous, current)

        self.assertEqual(
            report.to_dict(),
            StrategyContractCompatibilityReport.from_json(report.to_json()).to_dict(),
        )

    def test_compatibility_report_loader_rejects_invalid_boundary_values(self) -> None:
        case = load_fixture()["compatibility_cases"][0]
        previous = StrategyContract.from_dict(dict(case["previous"]))
        current = StrategyContract.from_dict(dict(case["current"]))
        base_payload = evaluate_strategy_contract_compatibility(previous, current).to_dict()
        invalid_cases = (
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ship"),
                "status: must be a valid strategy contract status",
            ),
            (
                "compatible_truthy_string",
                lambda payload: payload.__setitem__("compatible", "true"),
                "compatible: must be boolean",
            ),
            (
                "changed_fields_string",
                lambda payload: payload.__setitem__("changed_fields", "field"),
                "changed_fields: must be a list of strings",
            ),
            (
                "timestamp_naive",
                lambda payload: payload.__setitem__("timestamp", "2026-03-28T00:00:00"),
                "timestamp: must be timezone-aware",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    StrategyContractCompatibilityReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
