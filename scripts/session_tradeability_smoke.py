from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.deployment_packets import (
    SessionReadinessPacket,
    SessionTradeabilityRequest,
    validate_session_readiness_packet,
    validate_session_tradeability,
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


def session_payload_by_case(fixture: dict[str, object], case_id: str) -> dict[str, object]:
    session_case = next(
        case for case in fixture["session_cases"] if case["case_id"] == case_id
    )
    return dict(session_case["payload"])


def build_session(payload: dict[str, object]) -> SessionReadinessPacket:
    return SessionReadinessPacket.from_dict(payload)


def build_tradeability_request(
    packet: SessionReadinessPacket, overrides: dict[str, object] | None = None
) -> SessionTradeabilityRequest:
    payload: dict[str, object] = {
        "tradeability_gate_id": "session_tradeability_gate_default",
        "session_packet": packet.to_dict(),
        "active_deployment_instance_id": packet.deployment_instance_id,
        "active_promotion_packet_id": packet.source_promotion_packet_id,
        "current_session_id": packet.session_id,
        "evaluated_at_utc": packet.valid_from_utc,
        "stale_check_ids": [],
        "failed_check_ids": [],
        "correlation_id": "corr-session-tradeability-default",
        "operator_reason_bundle": ["session tradeability gate evaluated"],
        "signed_gate_hash": "session_tradeability_sha256_default",
    }
    payload = deep_merge(payload, overrides or {})
    return SessionTradeabilityRequest.from_dict(payload)


def session_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["session_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        validate_session_readiness_packet(
            case["case_id"],
            build_session(case["payload"]),
        ).to_dict()
        for case in cases
    ]


def tradeability_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["session_tradeability_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    reports = []
    for case in cases:
        session_packet = build_session(
            deep_merge(
                session_payload_by_case(fixture, case["session_case_id"]),
                case.get("session_overrides", {}),
            )
        )
        request = build_tradeability_request(
            session_packet,
            case.get("request_overrides"),
        )
        reports.append(validate_session_tradeability(case["case_id"], request).to_dict())
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.4 session readiness and tradeability smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named session or tradeability case instead of the full fixture set.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    grouped_reports = {
        "session_reports": session_reports(fixture, args.case_id),
        "session_tradeability_reports": tradeability_reports(fixture, args.case_id),
    }
    if args.case_id is not None and not any(grouped_reports.values()):
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(grouped_reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
