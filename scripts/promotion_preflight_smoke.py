from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.deployment_packets import (
    PromotionPacket,
    PromotionPreflightRequest,
    validate_promotion_packet,
    validate_promotion_preflight,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
)


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def promotion_payload_by_case(
    fixture: dict[str, object], case_id: str
) -> dict[str, object]:
    promotion_case = next(
        case for case in fixture["promotion_cases"] if case["case_id"] == case_id
    )
    return dict(promotion_case["payload"])


def build_promotion(payload: dict[str, object]) -> PromotionPacket:
    return PromotionPacket.from_dict(payload)


def build_preflight_request(
    packet: PromotionPacket, overrides: dict[str, object] | None = None
) -> PromotionPreflightRequest:
    payload: dict[str, object] = {
        "preflight_report_id": "promotion_preflight_report_default",
        "promotion_packet": packet.to_dict(),
        "resolved_artifact_ids": [
            packet.candidate_bundle_id,
            packet.bundle_readiness_record_id,
            packet.replay_certification_id,
            packet.portability_certification_id,
            packet.execution_symbol_tradability_study_id,
            packet.fee_schedule_snapshot_id,
            packet.margin_snapshot_id,
            packet.market_data_entitlement_check_id,
            *packet.active_waiver_ids,
            *packet.incident_reference_ids,
        ],
        "integrity_verified_artifact_ids": [
            packet.candidate_bundle_id,
            packet.bundle_readiness_record_id,
            packet.replay_certification_id,
            packet.portability_certification_id,
            packet.execution_symbol_tradability_study_id,
            packet.fee_schedule_snapshot_id,
            packet.margin_snapshot_id,
            packet.market_data_entitlement_check_id,
            *packet.active_waiver_ids,
            *packet.incident_reference_ids,
        ],
        "verified_compatibility_domain_ids": [
            "data_protocol",
            "strategy_protocol",
            "ops_protocol",
            "policy_bundle_hash",
            "compatibility_matrix_version",
        ],
        "stale_evidence_ids": [],
        "superseded_artifact_ids": [],
        "broker_capability_check_id": "broker_capability_preflight_default",
        "backup_freshness_check_id": "backup_freshness_preflight_default",
        "restore_drill_check_id": "restore_drill_preflight_default",
        "clock_health_check_id": "clock_health_preflight_default",
        "secret_health_check_id": "ops_health_preflight_default",
        "failed_check_ids": [],
        "correlation_id": "corr-promotion-preflight-default",
        "operator_reason_bundle": ["promotion preflight completed"],
        "signed_preflight_hash": "promotion_preflight_sha256_default",
    }
    if packet.native_validation_id:
        payload["resolved_artifact_ids"].append(packet.native_validation_id)
        payload["integrity_verified_artifact_ids"].append(packet.native_validation_id)
    if packet.paper_pass_evidence_id:
        payload["resolved_artifact_ids"].append(packet.paper_pass_evidence_id)
        payload["integrity_verified_artifact_ids"].append(packet.paper_pass_evidence_id)
    if packet.shadow_pass_evidence_id:
        payload["resolved_artifact_ids"].append(packet.shadow_pass_evidence_id)
        payload["integrity_verified_artifact_ids"].append(packet.shadow_pass_evidence_id)
    payload = deep_merge(payload, overrides or {})
    return PromotionPreflightRequest.from_dict(payload)


def promotion_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["promotion_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        validate_promotion_packet(case["case_id"], build_promotion(case["payload"])).to_dict()
        for case in cases
    ]


def preflight_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["promotion_preflight_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    reports = []
    for case in cases:
        packet = build_promotion(
            deep_merge(
                promotion_payload_by_case(fixture, case["promotion_case_id"]),
                case.get("promotion_overrides", {}),
            )
        )
        request = build_preflight_request(
            packet,
            case.get("preflight_overrides"),
        )
        reports.append(validate_promotion_preflight(case["case_id"], request).to_dict())
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.3 promotion preflight smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named promotion or promotion-preflight case instead of the full fixture set.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    grouped_reports = {
        "promotion_reports": promotion_reports(fixture, args.case_id),
        "promotion_preflight_reports": preflight_reports(fixture, args.case_id),
    }
    if args.case_id is not None and not any(grouped_reports.values()):
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(grouped_reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
