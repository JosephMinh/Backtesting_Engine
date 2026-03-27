from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from python.bindings import BINDING_PACKAGE_CONTRACT


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MEMBERS = [
    "rust/kernels",
    "rust/opsd",
    "rust/guardian",
    "rust/watchdog",
]


def _load_workspace_manifest() -> dict[str, object]:
    return tomllib.loads((ROOT / "Cargo.toml").read_text())


def main() -> int:
    manifest = _load_workspace_manifest()
    workspace = manifest["workspace"]
    members = workspace["members"]
    if members != EXPECTED_MEMBERS:
        print(f"unexpected workspace members: {members!r}", file=sys.stderr)
        return 1

    metadata = workspace["metadata"]["backtesting_engine"]
    cargo_binary = shutil.which("cargo")
    if cargo_binary is None:
        print("cargo executable not found on PATH", file=sys.stderr)
        return 1
    metadata_result = subprocess.run(
        [cargo_binary, "metadata", "--no-deps", "--format-version", "1"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if metadata_result.returncode != 0:
        print(metadata_result.stderr, file=sys.stderr)
        return metadata_result.returncode

    try:
        metadata_payload = json.loads(metadata_result.stdout)
    except json.JSONDecodeError as exc:
        print(f"cargo metadata returned invalid JSON: {exc}", file=sys.stderr)
        return 1
    package_names = sorted(package["name"] for package in metadata_payload["packages"])

    print("Rust workspace smoke summary")
    print(f"bindings package: {BINDING_PACKAGE_CONTRACT.package_root}")
    print(f"future extension module: {BINDING_PACKAGE_CONTRACT.future_extension_module}")
    print(f"workspace members: {', '.join(members)}")
    print(f"cargo packages: {', '.join(package_names)}")
    print(f"build entrypoint: {metadata['build_entrypoint']}")
    print(f"lint entrypoint: {metadata['lint_entrypoint']}")
    print(f"test entrypoint: {metadata['test_entrypoint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
