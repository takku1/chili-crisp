"""Isolated, offline compiler export. Returned artifacts are never host-executed."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import time

from .contracts import validate
from .project import snapshot
from .runner import file_hash, run_trial, tree_hash


def check_elf(data, maximum_bytes):
    if not 64 <= len(data) <= maximum_bytes or data[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError("Export is not a bounded ELF64 little-endian artifact")
    kind, machine, version = struct.unpack_from("<HHI", data, 16)
    if kind not in (2, 3) or machine != 62 or version != 1:
        raise ValueError("Export has an unsupported ELF type or architecture")


def load_policy(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text())
    validate(value, "experiment")
    if value["isolation"]["seccomp"] != "pilot_build_v1" or "source_mount" in value["target"]:
        raise ValueError("Compiler manifest needs the dedicated build profile and no supplied source mount")
    if len(value["workloads"]) != 1 or value["workloads"][0].get("oracle", {}).get("kind") != "build_elf_v1":
        raise ValueError("Compiler manifest needs one ELF-export workload")
    workload = value["workloads"][0]
    oracle = workload["oracle"]
    policy = json.loads(Path(oracle["policy_path"]).read_text())
    validate(policy, "build-artifact")
    if file_hash(oracle["policy_path"]) != oracle["policy_hash"] or file_hash(workload["input"]) != workload["input_hash"]:
        raise ValueError("Compiler input/export policy identity mismatch")
    if value["limits"]["output_bytes_per_stream"] < policy["maximum_bytes"]:
        raise ValueError("Compiler capture cap must cover the declared export cap")
    if tree_hash(value["target"]["rootfs"]) != value["target"]["rootfs_hash"]:
        raise ValueError("Frozen compiler toolchain identity mismatch")
    return value, policy


def _save(output, record):
    temporary = output / "build-record.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, output / "build-record.json")


def compile_candidate(source, manifest_path, output, budget, deadline, *, evidence_root=None):
    from .evaluation import CleanupRequired, ensure_clean
    source, output = Path(source).resolve(), Path(output).resolve()
    manifest_path = Path(manifest_path).resolve()
    manifest, policy = load_policy(manifest_path)
    if budget <= 0 or budget % manifest["search"]["page_size"] or not math.isfinite(deadline):
        raise ValueError("Compiler budget must be positive/page aligned and deadline finite")
    if time.monotonic() >= deadline:
        raise ValueError("Compiler deadline exhausted")
    runtime = Path(manifest["target"]["rootfs"]).resolve()
    if (output.is_relative_to(source) or source.is_relative_to(output)
            or output.is_relative_to(runtime) or runtime.is_relative_to(output)):
        raise ValueError("Compiler source, output and toolchain must be separate")
    evidence_root = Path(evidence_root).resolve() if evidence_root else output / "evidence"
    ensure_clean(evidence_root)
    output.mkdir(parents=True, exist_ok=False)
    record = {"kind": "isolated_compilation", "status": "running", "reserved_trials": 2,
        "manifest_sha256": file_hash(manifest_path), "toolchain_sha256": manifest["target"]["rootfs_hash"],
        "builder_sha256": file_hash(__file__), "memory_budget": budget, "trials": []}
    _save(output, record)
    try:
        frozen = output / "source"
        record["source_hash"] = snapshot(source, frozen)
        record["source_tree_hash"] = tree_hash(frozen)
        manifest["target"].update(source_hash=record["source_tree_hash"],
            source_mount={"path": str(frozen), "tree_hash": record["source_tree_hash"]})
        manifest["evidence_directory"] = str(evidence_root)
        record["trial_manifest_sha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        _save(output, record)
        digests = []
        for _ in range(2):
            result = run_trial(copy.deepcopy(manifest), manifest["workloads"][0]["id"], budget,
                               experiment_deadline=deadline)
            validate(result, "result")
            record["trials"].append(result["trial_id"])
            _save(output, record)
            if result["lifecycle"] != "FINALIZED" or result["outcome"] in {"cleanup_failure", "unsupported", "runner_failure"}:
                raise CleanupRequired("Compiler worker needs inspection/recovery: " + str(result["error"]))
            if result["outcome"] != "pass":
                raise ValueError("Isolated compilation failed: " + result["outcome"])
            if result["effective_budget_bytes"] != budget:
                raise CleanupRequired("Compiler effective budget differs")
            payload = evidence_root / result["trial_id"] / "stdout"
            if file_hash(payload) != result["artifact_hashes"]["stdout"]:
                raise ValueError("Compiler export integrity mismatch")
            check_elf(payload.read_bytes(), policy["maximum_bytes"])
            digests.append(file_hash(payload))
        if len(set(digests)) != 1:
            raise ValueError("Fresh compiler outputs were not byte-identical")
        if (file_hash(manifest_path) != record["manifest_sha256"] or load_policy(manifest_path)[0]["target"]["rootfs_hash"] != record["toolchain_sha256"]
                or tree_hash(frozen) != record["source_tree_hash"]):
            raise ValueError("Compiler policy/toolchain/source changed during build")
        artifacts = output / "artifacts"
        artifacts.mkdir()
        (artifacts / "program").write_bytes(payload.read_bytes())
        (artifacts / "program").chmod(0o555)
        record.update(status="retained", artifact_sha256=digests[0], artifacts_tree_hash=tree_hash(artifacts),
            evidence_directory=str(evidence_root), reproducibility="two fresh builds, same pinned host/toolchain; not cross-host reproducibility")
        _save(output, record)
        return record
    except BaseException as error:
        record.update(status="interrupted" if isinstance(error, (CleanupRequired, KeyboardInterrupt, SystemExit)) else "rejected",
                      error=f"{type(error).__name__}: {error}")
        _save(output, record)
        raise


def verify_cached(source, manifest_path, output, budget):
    """Check cached provenance before reuse; corruption never triggers a free rebuild."""
    output = Path(output)
    manifest, _ = load_policy(manifest_path)
    record = json.loads((output / "build-record.json").read_text())
    if (record["status"] != "retained" or record["manifest_sha256"] != file_hash(manifest_path)
            or record["builder_sha256"] != file_hash(__file__) or record["memory_budget"] != budget
            or record["toolchain_sha256"] != manifest["target"]["rootfs_hash"]
            or record["source_tree_hash"] != tree_hash(source)
            or record["source_tree_hash"] != tree_hash(output / "source")
            or record["artifacts_tree_hash"] != tree_hash(output / "artifacts")
            or record["artifact_sha256"] != file_hash(output / "artifacts/program")
            or len(record["trials"]) != 2):
        raise ValueError("Cached compilation identity differs")
    for trial_id in record["trials"]:
        trial = Path(record["evidence_directory"]) / trial_id
        result = json.loads((trial / "result.json").read_text())
        validate(result, "result")
        if (result["outcome"] != "pass" or result["lifecycle"] != "FINALIZED"
                or result["manifest_hash"] != record["trial_manifest_sha256"]
                or result["effective_budget_bytes"] != budget
                or result["artifact_hashes"]["stdout"] != record["artifact_sha256"]):
            raise ValueError("Cached compiler trial differs")
        for name, digest in result["artifact_hashes"].items():
            if Path(name).name != name or file_hash(trial / name) != digest:
                raise ValueError("Cached compiler artifact differs")
    return output / "artifacts"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600:
        raise ValueError("Compiler wall budget must be 0..3600 seconds")
    print(json.dumps(compile_candidate(args.source, args.manifest, args.output, args.budget,
                                      time.monotonic()+args.seconds), indent=2))


if __name__ == "__main__":
    main()
