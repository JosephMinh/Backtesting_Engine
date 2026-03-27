from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
BINDING_TARGET_ROOT = REPO_ROOT / "target" / "python-bindings"
BINDING_CARGO_TARGET_DIR = BINDING_TARGET_ROOT / "cargo-target"
BINDING_TMPDIR = BINDING_TARGET_ROOT / "tmp"


class KernelBindingError(RuntimeError):
    """Raised when the Python binding cannot execute or validate the Rust kernel."""


@dataclass(frozen=True)
class BoundKernelIdentity:
    strategy_family_id: str
    rust_crate: str
    python_binding_module: str
    kernel_abi_version: str
    state_serialization_version: str
    semantic_version: str
    canonical_digest: str


@dataclass(frozen=True)
class BoundDecision:
    sequence_number: int
    disposition: str
    score_ticks: int


@dataclass(frozen=True)
class BoundKernelRun:
    entry_path: str
    identity: BoundKernelIdentity
    lookback_bars: int
    threshold_ticks: int
    decisions: tuple[BoundDecision, ...]


def rust_subprocess_env() -> dict[str, str]:
    BINDING_CARGO_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    BINDING_TMPDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(BINDING_CARGO_TARGET_DIR)
    env["TMPDIR"] = str(BINDING_TMPDIR)
    return env


def decode_json_object(raw: str, *, context: str) -> dict[str, object]:
    try:
        payload = json.JSONDecoder().decode(raw)
    except json.JSONDecodeError as exc:
        raise KernelBindingError(f"{context} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise KernelBindingError(f"{context} did not return a JSON object")
    return payload


def run_gold_momentum(
    closes: list[int] | tuple[int, ...],
    *,
    lookback_bars: int,
    threshold_ticks: int,
    expected_abi_version: str = "abi_v2",
    expected_state_version: str = "state_v2",
) -> BoundKernelRun:
    if lookback_bars <= 0:
        raise KernelBindingError("lookback_bars must be positive")
    if threshold_ticks < 0:
        raise KernelBindingError("threshold_ticks must be non-negative")
    if not closes:
        raise KernelBindingError("at least one close tick is required")

    payload = _run_bridge(
        [
            "--lookback-bars",
            str(lookback_bars),
            "--threshold-ticks",
            str(threshold_ticks),
            "--closes",
            ",".join(str(int(close)) for close in closes),
            "--json",
        ]
    )
    identity = BoundKernelIdentity(**payload["identity"])
    if identity.kernel_abi_version != expected_abi_version:
        raise KernelBindingError(
            f"kernel ABI mismatch: expected {expected_abi_version}, got {identity.kernel_abi_version}"
        )
    if identity.state_serialization_version != expected_state_version:
        raise KernelBindingError(
            "kernel state serialization mismatch: "
            f"expected {expected_state_version}, got {identity.state_serialization_version}"
        )
    decisions = tuple(BoundDecision(**decision) for decision in payload["decisions"])
    return BoundKernelRun(
        entry_path=str(payload["entry_path"]),
        identity=identity,
        lookback_bars=int(payload["lookback_bars"]),
        threshold_ticks=int(payload["threshold_ticks"]),
        decisions=decisions,
    )


def _run_bridge(args: list[str]) -> dict[str, object]:
    command = [
        "cargo",
        "run",
        "-p",
        "backtesting-engine-kernels",
        "--bin",
        "gold_momentum_binding_bridge",
        "--",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=rust_subprocess_env(),
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "binding bridge failed"
        raise KernelBindingError(stderr)
    return decode_json_object(result.stdout, context="binding bridge")
