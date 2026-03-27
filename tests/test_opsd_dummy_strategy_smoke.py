from __future__ import annotations

import json
import subprocess  # nosec B404 - trusted repo-local smoke script
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_dummy_strategy_smoke.py"
FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "opsd_dummy_strategy_cases.json"
)


def load_cases() -> list[dict[str, str]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        {
            "scenario": str(case["scenario"]),
            "expected_final_status": str(case["expected_final_status"]),
            "expected_final_reason_code": str(case["expected_final_reason_code"]),
            "expected_kernel_disposition": str(case["expected_kernel_disposition"]),
            "expected_readiness_status": str(case["expected_readiness_status"]),
            "expected_readiness_reason_code": str(case["expected_readiness_reason_code"]),
            "expected_risk_status": str(case["expected_risk_status"]),
            "expected_paper_route_outcome": str(case["expected_paper_route_outcome"]),
            "expected_shadow_route_outcome": str(case["expected_shadow_route_outcome"]),
            "expected_next_session_eligibility": str(case["expected_next_session_eligibility"]),
            "expected_reset_reason_code": str(case["expected_reset_reason_code"]),
            "expected_broker_reconnect_observed": str(
                case["expected_broker_reconnect_observed"]
            ).lower(),
            "expected_shadow_broker_artifact_delta": str(
                case["expected_shadow_broker_artifact_delta"]
            ),
            "expected_operational_evidence_record_count": str(
                case["expected_operational_evidence_record_count"]
            ),
        }
        for case in payload["scenario_cases"]
    ]


def parse_smoke_output(stdout: str) -> tuple[dict[str, dict[str, str]], Path]:
    records: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    artifact_root: Path | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "scenario":
            current = {"scenario": value}
            records[value] = current
            continue
        if key == "artifact_root":
            artifact_root = Path(value)
            continue
        if current is not None:
            current[key] = value
    if artifact_root is None:
        raise AssertionError("smoke output did not include artifact_root")
    return records, artifact_root


class OpsdDummyStrategySmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_fixture_scenarios_and_writes_artifacts(self) -> None:
        result = subprocess.run(  # nosec B603 - trusted repo-local smoke script
            [sys.executable, str(SMOKE_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        records, artifact_root = parse_smoke_output(result.stdout)
        self.assertTrue(artifact_root.exists())

        for case in load_cases():
            with self.subTest(scenario=case["scenario"]):
                record = records[case["scenario"]]
                self.assertEqual(case["expected_final_status"], record["final_status"])
                self.assertEqual(
                    case["expected_final_reason_code"], record["final_reason_code"]
                )
                self.assertEqual(
                    case["expected_kernel_disposition"], record["kernel_disposition"]
                )
                self.assertEqual(
                    case["expected_readiness_status"], record["readiness_status"]
                )
                self.assertEqual(
                    case["expected_readiness_reason_code"],
                    record["readiness_reason_code"],
                )
                self.assertEqual(case["expected_risk_status"], record["risk_status"])
                self.assertEqual(
                    case["expected_paper_route_outcome"],
                    record["paper_route_outcome"],
                )
                self.assertEqual(
                    case["expected_shadow_route_outcome"],
                    record["shadow_route_outcome"],
                )
                self.assertEqual(
                    case["expected_next_session_eligibility"],
                    record["next_session_eligibility"],
                )
                self.assertEqual(
                    case["expected_reset_reason_code"], record["reset_reason_code"]
                )
                self.assertEqual(
                    case["expected_broker_reconnect_observed"],
                    record["broker_reconnect_observed"],
                )
                self.assertEqual(
                    case["expected_shadow_broker_artifact_delta"],
                    record["shadow_broker_artifact_delta"],
                )
                self.assertEqual(
                    case["expected_operational_evidence_record_count"],
                    record["operational_evidence_record_count"],
                )

                scenario_dir = artifact_root / case["scenario"]
                self.assertTrue((scenario_dir / "dummy_strategy_summary.txt").exists())
                self.assertTrue((scenario_dir / "correlated_log.txt").exists())
                self.assertTrue((scenario_dir / "reason_bundle.txt").exists())
                self.assertTrue((scenario_dir / "kernel_binding.txt").exists())
                self.assertTrue(
                    (scenario_dir / "broker_reconnect_observation.txt").exists()
                )
                self.assertTrue((scenario_dir / "reconciliation_summary.txt").exists())
                self.assertTrue(
                    (scenario_dir / "live_bar" / "live_bar_report.txt").exists()
                )
                self.assertTrue(
                    (scenario_dir / "runtime_risk" / "runtime_risk_report.txt").exists()
                )
                self.assertTrue(
                    (scenario_dir / "readiness" / "session_readiness_packet.txt").exists()
                )
                self.assertTrue(
                    (scenario_dir / "paper_route" / "route_mode_report.txt").exists()
                )

                summary_text = (
                    scenario_dir / "dummy_strategy_summary.txt"
                ).read_text(encoding="utf-8")
                self.assertIn(
                    f"final_status={case['expected_final_status']}", summary_text
                )
                self.assertIn(
                    f"final_reason_code={case['expected_final_reason_code']}",
                    summary_text,
                )
                reason_bundle_text = (
                    scenario_dir / "reason_bundle.txt"
                ).read_text(encoding="utf-8")
                self.assertTrue(reason_bundle_text.strip())

                if int(case["expected_operational_evidence_record_count"]) > 0:
                    self.assertTrue(
                        (
                            scenario_dir
                            / "archive"
                            / "operational_evidence_manifest.txt"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            scenario_dir
                            / "archive"
                            / "operational_evidence_query_results.txt"
                        ).exists()
                    )
                    self.assertTrue(
                        (scenario_dir / "shadow_route" / "route_mode_report.txt").exists()
                    )


if __name__ == "__main__":
    unittest.main()
