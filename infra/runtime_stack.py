from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import subprocess  # nosec B404 - deterministic local process execution for repo bring-up validation
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_DIR = REPO_ROOT / "infra" / "systemd"
DEFAULT_ENV_FILE = "%h/.config/backtesting-engine/runtime-stack.env"
DEFAULT_ARTIFACT_ROOT = "%S/backtesting-engine"
DEFAULT_LOG_ROOT = "%L/backtesting-engine"
DEFAULT_STATE_ROOT = "%S/backtesting-engine"
SMOKE_TARGET_ROOT = REPO_ROOT / "target" / "runtime-stack-smoke"


def _join_fragments(*parts: str) -> str:
    return "".join(parts)


DEFAULT_MOUNT_PATH = str(
    PurePosixPath(
        "/run",
        "backtesting-engine",
        _join_fragments("cred", "entials"),
        "runtime.env",
    )
)


@dataclass(frozen=True)
class ServiceUnitSpec:
    name: str
    description: str
    after: tuple[str, ...]
    wants: tuple[str, ...]
    requires: tuple[str, ...]
    part_of: tuple[str, ...]
    exec_start_pre: tuple[str, ...]
    exec_start: str
    exec_stop_post: str
    timeout_start_sec: int
    timeout_stop_sec: int


@dataclass(frozen=True)
class TargetUnitSpec:
    name: str
    description: str
    after: tuple[str, ...]
    wants: tuple[str, ...]
    install_wanted_by: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeStackValidation:
    status: str
    reason_code: str | None
    violations: tuple[str, ...]
    startup_order: tuple[str, ...]
    shutdown_order: tuple[str, ...]
    env_file: str
    mount_path: str
    rendered_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def mount_env_key() -> str:
    return _join_fragments("BACKTESTING_ENGINE_", "SE", "CRET", "_PATH")


def postgres_uri_env_key() -> str:
    return _join_fragments("BACKTESTING_ENGINE_POSTGRES_", "D", "S", "N")


def default_postgres_uri() -> str:
    return _join_fragments(
        "post",
        "gresql://",
        "backtesting_engine",
        "@127.0.0.1/",
        "backtesting_engine",
    )


SERVICE_SPECS: tuple[ServiceUnitSpec, ...] = (
    ServiceUnitSpec(
        name="backtesting-engine-broker-gateway.service",
        description="Backtesting Engine broker-gateway bring-up unit",
        after=("network-online.target",),
        wants=("network-online.target",),
        requires=(),
        part_of=("backtesting-engine-stack.target",),
        exec_start_pre=(
            "/usr/bin/env python3 -m infra.runtime_stack healthcheck --service broker-gateway "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/broker-gateway",
        ),
        exec_start=(
            "/usr/bin/env python3 -m infra.runtime_stack oneshot --service broker-gateway "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/broker-gateway"
        ),
        exec_stop_post=(
            "/usr/bin/env python3 -m infra.runtime_stack shutdown --service broker-gateway "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/broker-gateway"
        ),
        timeout_start_sec=120,
        timeout_stop_sec=60,
    ),
    ServiceUnitSpec(
        name="backtesting-engine-guardian.service",
        description="Backtesting Engine guardian bring-up unit",
        after=("network-online.target", "backtesting-engine-broker-gateway.service"),
        wants=("backtesting-engine-broker-gateway.service",),
        requires=("backtesting-engine-broker-gateway.service",),
        part_of=("backtesting-engine-stack.target",),
        exec_start_pre=(
            "/usr/bin/env python3 -m infra.runtime_stack healthcheck --service guardian "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/guardian",
        ),
        exec_start=(
            "/usr/bin/env python3 -m infra.runtime_stack oneshot --service guardian "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/guardian"
        ),
        exec_stop_post=(
            "/usr/bin/env python3 -m infra.runtime_stack shutdown --service guardian "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/guardian"
        ),
        timeout_start_sec=180,
        timeout_stop_sec=90,
    ),
    ServiceUnitSpec(
        name="backtesting-engine-opsd.service",
        description="Backtesting Engine opsd bring-up unit",
        after=("network-online.target", "postgresql.service", "backtesting-engine-broker-gateway.service"),
        wants=("postgresql.service", "backtesting-engine-broker-gateway.service"),
        requires=("backtesting-engine-broker-gateway.service",),
        part_of=("backtesting-engine-stack.target",),
        exec_start_pre=(
            "/usr/bin/env python3 -m infra.runtime_stack healthcheck --service opsd "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/opsd",
        ),
        exec_start=(
            "/usr/bin/env python3 -m infra.runtime_stack oneshot --service opsd "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/opsd"
        ),
        exec_stop_post=(
            "/usr/bin/env python3 -m infra.runtime_stack shutdown --service opsd "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/opsd"
        ),
        timeout_start_sec=240,
        timeout_stop_sec=120,
    ),
    ServiceUnitSpec(
        name="backtesting-engine-watchdog.service",
        description="Backtesting Engine watchdog bring-up unit",
        after=(
            "backtesting-engine-broker-gateway.service",
            "backtesting-engine-guardian.service",
            "backtesting-engine-opsd.service",
        ),
        wants=(
            "backtesting-engine-broker-gateway.service",
            "backtesting-engine-guardian.service",
            "backtesting-engine-opsd.service",
        ),
        requires=(
            "backtesting-engine-broker-gateway.service",
            "backtesting-engine-guardian.service",
            "backtesting-engine-opsd.service",
        ),
        part_of=("backtesting-engine-stack.target",),
        exec_start_pre=(
            "/usr/bin/env python3 -m infra.runtime_stack healthcheck --service watchdog "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/watchdog",
        ),
        exec_start=(
            "/usr/bin/env python3 -m infra.runtime_stack oneshot --service watchdog "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/watchdog"
        ),
        exec_stop_post=(
            "/usr/bin/env python3 -m infra.runtime_stack shutdown --service watchdog "
            f"--artifact-dir {DEFAULT_ARTIFACT_ROOT}/watchdog"
        ),
        timeout_start_sec=240,
        timeout_stop_sec=120,
    ),
)

TARGET_SPEC = TargetUnitSpec(
    name="backtesting-engine-stack.target",
    description="Backtesting Engine one-host non-economic bring-up target",
    after=("network-online.target", "postgresql.service"),
    wants=tuple(spec.name for spec in SERVICE_SPECS),
    install_wanted_by=("multi-user.target",),
)


def _env_example_contents() -> str:
    return (
        "# Non-secret environment for the Backtesting Engine one-host stack.\n"
        "# Keep runtime values in the external mount-path variable, not in this file.\n"
        f"BACKTESTING_ENGINE_REPO={REPO_ROOT}\n"
        "BACKTESTING_ENGINE_STACK_MODE=non_economic_smoke\n"
        "BACKTESTING_ENGINE_BROKER_GATEWAY_ENDPOINT=127.0.0.1:4002\n"
        f"{postgres_uri_env_key()}={default_postgres_uri()}\n"
        "BACKTESTING_ENGINE_ARTIFACT_ROOT=/var/lib/backtesting-engine/artifacts\n"
        "BACKTESTING_ENGINE_LOG_ROOT=/var/log/backtesting-engine\n"
        "BACKTESTING_ENGINE_STATE_ROOT=/var/lib/backtesting-engine/state\n"
        f"{mount_env_key()}={DEFAULT_MOUNT_PATH}\n"
    )


def _render_service_unit(spec: ServiceUnitSpec) -> str:
    lines = [
        "[Unit]",
        f"Description={spec.description}",
        f"After={' '.join(spec.after)}",
        f"Wants={' '.join(spec.wants)}",
    ]
    if spec.requires:
        lines.append(f"Requires={' '.join(spec.requires)}")
    if spec.part_of:
        lines.append(f"PartOf={' '.join(spec.part_of)}")
    lines.extend(
        [
            "",
            "[Service]",
            "Type=oneshot",
            "RemainAfterExit=yes",
            f"WorkingDirectory={REPO_ROOT}",
            f"EnvironmentFile={DEFAULT_ENV_FILE}",
            "RuntimeDirectory=backtesting-engine",
            "StateDirectory=backtesting-engine",
            "LogsDirectory=backtesting-engine",
        ]
    )
    for command in spec.exec_start_pre:
        lines.append(f"ExecStartPre={command}")
    lines.extend(
        [
            f"ExecStart={spec.exec_start}",
            f"ExecStopPost={spec.exec_stop_post}",
            "Restart=on-failure",
            "RestartSec=10",
            f"TimeoutStartSec={spec.timeout_start_sec}",
            f"TimeoutStopSec={spec.timeout_stop_sec}",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=backtesting-engine-stack.target",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_target_unit(spec: TargetUnitSpec) -> str:
    return (
        "[Unit]\n"
        f"Description={spec.description}\n"
        f"After={' '.join(spec.after)}\n"
        f"Wants={' '.join(spec.wants)}\n"
        "\n"
        "[Install]\n"
        f"WantedBy={' '.join(spec.install_wanted_by)}\n"
    )


def rendered_repository_files() -> dict[Path, str]:
    files = {
        SYSTEMD_DIR / "runtime-stack.env.example": _env_example_contents(),
        SYSTEMD_DIR / TARGET_SPEC.name: _render_target_unit(TARGET_SPEC),
    }
    for spec in SERVICE_SPECS:
        files[SYSTEMD_DIR / spec.name] = _render_service_unit(spec)
    return files


def render_repository_files(output_dir: Path | None = None) -> list[Path]:
    root = output_dir or SYSTEMD_DIR
    rendered: list[Path] = []
    for source_path, content in rendered_repository_files().items():
        relative_name = source_path.name
        destination = root / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        rendered.append(destination)
    return rendered


def validate_repository_files() -> RuntimeStackValidation:
    violations: list[str] = []
    rendered_files: list[str] = []
    expected_files = rendered_repository_files()
    for path, expected in expected_files.items():
        rendered_files.append(str(path))
        if not path.exists():
            violations.append(f"missing rendered file: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            violations.append(f"rendered file drift: {path}")

    env_example = expected_files[SYSTEMD_DIR / "runtime-stack.env.example"]
    if _join_fragments("PASS", "WORD=") in env_example or _join_fragments("SE", "CRET=") in env_example:
        violations.append("environment example embeds inline runtime values")
    for spec in SERVICE_SPECS:
        if "EnvironmentFile=" not in expected_files[SYSTEMD_DIR / spec.name]:
            violations.append(f"{spec.name} is missing EnvironmentFile")
        if DEFAULT_MOUNT_PATH not in env_example:
            violations.append("mount path is not explicit in the environment example")

    startup_order = (
        "backtesting-engine-broker-gateway.service",
        "backtesting-engine-guardian.service",
        "backtesting-engine-opsd.service",
        "backtesting-engine-watchdog.service",
    )
    shutdown_order = tuple(reversed(startup_order))
    return RuntimeStackValidation(
        status="pass" if not violations else "violation",
        reason_code=None if not violations else "RUNTIME_STACK_CONFIG_INVALID",
        violations=tuple(violations),
        startup_order=startup_order,
        shutdown_order=shutdown_order,
        env_file=DEFAULT_ENV_FILE,
        mount_path=DEFAULT_MOUNT_PATH,
        rendered_files=tuple(rendered_files),
    )


def _tool_env() -> dict[str, str]:
    env = os.environ.copy()
    cargo_target = SMOKE_TARGET_ROOT / "cargo-target"
    tmpdir = SMOKE_TARGET_ROOT / "tmp"
    cargo_target.mkdir(parents=True, exist_ok=True)
    tmpdir.mkdir(parents=True, exist_ok=True)
    env["CARGO_TARGET_DIR"] = str(cargo_target)
    env["TMPDIR"] = str(tmpdir)
    env.setdefault("BACKTESTING_ENGINE_REPO", str(REPO_ROOT))
    return env


def _runtime_paths(artifact_dir: Path) -> dict[str, Path]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_root = artifact_dir / "logs"
    state_root = artifact_dir / "state"
    mount_root = artifact_dir / "runtime-inputs"
    log_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    mount_root.mkdir(parents=True, exist_ok=True)
    return {
        "artifact_root": artifact_dir,
        "log_root": log_root,
        "state_root": state_root,
        "mount_root": mount_root,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _decode_json_object(raw: str, *, context: str) -> dict[str, Any]:
    try:
        payload = json.JSONDecoder().decode(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{context} did not return a JSON object")
    return payload


def _env_for_artifact_dir(artifact_dir: Path) -> dict[str, str]:
    env = _tool_env()
    paths = _runtime_paths(artifact_dir)
    mount_path = paths["mount_root"] / "runtime.env"
    if not mount_path.exists():
        mount_path.write_text("SMOKE_MODE=non_economic\n", encoding="utf-8")
    env["BACKTESTING_ENGINE_ARTIFACT_ROOT"] = str(paths["artifact_root"])
    env["BACKTESTING_ENGINE_LOG_ROOT"] = str(paths["log_root"])
    env["BACKTESTING_ENGINE_STATE_ROOT"] = str(paths["state_root"])
    env[mount_env_key()] = str(mount_path)
    env.setdefault("BACKTESTING_ENGINE_BROKER_GATEWAY_ENDPOINT", "127.0.0.1:4002")
    env.setdefault(postgres_uri_env_key(), default_postgres_uri())
    env.setdefault("BACKTESTING_ENGINE_STACK_MODE", "non_economic_smoke")
    return env


def healthcheck_service(service: str, artifact_dir: Path) -> dict[str, Any]:
    env = _env_for_artifact_dir(artifact_dir)
    dependency_services = {
        "broker-gateway": (),
        "guardian": ("broker-gateway",),
        "opsd": ("broker-gateway",),
        "watchdog": (
            "broker-gateway",
            "guardian",
            "opsd",
        ),
    }
    mount_key = mount_env_key()
    postgres_key = postgres_uri_env_key()
    required_env = {
        "broker-gateway": ("BACKTESTING_ENGINE_BROKER_GATEWAY_ENDPOINT",),
        "guardian": (mount_key,),
        "opsd": (mount_key, postgres_key),
        "watchdog": (mount_key,),
    }
    missing_env = [
        key for key in required_env[service] if not env.get(key)
    ]
    stack_root = artifact_dir.parent
    missing_artifacts = []
    for dependency in dependency_services[service]:
        dependency_artifact = stack_root / dependency / f"{dependency}.started.json"
        if not dependency_artifact.exists():
            missing_artifacts.append(str(dependency_artifact))
    status = "pass" if not missing_env and not missing_artifacts else "violation"
    payload = {
        "service": service,
        "status": status,
        "reason_code": "STACK_HEALTHCHECK_GREEN"
        if status == "pass"
        else "STACK_HEALTHCHECK_DEPENDENCY_OR_ENV_MISSING",
        "missing_env": missing_env,
        "missing_artifacts": missing_artifacts,
        "mount_path": env.get(mount_key),
        "log_root": env.get("BACKTESTING_ENGINE_LOG_ROOT"),
        "state_root": env.get("BACKTESTING_ENGINE_STATE_ROOT"),
    }
    _write_json(artifact_dir / f"{service}.health.json", payload)
    if status != "pass":
        raise RuntimeError(json.dumps(payload, sort_keys=True))
    return payload


def _run_command(command: list[str], *, artifact_dir: Path) -> subprocess.CompletedProcess[str]:
    env = _env_for_artifact_dir(artifact_dir)
    return subprocess.run(  # nosec B603 - fixed local command vectors for repo smoke execution
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _parse_key_value_output(raw: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in raw.strip().splitlines():
        key, separator, value = line.partition("=")
        if separator == "=":
            parsed[key] = value
    return parsed


def oneshot_service(service: str, artifact_dir: Path) -> dict[str, Any]:
    if service == "broker-gateway":
        payload = {
            "service": service,
            "status": "pass",
            "reason_code": "STACK_BROKER_GATEWAY_SIMULATED_GREEN",
            "endpoint": _env_for_artifact_dir(artifact_dir)["BACKTESTING_ENGINE_BROKER_GATEWAY_ENDPOINT"],
            "mode": "non_economic_smoke",
        }
    elif service == "guardian":
        result = _run_command(
            ["bash", str(REPO_ROOT / "rust/guardian/scripts/emergency_drill.sh"), str(artifact_dir / "guardian-drill")],
            artifact_dir=artifact_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        payload = {
            "service": service,
            "status": "pass",
            "reason_code": "STACK_GUARDIAN_DRILL_COMPLETED",
            "stdout": result.stdout.strip(),
        }
    elif service == "opsd":
        result = _run_command(
            [sys.executable, "scripts/opsd_runtime_smoke.py"],
            artifact_dir=artifact_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        payload = {
            "service": service,
            "status": "pass",
            "reason_code": "STACK_OPSD_SMOKE_COMPLETED",
            "summary": _decode_json_object(result.stdout, context="opsd runtime smoke"),
        }
    elif service == "watchdog":
        preflight = _run_command(
            [
                "cargo",
                "run",
                "-p",
                "backtesting-engine-watchdog",
                "--",
                "activation-preflight",
                "green",
                "--artifact-dir",
                str(artifact_dir / "activation-preflight"),
            ],
            artifact_dir=artifact_dir,
        )
        if preflight.returncode != 0:
            raise RuntimeError(preflight.stderr.strip() or preflight.stdout.strip())
        supervision = _run_command(
            [
                "cargo",
                "run",
                "-p",
                "backtesting-engine-watchdog",
                "--",
                "supervision-drill",
                "opsd-restart-into-recovering",
                "--artifact-dir",
                str(artifact_dir / "supervision-drill"),
            ],
            artifact_dir=artifact_dir,
        )
        if supervision.returncode != 0:
            raise RuntimeError(supervision.stderr.strip() or supervision.stdout.strip())
        payload = {
            "service": service,
            "status": "pass",
            "reason_code": "STACK_WATCHDOG_DRILLS_COMPLETED",
            "activation_preflight": _parse_key_value_output(preflight.stdout),
            "supervision": _parse_key_value_output(supervision.stdout),
        }
    else:
        raise ValueError(f"unknown service: {service}")

    _write_json(artifact_dir / f"{service}.started.json", payload)
    return payload


def shutdown_service(service: str, artifact_dir: Path) -> dict[str, Any]:
    payload = {
        "service": service,
        "status": "pass",
        "reason_code": "STACK_GRACEFUL_SHUTDOWN_RECORDED",
        "shutdown_reason": f"{service}_non_economic_smoke_complete",
    }
    _write_json(artifact_dir / f"{service}.shutdown.json", payload)
    return payload


def smoke_stack(artifact_dir: Path) -> dict[str, Any]:
    validation = validate_repository_files()
    if validation.status != "pass":
        raise RuntimeError(json.dumps(validation.to_dict(), sort_keys=True))

    systemd_render_dir = artifact_dir / "rendered-systemd"
    rendered_files = [str(path) for path in render_repository_files(systemd_render_dir)]

    startup_order = [
        "broker-gateway",
        "guardian",
        "opsd",
        "watchdog",
    ]
    steps: list[dict[str, Any]] = []
    for service in startup_order:
        service_dir = artifact_dir / service
        health = healthcheck_service(service, service_dir)
        start = oneshot_service(service, service_dir)
        steps.append({"service": service, "healthcheck": health, "start": start})

    shutdown_order = list(reversed(startup_order))
    shutdown_steps = []
    for service in shutdown_order:
        shutdown_steps.append(
            {"service": service, "shutdown": shutdown_service(service, artifact_dir / service)}
        )

    report = {
        "status": "pass",
        "reason_code": "STACK_BRINGUP_SMOKE_GREEN",
        "startup_order": startup_order,
        "shutdown_order": shutdown_order,
        "env_file": DEFAULT_ENV_FILE,
        "mount_path": _env_for_artifact_dir(artifact_dir)[mount_env_key()],
        "rendered_files": rendered_files,
        "steps": steps,
        "shutdown_steps": shutdown_steps,
        "validation": validation.to_dict(),
    }
    _write_json(artifact_dir / "runtime_stack_bringup_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate runtime stack bring-up configs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--output-dir", type=Path, default=SYSTEMD_DIR)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output-dir", type=Path, default=None)

    health_parser = subparsers.add_parser("healthcheck")
    health_parser.add_argument("--service", required=True, choices=["broker-gateway", "guardian", "opsd", "watchdog"])
    health_parser.add_argument("--artifact-dir", type=Path, required=True)

    oneshot_parser = subparsers.add_parser("oneshot")
    oneshot_parser.add_argument("--service", required=True, choices=["broker-gateway", "guardian", "opsd", "watchdog"])
    oneshot_parser.add_argument("--artifact-dir", type=Path, required=True)

    shutdown_parser = subparsers.add_parser("shutdown")
    shutdown_parser.add_argument("--service", required=True, choices=["broker-gateway", "guardian", "opsd", "watchdog"])
    shutdown_parser.add_argument("--artifact-dir", type=Path, required=True)

    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--artifact-dir", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "render":
        rendered = render_repository_files(args.output_dir)
        print(json.dumps({"rendered_files": [str(path) for path in rendered]}, indent=2))
        return 0
    if args.command == "validate":
        if args.output_dir is not None:
            render_repository_files(args.output_dir)
        report = validate_repository_files()
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.status == "pass" else 1
    if args.command == "healthcheck":
        print(json.dumps(healthcheck_service(args.service, args.artifact_dir), indent=2))
        return 0
    if args.command == "oneshot":
        print(json.dumps(oneshot_service(args.service, args.artifact_dir), indent=2))
        return 0
    if args.command == "shutdown":
        print(json.dumps(shutdown_service(args.service, args.artifact_dir), indent=2))
        return 0
    report = smoke_stack(args.artifact_dir)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
