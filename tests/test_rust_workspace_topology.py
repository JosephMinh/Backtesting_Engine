from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from python.bindings import BINDING_PACKAGE_CONTRACT


ROOT = Path(__file__).resolve().parents[1]
CARGO_MANIFEST = ROOT / "Cargo.toml"
EXPECTED_MEMBERS = (
    "rust/kernels",
    "rust/opsd",
    "rust/guardian",
    "rust/watchdog",
)
EXPECTED_PACKAGES = {
    "rust/kernels": "backtesting-engine-kernels",
    "rust/opsd": "backtesting-engine-opsd",
    "rust/guardian": "backtesting-engine-guardian",
    "rust/watchdog": "backtesting-engine-watchdog",
}


def _load_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text())


class RustWorkspaceTopologyTest(unittest.TestCase):
    def test_root_workspace_declares_expected_members(self) -> None:
        manifest = _load_toml(CARGO_MANIFEST)
        workspace = manifest["workspace"]
        self.assertEqual(list(EXPECTED_MEMBERS), workspace["members"])
        self.assertEqual("2", workspace["resolver"])

    def test_workspace_metadata_declares_shared_entrypoints(self) -> None:
        manifest = _load_toml(CARGO_MANIFEST)
        metadata = manifest["workspace"]["metadata"]["backtesting_engine"]
        self.assertEqual("python/bindings", metadata["python_bindings_package"])
        self.assertEqual("cargo check --workspace", metadata["build_entrypoint"])
        self.assertEqual("cargo fmt --all --check", metadata["format_entrypoint"])
        self.assertEqual(
            "cargo clippy --workspace --all-targets -- -D warnings",
            metadata["lint_entrypoint"],
        )
        self.assertEqual("cargo test --workspace", metadata["test_entrypoint"])

    def test_crate_manifests_match_expected_workspace_roles(self) -> None:
        manifest = _load_toml(CARGO_MANIFEST)
        roles = manifest["workspace"]["metadata"]["backtesting_engine"]["crate_responsibilities"]
        for member in EXPECTED_MEMBERS:
            with self.subTest(member=member):
                crate_manifest = _load_toml(ROOT / member / "Cargo.toml")
                self.assertEqual(EXPECTED_PACKAGES[member], crate_manifest["package"]["name"])
                self.assertEqual("src/lib.rs", crate_manifest["lib"]["path"])
                self.assertFalse(crate_manifest["package"]["publish"])
                self.assertTrue(crate_manifest["lints"]["workspace"])
                self.assertIn(member, roles)

    def test_opsd_depends_on_kernels_and_other_operational_crates_stay_independent(self) -> None:
        opsd_manifest = _load_toml(ROOT / "rust/opsd/Cargo.toml")
        self.assertEqual(
            {"path": "../kernels"},
            opsd_manifest["dependencies"]["backtesting-engine-kernels"],
        )
        guardian_manifest = _load_toml(ROOT / "rust/guardian/Cargo.toml")
        watchdog_manifest = _load_toml(ROOT / "rust/watchdog/Cargo.toml")
        self.assertNotIn("dependencies", guardian_manifest)
        self.assertNotIn("dependencies", watchdog_manifest)

    def test_binding_package_contract_points_to_kernel_member(self) -> None:
        self.assertEqual("python/bindings", BINDING_PACKAGE_CONTRACT.package_root)
        self.assertEqual("rust/kernels", BINDING_PACKAGE_CONTRACT.rust_workspace_member)
        self.assertEqual("python.bindings._kernels", BINDING_PACKAGE_CONTRACT.future_extension_module)
        self.assertTrue((ROOT / BINDING_PACKAGE_CONTRACT.package_root / "__init__.py").exists())
