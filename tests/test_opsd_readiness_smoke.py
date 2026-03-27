from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "opsd_readiness_smoke.py"
FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "opsd_readiness_cases.json"
)


def load_cases() -> list[dict[str, str]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        {
            "scenario": str(case["scenario"]),
            "expected_status": str(case["expected_status"]),
            "expected_reason_code": str(case["expected_reason_code"]),
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


class OpsdReadinessSmokeTest(unittest.TestCase):
    def test_smoke_script_exercises_fixture_scenarios_and_writes_artifacts(self) -> None:
        result = subprocess.run(
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
                self.assertEqual(case["expected_status"], record["status"])
                self.assertEqual(
                    case["expected_reason_code"], record["reason_code"]
                )
                scenario_dir = artifact_root / case["scenario"]
                request_artifact = scenario_dir / "session_readiness_request.txt"
                packet_artifact = scenario_dir / "session_readiness_packet.txt"
                self.assertTrue(request_artifact.exists())
                self.assertTrue(packet_artifact.exists())
                packet_text = packet_artifact.read_text(encoding="utf-8")
                self.assertIn(f"status={case['expected_status']}", packet_text)
                self.assertIn(
                    f"reason_code={case['expected_reason_code']}", packet_text
                )


if __name__ == "__main__":
    unittest.main()
