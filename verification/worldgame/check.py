"""Build a trusted driver against frozen/candidate libraries and check fields."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from chilicrisp.fields import decode, compare
from chilicrisp.runner import tree_hash
CASES = [("ocean", "42", "1.0"), ("ocean", "7", "0.8"), ("ocean", "2026", "1.2"),
         ("manufactured", "17"), ("manufactured", "33"), ("manufactured", "65")]


def selected_cases(tier):
    if tier not in {"screen", "full"}:
        raise ValueError("unknown verification tier")
    # Stable original indexes keep screening compatible with full references.
    indexes = [3, 0] if tier == "screen" else range(len(CASES))
    return [(index, CASES[index]) for index in indexes]


def reference_values(directory, index, case):
    evidence = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    if evidence.get("outcome", "pass") != "pass":
        raise ValueError("reference verification did not pass")
    matches = [record for record in evidence["cases"] if tuple(record["case"]) == case]
    if len(matches) != 1:
        raise ValueError("reference case missing or ambiguous")
    path = directory / f"case-{index}.bin"
    if hashlib.sha256(path.read_bytes()).hexdigest() != matches[0]["sha256"]:
        raise ValueError("reference field hash mismatch")
    return load(path)


def load(path):
    return decode(path.read_bytes())


def manufactured(n):
    h = 1/(n-1)
    eigenvalue = 8*math.sin(math.pi*h/2)**2 / h**2
    return [0.0 if x in (0,n-1) or y in (0,n-1) else
            2*math.pi**2/eigenvalue * math.sin(math.pi*x*h)*math.sin(math.pi*y*h)
            for y in range(n) for x in range(n)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--tier", choices=("screen", "full"), default="full",
                        help="screen: two public cases; full: all six public cases")
    args = parser.parse_args()
    source = args.source.resolve()
    started = time.monotonic()
    source_hash = tree_hash(source / "crates/mote-core")
    destination = ROOT / "reports/worldgame/field-checks" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination.mkdir(parents=True)
    build = ROOT / "artifacts" / ("field-driver-" + destination.name)
    build.mkdir()
    manifest = '[package]\nname="chili-field-driver"\nversion="0.1.0"\nedition="2024"\n[workspace]\n[dependencies]\nmote-core={path=' + json.dumps((source / "crates/mote-core").as_posix()) + '}\n[[bin]]\nname="field-driver"\npath=' + json.dumps((ROOT / "verification/worldgame/harness.rs").as_posix()) + '\n'
    (build / "Cargo.toml").write_text(manifest)
    # Lock resolution uses only the pinned original graph and cached artifacts.
    (build / "Cargo.lock").write_bytes((source / "Cargo.lock").read_bytes())
    command = ["cargo", "+1.98.0", "build", "--offline", "--release", "--manifest-path", str(build / "Cargo.toml")]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (destination / "build.log").write_text(result.stdout + result.stderr)
    executable = build / "target/release" / ("field-driver.exe" if sys.platform == "win32" else "field-driver")
    records = []
    outcome, error = "pass", None
    try:
        if result.returncode:
            raise RuntimeError("trusted driver build failed; see build.log")
        for index, case in selected_cases(args.tier):
            record = dict(case=case, case_index=index, outcome="running")
            records.append(record)
            case_started = time.monotonic()
            output = destination / f"case-{index}.bin"
            try:
                with output.open("wb") as out, (destination / f"case-{index}.stderr").open("wb") as err:
                    run = subprocess.run([str(executable), *case], stdout=out, stderr=err, timeout=60)
                record["exit_code"] = run.returncode
                if run.returncode:
                    raise RuntimeError(f"field driver failed on {case}")
                values = load(output)
                record.update(field_count=len(values), sha256=hashlib.sha256(output.read_bytes()).hexdigest())
                if case[0] == "manufactured":
                    record["analytic_max_abs_error"] = compare(values, manufactured(int(case[1])))
                elif len(values) != 131040:
                    raise ValueError("circulation field count mismatch")
                if args.reference:
                    record["differential_max_abs_error"] = compare(
                        values, reference_values(args.reference, index, case))
                record["outcome"] = "pass"
            except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as failure:
                record.update(outcome="reject", error=str(failure))
                raise
            finally:
                record["elapsed_seconds"] = time.monotonic() - case_started
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as failure:
        outcome, error = "reject", str(failure)
    stable = tree_hash(source / "crates/mote-core") == source_hash
    if not stable:
        outcome, error = "reject", "source changed during verification"
    evidence = dict(source=str(source), harness_sha256=hashlib.sha256((ROOT / "verification/worldgame/harness.rs").read_bytes()).hexdigest(),
        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest() if executable.is_file() else None,
        build_command=command, generated_lock_sha256=hashlib.sha256((build / "Cargo.lock").read_bytes()).hexdigest(),
        reference=str(args.reference) if args.reference else None, cases=records,
        tolerance=dict(atol=1e-8, rtol=1e-8), limitations="Public circulation cases and manufactured shared-solver checks; not evolved transport or empirical Earth validation")
    evidence.update(tier=args.tier, outcome=outcome, error=error, source_hash=source_hash,
                    source_stable=stable, acceptance_eligible=False,
                    elapsed_seconds=time.monotonic() - started,
                    build_exit_code=result.returncode)
    (destination / "results.json").write_text(json.dumps(evidence, indent=2))
    print(destination)
    return 0 if outcome == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
