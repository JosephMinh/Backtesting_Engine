from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
import subprocess

from python.bindings._kernels import (
    BINDING_TARGET_ROOT,
    BoundDecision,
    BoundKernelIdentity,
    BoundKernelRun,
    KernelBindingError,
    decode_json_object,
    rust_subprocess_env,
    run_gold_momentum,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = (
    REPO_ROOT / "rust" / "kernels" / "fixtures" / "gold_momentum_replay_cases.txt"
)


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    lookback_bars: int
    threshold_ticks: int
    candidate_bundle: str
    resolved_context_bundle: str
    signal_kernel: str
    closes: tuple[int, ...]


@dataclass(frozen=True)
class CertificationMismatch:
    source: str
    message: str


@dataclass(frozen=True)
class EquivalenceCertificationReport:
    case_id: str
    kernel_digest: str
    fixture_path: str
    property_case_count: int
    random_seed: int
    python_entry_path: str
    rust_entry_paths: tuple[str, ...]
    structured_logs: tuple[dict[str, object], ...]
    mismatches: tuple[CertificationMismatch, ...]
    mismatch_bundle_path: str | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["mismatches"] = [asdict(mismatch) for mismatch in self.mismatches]
        payload["structured_logs"] = [dict(log) for log in self.structured_logs]
        return payload


def run_equivalence_certification(
    case_id: str,
    *,
    fixture_path: Path | None = None,
    output_dir: Path | None = None,
    property_case_count: int = 4,
    random_seed: int = 19,
) -> EquivalenceCertificationReport:
    fixture_path = fixture_path or DEFAULT_FIXTURE_PATH
    output_dir = output_dir or BINDING_TARGET_ROOT / "binding-certification"
    cases = _load_fixture_cases(fixture_path)
    case = next(item for item in cases if item.case_id == case_id)

    direct_fixture = _run_direct_fixture_case(case_id, fixture_path, output_dir)
    bound_fixture = run_gold_momentum(
        list(case.closes),
        lookback_bars=case.lookback_bars,
        threshold_ticks=case.threshold_ticks,
    )

    mismatches: list[CertificationMismatch] = []
    structured_logs: list[dict[str, object]] = [
        {
            "event": "equivalence_certification_started",
            "fixture_path": str(fixture_path),
            "case_id": case.case_id,
            "property_case_count": property_case_count,
            "random_seed": random_seed,
        }
    ]
    mismatches.extend(_compare_runs("fixture_case", direct_fixture, bound_fixture))

    rng = random.Random(random_seed)
    for offset in range(property_case_count):
        lookback_bars = 2 + (offset % 3)
        threshold_ticks = 3 + (offset % 4)
        closes = _random_closes(rng, length=8 + offset)
        direct_random = _run_direct_series(closes, lookback_bars, threshold_ticks)
        bound_random = run_gold_momentum(
            closes,
            lookback_bars=lookback_bars,
            threshold_ticks=threshold_ticks,
        )
        mismatches.extend(
            _compare_runs(f"random_case_{offset}", direct_random, bound_random)
        )

    mismatch_bundle_path = None
    if mismatches:
        output_dir.mkdir(parents=True, exist_ok=True)
        mismatch_bundle = output_dir / f"{case.case_id}_equivalence_mismatch.json"
        mismatch_bundle.write_text(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "kernel_digest": direct_fixture.identity.canonical_digest,
                    "fixture_path": str(fixture_path),
                    "python_entry_path": bound_fixture.entry_path,
                    "rust_entry_paths": [
                        direct_fixture.entry_path,
                        "rust.bin.gold_momentum_direct_runner",
                    ],
                    "mismatches": [asdict(item) for item in mismatches],
                },
                indent=2,
            )
        )
        mismatch_bundle_path = str(mismatch_bundle)
        structured_logs.append(
            {
                "event": "equivalence_certification_failed",
                "mismatch_bundle_path": mismatch_bundle_path,
                "mismatch_count": len(mismatches),
            }
        )
    else:
        structured_logs.append(
            {
                "event": "equivalence_certification_passed",
                "kernel_digest": direct_fixture.identity.canonical_digest,
                "fixture_case": case.case_id,
                "property_case_count": property_case_count,
            }
        )

    return EquivalenceCertificationReport(
        case_id=case.case_id,
        kernel_digest=direct_fixture.identity.canonical_digest,
        fixture_path=str(fixture_path),
        property_case_count=property_case_count,
        random_seed=random_seed,
        python_entry_path=bound_fixture.entry_path,
        rust_entry_paths=(direct_fixture.entry_path, "rust.bin.gold_momentum_direct_runner"),
        structured_logs=tuple(structured_logs),
        mismatches=tuple(mismatches),
        mismatch_bundle_path=mismatch_bundle_path,
    )


def _load_fixture_cases(path: Path) -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    for block in path.read_text().split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        fields: dict[str, str] = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
        cases.append(
            FixtureCase(
                case_id=fields["case_id"],
                lookback_bars=int(fields["lookback_bars"]),
                threshold_ticks=int(fields["threshold_ticks"]),
                candidate_bundle=fields["candidate_bundle"],
                resolved_context_bundle=fields["resolved_context_bundle"],
                signal_kernel=fields["signal_kernel"],
                closes=tuple(int(item) for item in fields["closes"].split(",")),
            )
        )
    return cases


def _run_direct_fixture_case(
    case_id: str,
    fixture_path: Path,
    output_dir: Path,
) -> BoundKernelRun:
    payload = _run_rust_json(
        [
            "cargo",
            "run",
            "-p",
            "backtesting-engine-kernels",
            "--bin",
            "gold_momentum_smoke",
            "--",
            "--case-id",
            case_id,
            "--fixture-path",
            str(fixture_path),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )
    return _bound_run_from_payload(payload, decisions_key="actual")


def _run_direct_series(
    closes: list[int],
    lookback_bars: int,
    threshold_ticks: int,
) -> BoundKernelRun:
    payload = _run_rust_json(
        [
            "cargo",
            "run",
            "-p",
            "backtesting-engine-kernels",
            "--bin",
            "gold_momentum_direct_runner",
            "--",
            "--lookback-bars",
            str(lookback_bars),
            "--threshold-ticks",
            str(threshold_ticks),
            "--closes",
            ",".join(str(close) for close in closes),
            "--json",
        ]
    )
    return _bound_run_from_payload(payload, decisions_key="decisions")


def _run_rust_json(command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=rust_subprocess_env(),
    )
    stdout = result.stdout.strip()
    if stdout:
        try:
            return decode_json_object(stdout, context="direct Rust path")
        except KernelBindingError:
            pass
    if result.returncode != 0:
        raise KernelBindingError(result.stderr.strip() or stdout)
    raise KernelBindingError("direct Rust path did not return a JSON object")


def _bound_run_from_payload(
    payload: dict[str, object], *, decisions_key: str
) -> BoundKernelRun:
    identity_payload = payload["identity"]
    if not isinstance(identity_payload, dict):
        raise KernelBindingError("direct Rust path did not return an identity object")
    identity = BoundKernelIdentity(**identity_payload)
    decision_payload = payload[decisions_key]
    if not isinstance(decision_payload, list):
        raise KernelBindingError("direct Rust path did not return a decision list")
    decisions = tuple(BoundDecision(**decision) for decision in decision_payload)
    return BoundKernelRun(
        entry_path=str(payload["entry_path"]),
        identity=identity,
        lookback_bars=int(payload.get("lookback_bars", 0)),
        threshold_ticks=int(payload.get("threshold_ticks", 0)),
        decisions=decisions,
    )


def _compare_runs(label: str, direct: BoundKernelRun, bound: BoundKernelRun) -> list[CertificationMismatch]:
    mismatches: list[CertificationMismatch] = []
    if direct.identity.canonical_digest != bound.identity.canonical_digest:
        mismatches.append(
            CertificationMismatch(
                source=label,
                message=(
                    f"digest mismatch: rust={direct.identity.canonical_digest} "
                    f"python={bound.identity.canonical_digest}"
                ),
            )
        )
    if len(direct.decisions) != len(bound.decisions):
        mismatches.append(
            CertificationMismatch(
                source=label,
                message=(
                    f"decision count mismatch: rust={len(direct.decisions)} "
                    f"python={len(bound.decisions)}"
                ),
            )
        )
    for index, (rust_decision, python_decision) in enumerate(
        zip(direct.decisions, bound.decisions)
    ):
        if (
            rust_decision.sequence_number != python_decision.sequence_number
            or rust_decision.disposition != python_decision.disposition
            or rust_decision.score_ticks != python_decision.score_ticks
        ):
            mismatches.append(
                CertificationMismatch(
                    source=label,
                    message=(
                        f"decision {index} mismatch: "
                        f"rust=({rust_decision.sequence_number},{rust_decision.disposition},{rust_decision.score_ticks}) "
                        f"python=({python_decision.sequence_number},{python_decision.disposition},{python_decision.score_ticks})"
                    ),
                )
            )
    return mismatches


def _random_closes(rng: random.Random, *, length: int) -> list[int]:
    close = 10_000
    values: list[int] = []
    for _ in range(length):
        close = max(1, close + rng.randint(-5, 5))
        values.append(close)
    return values


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", default="gold_momentum_promotable")
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BINDING_TARGET_ROOT / "binding-certification",
    )
    parser.add_argument("--property-case-count", type=int, default=4)
    parser.add_argument("--random-seed", type=int, default=19)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_equivalence_certification(
        args.case_id,
        fixture_path=args.fixture_path,
        output_dir=args.output_dir,
        property_case_count=args.property_case_count,
        random_seed=args.random_seed,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("Kernel equivalence certification summary")
        print(f"case_id: {report.case_id}")
        print(f"kernel_digest: {report.kernel_digest}")
        print(f"python_entry_path: {report.python_entry_path}")
        print(f"rust_entry_paths: {', '.join(report.rust_entry_paths)}")
        print(f"mismatch_count: {len(report.mismatches)}")
        if report.mismatch_bundle_path is not None:
            print(f"mismatch_bundle_path: {report.mismatch_bundle_path}")
    return 0 if not report.mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
