from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess  # nosec B404 - trusted repo-local validation script
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "runbook_validation_smoke.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("runbook_validation_smoke", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise AssertionError("failed to load runbook validation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_last_json_object(payload: str, *, label: str) -> dict[str, object]:
    for raw_line in reversed(payload.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = json.JSONDecoder().decode(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise AssertionError(f"{label} did not emit a final JSON object")


def extract_artifact_root(stdout: str) -> Path:
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("artifact_root="):
            return Path(line.split("=", 1)[1])
    raise AssertionError("script output did not include artifact_root=...")


class RunbookValidationTests(unittest.TestCase):
    def test_runbook_specs_validate_documented_command_paths(self) -> None:
        module = load_script_module()
        results = module.validate_runbooks()

        self.assertEqual(9, len(results))
        self.assertTrue(all(result["status"] == "pass" for result in results))
        self.assertEqual(
            {
                "runtime_startup",
                "session_readiness_review",
                "shadow_paper_review",
                "guardian_emergency_actions",
                "reconciliation_response",
                "restore_recovery",
                "migration_rehearsal",
                "incident_escalation",
                "restore_drill_baseline",
            },
            {result["runbook_id"] for result in results},
        )

    def test_validation_smoke_runs_representative_path_and_writes_report(self) -> None:
        module = load_script_module()
        env = os.environ.copy()
        env["TMPDIR"] = str(module.SAFE_TMPDIR)
        env["TMP"] = str(module.SAFE_TMPDIR)
        env["TEMP"] = str(module.SAFE_TMPDIR)
        env["CARGO_TARGET_DIR"] = str(module.SAFE_TMPDIR / "backtesting-engine-cargo-target")
        env["PYTHONPATH"] = str(REPO_ROOT)

        with tempfile.TemporaryDirectory(dir=str(module.SAFE_TMPDIR)) as output_dir:
            result = subprocess.run(  # nosec B603 - trusted repo-local validation script
                [sys.executable, str(SCRIPT_PATH), "--output-dir", output_dir],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            parsed = decode_last_json_object(result.stdout, label="runbook validation stdout")
            self.assertEqual("pass", parsed["status"])
            self.assertEqual(9, len(parsed["runbooks"]))
            self.assertEqual("pass", parsed["representative_path"]["status"])
            readiness_step = parsed["representative_path"]["steps"][1]
            self.assertEqual("broker-state-blocked", readiness_step["scenario"])
            self.assertEqual("blocked", readiness_step["status"])
            self.assertEqual("READINESS_PROVIDER_BLOCKED", readiness_step["reason_code"])
            self.assertIn(
                "restore_drill_baseline",
                {runbook["runbook_id"] for runbook in parsed["runbooks"]},
            )

            written = Path(output_dir) / "runbook_validation_report.json"
            self.assertTrue(written.exists())
            written_report = json.JSONDecoder().decode(written.read_text(encoding="utf-8"))
            self.assertEqual("pass", written_report["status"])

    def test_shell_smokes_use_unique_default_artifact_roots(self) -> None:
        module = load_script_module()
        bash = shutil.which("bash")
        if bash is None:  # pragma: no cover - defensive
            self.fail("bash is required for shell smoke regression coverage")
        scripts = [
            REPO_ROOT / "scripts" / "runtime_stack_bringup_smoke.sh",
            REPO_ROOT / "rust" / "guardian" / "scripts" / "emergency_drill.sh",
            REPO_ROOT / "rust" / "watchdog" / "scripts" / "supervision_drill.sh",
            REPO_ROOT / "rust" / "watchdog" / "scripts" / "restore_migration_smoke.sh",
            REPO_ROOT / "rust" / "watchdog" / "scripts" / "preflight_health_smoke.sh",
        ]
        with tempfile.TemporaryDirectory(dir=str(module.SAFE_TMPDIR)) as tempdir:
            fake_bin = Path(tempdir) / "fake-bin"
            fake_bin.mkdir()
            stub = "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'artifact_dir=""',
                    'prev=""',
                    'for arg in "$@"; do',
                    '  if [[ "$prev" == "--artifact-dir" ]]; then',
                    '    artifact_dir="$arg"',
                    "  fi",
                    '  prev="$arg"',
                    "done",
                    'if [[ -n "$artifact_dir" ]]; then',
                    '  mkdir -p "$artifact_dir"',
                    "fi",
                ]
            )
            for executable in ("cargo", "python3"):
                path = fake_bin / executable
                path.write_text(stub + "\n", encoding="utf-8")
                path.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
            env["TMPDIR"] = str(Path(tempdir) / "tmp")

            for script in scripts:
                first = subprocess.run(  # nosec B603 - executes trusted repo-local shell harnesses under stubbed PATH
                    [bash, str(script)],
                    cwd=REPO_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                second = subprocess.run(  # nosec B603 - executes trusted repo-local shell harnesses under stubbed PATH
                    [bash, str(script)],
                    cwd=REPO_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                first_root = extract_artifact_root(first.stdout)
                second_root = extract_artifact_root(second.stdout)
                self.assertNotEqual(
                    first_root,
                    second_root,
                    f"{script} reused the same default artifact root across invocations",
                )
                self.assertTrue(first_root.exists())
                self.assertTrue(second_root.exists())


if __name__ == "__main__":
    unittest.main()
