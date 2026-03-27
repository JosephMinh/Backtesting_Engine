from __future__ import annotations

from pathlib import Path
import shutil
import subprocess  # nosec B404 - deterministic local cargo invocation for repo smoke validation
import sys


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("startup-handoff", "mailbox-backpressure")


def _run_scenario(scenario: str) -> dict[str, str]:
    cargo_binary = shutil.which("cargo")
    if cargo_binary is None:
        raise RuntimeError("cargo executable not found on PATH")
    try:
        result = subprocess.run(  # nosec B603 - fixed executable path and fixed argument vector
            [
                cargo_binary,
                "run",
                "-p",
                "backtesting-engine-opsd",
                "--",
                "--scenario",
                scenario,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or exc.stdout.strip()) from exc
    parsed: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        key, separator, value = line.partition("=")
        if separator != "=":
            raise RuntimeError(f"unexpected output line: {line!r}")
        parsed[key] = value
    return parsed


def main() -> int:
    startup = _run_scenario("startup-handoff")
    if startup["scenario"] != "startup_handoff":
        print(f"unexpected startup scenario marker: {startup!r}", file=sys.stderr)
        return 1
    if startup["broker_drain_order"] != "cancel_open_orders,health_probe":
        print(f"unexpected broker drain order: {startup!r}", file=sys.stderr)
        return 1
    if startup["reconciliation_tick"] != "reconciliation:reconciliation_tick:high":
        print(f"unexpected reconciliation routing: {startup!r}", file=sys.stderr)
        return 1

    overflow = _run_scenario("mailbox-backpressure")
    if overflow["scenario"] != "mailbox_backpressure":
        print(f"unexpected backpressure scenario marker: {overflow!r}", file=sys.stderr)
        return 1
    if overflow["mailbox_owner"] != "broker":
        print(f"unexpected backpressure owner: {overflow!r}", file=sys.stderr)
        return 1
    if overflow["priority"] != "high":
        print(f"unexpected backpressure priority: {overflow!r}", file=sys.stderr)
        return 1
    if overflow["message_kind"] != "flatten_positions":
        print(f"unexpected overflow message kind: {overflow!r}", file=sys.stderr)
        return 1

    print("opsd runtime smoke summary")
    print(f"scenarios: {', '.join(SCENARIOS)}")
    print(f"startup modules: {startup['booted_modules']}")
    print(f"startup dispatch count: {startup['dispatch_count']}")
    print(f"backpressure target: {overflow['mailbox_owner']}")
    print(f"backpressure depth/capacity: {overflow['depth']}/{overflow['capacity']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
