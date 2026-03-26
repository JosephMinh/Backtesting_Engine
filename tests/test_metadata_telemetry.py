import unittest

from shared.policy.metadata_telemetry import (
    RECORD_DEFINITIONS,
    StorageClass,
    VALIDATION_ERRORS,
    classification_reports,
    derivability_reports,
    records_by_storage_class,
)


class MetadataTelemetryContractTest(unittest.TestCase):
    def test_metadata_contract_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_canonical_metadata_remains_queryable_and_durable(self) -> None:
        canonical_records = records_by_storage_class(StorageClass.CANONICAL_METADATA)
        self.assertTrue(canonical_records)
        for record in canonical_records:
            with self.subTest(record_id=record.record_id):
                self.assertTrue(record.queryable_when_telemetry_pruned)
                self.assertTrue(record.durable_when_telemetry_pruned)
                self.assertTrue(record.retention_independent)

    def test_canonical_records_never_depend_on_telemetry_only_fields(self) -> None:
        for record in records_by_storage_class(StorageClass.CANONICAL_METADATA):
            with self.subTest(record_id=record.record_id):
                field_classes = {field_definition.field_class.value for field_definition in record.fields}
                self.assertNotIn("telemetry_only", field_classes)

    def test_dense_telemetry_is_anchored_but_not_authoritative(self) -> None:
        telemetry_records = records_by_storage_class(StorageClass.DENSE_TELEMETRY)
        self.assertTrue(telemetry_records)
        for record in telemetry_records:
            with self.subTest(record_id=record.record_id):
                self.assertFalse(record.queryable_when_telemetry_pruned)
                self.assertFalse(record.durable_when_telemetry_pruned)
                self.assertFalse(record.retention_independent)
                self.assertTrue(
                    any(
                        field_definition.field_class.value == "canonical_reference"
                        for field_definition in record.fields
                    )
                )
                self.assertFalse(
                    any(field_definition.required_for for field_definition in record.fields)
                )

    def test_replay_and_promotion_inputs_only_live_in_canonical_records(self) -> None:
        for report in derivability_reports():
            with self.subTest(record_id=report.record_id):
                if report.storage_class == StorageClass.DENSE_TELEMETRY.value:
                    self.assertFalse(report.replay_applicable)
                    self.assertFalse(report.promotion_applicable)
                    self.assertFalse(report.replay_state_derived_from_canonical)
                    self.assertFalse(report.promotion_state_derived_from_canonical)
                else:
                    if report.replay_applicable:
                        self.assertTrue(report.replay_state_derived_from_canonical)
                    if report.promotion_applicable:
                        self.assertTrue(report.promotion_state_derived_from_canonical)
                    self.assertEqual((), report.offending_fields)

    def test_classification_reports_list_every_field_and_lifecycle_binding(self) -> None:
        reports_by_id = {report.record_id: report for report in classification_reports()}
        self.assertEqual(len(RECORD_DEFINITIONS), len(reports_by_id))

        for record in RECORD_DEFINITIONS:
            with self.subTest(record_id=record.record_id):
                report = reports_by_id[record.record_id]
                expected_field_classification = {
                    field_definition.name: field_definition.field_class.value
                    for field_definition in record.fields
                }
                expected_replay_fields = tuple(
                    field_definition.name
                    for field_definition in record.fields
                    if "replay" in {need.value for need in field_definition.required_for}
                )
                expected_promotion_fields = tuple(
                    field_definition.name
                    for field_definition in record.fields
                    if "promotion" in {need.value for need in field_definition.required_for}
                )

                self.assertEqual(expected_field_classification, report.field_classification)
                self.assertEqual(expected_replay_fields, report.replay_fields)
                self.assertEqual(expected_promotion_fields, report.promotion_fields)

    def test_derivability_reports_match_record_requirements(self) -> None:
        reports_by_id = {report.record_id: report for report in derivability_reports()}
        self.assertEqual(len(RECORD_DEFINITIONS), len(reports_by_id))

        for record in RECORD_DEFINITIONS:
            with self.subTest(record_id=record.record_id):
                report = reports_by_id[record.record_id]
                expected_replay_applicable = any(
                    "replay" in {need.value for need in field_definition.required_for}
                    for field_definition in record.fields
                )
                expected_promotion_applicable = any(
                    "promotion" in {need.value for need in field_definition.required_for}
                    for field_definition in record.fields
                )

                if record.storage_class == StorageClass.DENSE_TELEMETRY:
                    self.assertFalse(expected_replay_applicable)
                    self.assertFalse(expected_promotion_applicable)
                    self.assertFalse(report.replay_applicable)
                    self.assertFalse(report.promotion_applicable)
                    self.assertFalse(report.replay_state_derived_from_canonical)
                    self.assertFalse(report.promotion_state_derived_from_canonical)
                else:
                    self.assertEqual(expected_replay_applicable, report.replay_applicable)
                    self.assertEqual(expected_promotion_applicable, report.promotion_applicable)
                    if expected_replay_applicable:
                        self.assertTrue(report.replay_state_derived_from_canonical)
                    if expected_promotion_applicable:
                        self.assertTrue(report.promotion_state_derived_from_canonical)
                    self.assertEqual((), report.offending_fields)

    def test_reports_are_structured_and_operator_readable(self) -> None:
        classification_report = classification_reports()[0]
        classification_payload = classification_report.to_dict()
        self.assertTrue(
            {
                "record_id",
                "storage_class",
                "plan_section",
                "queryable_when_telemetry_pruned",
                "durable_when_telemetry_pruned",
                "retention_independent",
                "field_classification",
                "replay_fields",
                "promotion_fields",
                "reason_code",
                "explanation",
                "timestamp",
            }.issubset(classification_payload.keys())
        )

        derivability_report = derivability_reports()[0]
        derivability_payload = derivability_report.to_dict()
        self.assertTrue(
            {
                "record_id",
                "storage_class",
                "replay_applicable",
                "replay_state_derived_from_canonical",
                "promotion_applicable",
                "promotion_state_derived_from_canonical",
                "offending_fields",
                "reason_code",
                "explanation",
                "timestamp",
            }.issubset(derivability_payload.keys())
        )

    def test_bead_records_cover_both_authoritative_and_telemetry_surfaces(self) -> None:
        record_ids = {record.record_id for record in RECORD_DEFINITIONS}
        self.assertIn("research_run", record_ids)
        self.assertIn("candidate_bundle", record_ids)
        self.assertIn("bundle_readiness_record", record_ids)
        self.assertIn("deployment_instance", record_ids)
        self.assertIn("release_certification", record_ids)
        self.assertIn("release_correction_event", record_ids)
        self.assertIn("promotion_packet", record_ids)
        self.assertIn("session_readiness_packet", record_ids)
        self.assertIn("run_metrics", record_ids)
        self.assertIn("diagnostics", record_ids)


if __name__ == "__main__":
    unittest.main()
