from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_route_mode_smoke.py"
FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "opsd_route_mode_cases.json"
)


def load_cases() -> list[dict[str, str]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        {
            "scenario": str(case["scenario"]),
            "expected_route_mode": str(case["expected_route_mode"]),
            "expected_outcome": str(case["expected_outcome"]),
            "expected_reason_code": str(case["expected_reason_code"]),
            "expected_route_target": str(case["expected_route_target"]),
            "expected_economic_mutation_permitted": str(
                case["expected_economic_mutation_permitted"]
            ).lower(),
            "expected_duplicate_prevented": str(
                case["expected_duplicate_prevented"]
            ).lower(),
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


class OpsdRouteModeSmokeTest(unittest.TestCase):
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
                self.assertEqual(case["expected_route_mode"], record["route_mode"])
                self.assertEqual(case["expected_outcome"], record["outcome"])
                self.assertEqual(case["expected_reason_code"], record["reason_code"])
                self.assertEqual(case["expected_route_target"], record["route_target"])
                self.assertEqual(
                    case["expected_economic_mutation_permitted"],
                    record["economic_mutation_permitted"],
                )
                self.assertEqual(
                    case["expected_duplicate_prevented"],
                    record["duplicate_prevented"],
                )
                scenario_dir = artifact_root / case["scenario"]
                request_artifact = scenario_dir / "route_mode_request.txt"
                report_artifact = scenario_dir / "route_mode_report.txt"
                manifest_artifact = scenario_dir / "route_mode_manifest.txt"
                self.assertTrue(request_artifact.exists())
                self.assertTrue(report_artifact.exists())
                self.assertTrue(manifest_artifact.exists())
                report_text = report_artifact.read_text(encoding="utf-8")
                self.assertIn(f"outcome={case['expected_outcome']}", report_text)
                self.assertIn(
                    f"reason_code={case['expected_reason_code']}",
                    report_text,
                )


if __name__ == "__main__":
    unittest.main()
