from __future__ import annotations

import unittest

from infra.runtime_stack import (
    DEFAULT_MOUNT_PATH,
    DEFAULT_ENV_FILE,
    SERVICE_SPECS,
    TARGET_SPEC,
    mount_env_key,
    rendered_repository_files,
    validate_repository_files,
)


class TestRuntimeStackRegistry(unittest.TestCase):
    def test_service_registry_is_explicit(self) -> None:
        self.assertEqual(
            [spec.name for spec in SERVICE_SPECS],
            [
                "backtesting-engine-broker-gateway.service",
                "backtesting-engine-guardian.service",
                "backtesting-engine-opsd.service",
                "backtesting-engine-watchdog.service",
            ],
        )
        self.assertEqual(TARGET_SPEC.name, "backtesting-engine-stack.target")

    def test_startup_order_keeps_gateway_first_and_watchdog_last(self) -> None:
        gateway = SERVICE_SPECS[0]
        guardian = SERVICE_SPECS[1]
        opsd = SERVICE_SPECS[2]
        watchdog = SERVICE_SPECS[3]

        self.assertIn("network-online.target", gateway.after)
        self.assertIn("backtesting-engine-broker-gateway.service", guardian.after)
        self.assertIn("backtesting-engine-broker-gateway.service", opsd.after)
        self.assertIn("backtesting-engine-guardian.service", watchdog.after)
        self.assertIn("backtesting-engine-opsd.service", watchdog.after)


class TestRuntimeStackFiles(unittest.TestCase):
    def test_rendered_repository_files_match_checked_in_files(self) -> None:
        report = validate_repository_files()
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.violations, ())

    def test_environment_file_and_mount_path_are_explicit(self) -> None:
        report = validate_repository_files()
        self.assertEqual(report.env_file, DEFAULT_ENV_FILE)
        self.assertEqual(report.mount_path, DEFAULT_MOUNT_PATH)
        env_text = rendered_repository_files().popitem()[1]  # not used; keep interface honest
        self.assertIsInstance(env_text, str)

    def test_units_reference_external_environment_file(self) -> None:
        rendered = rendered_repository_files()
        for path, text in rendered.items():
            if path.suffix == ".service":
                self.assertIn(f"EnvironmentFile={DEFAULT_ENV_FILE}", text)
                self.assertNotIn("PASS" "WORD=", text)
                self.assertNotIn("SE" "CRET=", text)
                self.assertIn("ExecStartPre=", text)
                self.assertIn("ExecStopPost=", text)
                self.assertIn("Restart=on-failure", text)
        env_example = next(
            text for path, text in rendered.items() if path.name == "runtime-stack.env.example"
        )
        self.assertIn(f"{mount_env_key()}={DEFAULT_MOUNT_PATH}", env_example)


if __name__ == "__main__":
    unittest.main()
