from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.runtime_recovery import (
    DegradationAssessment,
    GracefulShutdownRecord,
    LedgerCloseArtifact,
    RecoveryFenceRequest,
    RestoreDrillArtifact,
    validate_degradation_assessment,
    validate_graceful_shutdown,
    validate_ledger_close,
    validate_recovery_fence,
    validate_restore_drill,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "runtime_recovery_cases.json"
)


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def build_recovery(payload: dict[str, object]) -> RecoveryFenceRequest:
    return RecoveryFenceRequest.from_dict(payload)


def build_shutdown(payload: dict[str, object]) -> GracefulShutdownRecord:
    return GracefulShutdownRecord.from_dict(payload)


def build_degradation(payload: dict[str, object]) -> DegradationAssessment:
    return DegradationAssessment.from_dict(payload)


def build_ledger_close(payload: dict[str, object]) -> LedgerCloseArtifact:
    return LedgerCloseArtifact.from_dict(payload)


def build_restore(payload: dict[str, object]) -> RestoreDrillArtifact:
    return RestoreDrillArtifact.from_dict(payload)


def reports_for_group(
    fixture: dict[str, object],
    group_name: str,
    case_id: str | None,
) -> list[dict[str, object]]:
    cases = fixture[group_name]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]

    reports: list[dict[str, object]] = []
    for case in cases:
        if group_name == "recovery_fence_cases":
            reports.append(
                validate_recovery_fence(
                    case["case_id"],
                    build_recovery(case["payload"]),
                ).to_dict()
            )
        elif group_name == "graceful_shutdown_cases":
            reports.append(
                validate_graceful_shutdown(
                    case["case_id"],
                    build_shutdown(case["payload"]),
                ).to_dict()
            )
        elif group_name == "degradation_cases":
            reports.append(
                validate_degradation_assessment(
                    case["case_id"],
                    build_degradation(case["payload"]),
                ).to_dict()
            )
        elif group_name == "ledger_close_cases":
            reports.append(
                validate_ledger_close(
                    case["case_id"],
                    build_ledger_close(case["payload"]),
                ).to_dict()
            )
        elif group_name == "restore_drill_cases":
            reports.append(
                validate_restore_drill(
                    case["case_id"],
                    build_restore(case["payload"]),
                ).to_dict()
            )
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.11 runtime recovery smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named runtime-recovery case instead of the full fixture set.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    grouped_reports = {
        "recovery_fence_reports": reports_for_group(
            fixture,
            "recovery_fence_cases",
            args.case_id,
        ),
        "graceful_shutdown_reports": reports_for_group(
            fixture,
            "graceful_shutdown_cases",
            args.case_id,
        ),
        "degradation_reports": reports_for_group(
            fixture,
            "degradation_cases",
            args.case_id,
        ),
        "ledger_close_reports": reports_for_group(
            fixture,
            "ledger_close_cases",
            args.case_id,
        ),
        "restore_drill_reports": reports_for_group(
            fixture,
            "restore_drill_cases",
            args.case_id,
        ),
    }
    if args.case_id is not None and not any(grouped_reports.values()):
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(grouped_reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
