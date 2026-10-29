import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import time
import unittest
from unittest.mock import patch

from chilicrisp.__main__ import main
from chilicrisp import development as dev
from chilicrisp.measure import artifact_size, measure
from chilicrisp.project import initialize
from test_core import test_directory


CODEC = '''from pathlib import Path
import zlib
LEVEL = -1
DATA = b'chili-crisp-content-' * 8192
def build():
    Path('build').mkdir(exist_ok=True)
    data = DATA if LEVEL == -1 else zlib.compress(DATA, LEVEL)
    Path('build/payload.bin').write_bytes(data)
def readback():
    data = Path('build/payload.bin').read_bytes()
    return data if LEVEL == -1 else zlib.decompress(data)
'''
CHECK = "from codec import build, readback\nbuild()\nassert readback() == b'chili-crisp-content-' * 8192\n"
BENCH = "from codec import readback\nimport hashlib\nprint(hashlib.sha256(readback()).hexdigest())\n"


def fixture(directory, **changes):
    root = Path(directory)
    baseline = root / "baseline"
    baseline.mkdir()
    for name, content in (("codec.py", CODEC), ("check.py", CHECK), ("bench.py", BENCH)):
        (baseline / name).write_text(content, encoding="utf-8")
    config = initialize(baseline, [sys.executable, "check.py"],
                        [sys.executable, "-c", "from codec import build; build()"],
                        protected_paths=["check.py", "bench.py"])
    plan = {"schema_version": "0.1", "concept": "Return the same payload from a smaller stored artifact",
        "project_config": str(config), "benchmark_command": [sys.executable, "bench.py"],
        "objective": "artifact_bytes", "artifact_paths": ["build/payload.bin"],
        "repetitions": 2, "confirmation_repetitions": 2, "seed": 19, **changes}
    path = root / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    research = root / "research.json"
    research.write_text(json.dumps({"hypothesis": "Compressing repeated bytes reduces the artifact",
        "mechanism": "Lossless compression preserves the readback result",
        "falsification": "Readback changes, target is missed, or latency exceeds its guard",
        "sources": [{"reference": "https://docs.python.org/3/library/zlib.html",
                     "supports": "Lossless compression with selectable compression levels"}]}))
    candidate = root / "candidate"
    shutil.copytree(baseline, candidate)
    return path, root / "session", baseline, candidate, research


class DevelopmentTests(unittest.TestCase):
    def test_experiment_memory_is_bounded_and_excludes_proposer_claims(self):
        generations = [{"id": index, "decision": "rejected", "source_hash": "same",
            "research": {"hypothesis": "SECRET_UNMEASURED_CLAIM"},
            "phases": {"exploration": {"medians": {"candidate": {"artifact_bytes": index}},
                                      "records": ["raw-log"]}}} for index in range(12)]
        memory = dev._experiment_memory({"generations": generations})
        self.assertEqual(memory["total_attempts"], 12)
        self.assertEqual(memory["omitted_attempts"], 4)
        self.assertEqual(memory["attempts"][0]["id"], 4)
        self.assertEqual(memory["attempts"][-1]["measurements"]["exploration"]["candidate"]["artifact_bytes"], 11)
        self.assertNotIn("SECRET_UNMEASURED_CLAIM", json.dumps(memory))
        self.assertNotIn("raw-log", json.dumps(memory))

    def test_repeated_source_is_labelled_and_still_remeasured(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory, regression_limits={})
            dev.create(plan, session, trusted_local=True)
            first = dev.submit(session, candidate, research, trusted_local=True)
            second = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(first["generations"][-1]["repeat_of"], [])
            self.assertEqual(second["generations"][-1]["repeat_of"], [1])
            self.assertIn("exploration", second["generations"][-1]["phases"])
            memory = dev.request(session)["experiment_memory"]
            self.assertEqual(memory["attempts"][-1]["repeat_of"], [1])

    def test_two_real_generations_move_the_target_and_survive_reload(self):
        with test_directory() as directory:
            plan, session, baseline, candidate, research = fixture(directory, regression_limits={"wall_seconds": 5})
            state = dev.create(plan, session, trusted_local=True)
            first_target = dev.request(session)["target"]
            (candidate / "codec.py").write_text(CODEC.replace("LEVEL = -1", "LEVEL = 1"))
            first = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(first["generations"][-1]["decision"], "accepted_experimental")
            self.assertLess(dev.request(session)["target"], first_target)
            second_target = dev.request(session)["target"]
            (candidate / "codec.py").write_text(CODEC.replace("LEVEL = -1", "LEVEL = 9"))
            second = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(second["generations"][-1]["decision"], "accepted_experimental")
            self.assertLess(second["target"], second_target)
            self.assertEqual(len(dev.status(session)["champions"]), 3)
            self.assertEqual(second["champions"][-1]["verification"]["sealed"], "not_run")
            self.assertEqual(second["champions"][-1]["verification"]["production"], "not_accepted")
            self.assertEqual((baseline / "codec.py").read_text(), CODEC)
            self.assertEqual(state["champion"], 0)

    def test_wrong_output_and_changed_tests_cannot_replace_champion(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory, max_stagnation=2)
            state = dev.create(plan, session, trusted_local=True)
            original_target = state["target"]
            (candidate / "codec.py").write_text(CODEC.replace("return data if LEVEL", "return b'wrong' if LEVEL"))
            rejected = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(rejected["champion"], 0)
            self.assertEqual(rejected["generations"][-1]["decision"], "rejected")
            self.assertGreater(rejected["target"], original_target)
            (candidate / "check.py").write_text("pass")
            rejected = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(rejected["state"], "STOPPED")
            self.assertEqual(rejected["stop_reason"], "stagnation_cap")
            self.assertEqual(len(rejected["champions"]), 1)

    def test_failed_target_keeps_champion_and_rollback_remeasures_old_artifact(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory, regression_limits={})
            dev.create(plan, session, trusted_local=True)
            failed = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(failed["generations"][-1]["decision"], "rejected")
            (candidate / "codec.py").write_text(CODEC.replace("LEVEL = -1", "LEVEL = 1"))
            dev.submit(session, candidate, research, trusted_local=True)
            restored = dev.rollback(session, "initial", "Test retained-artifact rollback", trusted_local=True)
            champion = restored["champions"][restored["champion"]]
            self.assertEqual(champion["rollback_of"], "initial")
            self.assertEqual(champion["source_hash"], restored["champions"][0]["source_hash"])
            self.assertEqual(restored["events"][-1]["kind"], "rollback")

    def test_latency_regression_rejects_smaller_candidate(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory, regression_limits={"wall_seconds": .1})
            dev.create(plan, session, trusted_local=True)
            slower = CODEC.replace("LEVEL = -1", "LEVEL = 1").replace("def readback():", "def readback():\n    import time; time.sleep(.3)")
            (candidate / "codec.py").write_text(slower)
            rejected = dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(rejected["champion"], 0)
            self.assertIn("regression", rejected["generations"][-1]["reason"])

    def test_budget_reservation_stops_before_commands(self):
        with test_directory() as directory:
            plan, session, _, _, _ = fixture(directory, max_commands=1)
            with patch("chilicrisp.development.compare") as comparison:
                with self.assertRaisesRegex(ValueError, "budget"):
                    dev.create(plan, session, trusted_local=True)
            comparison.assert_not_called()
            self.assertEqual(dev.status(session)["state"], "STOPPED")

    def test_interruption_requires_explicit_recovery_and_counts_attempt(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory)
            dev.create(plan, session, trusted_local=True)
            with patch("chilicrisp.development.measure", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(dev.status(session)["state"], "INTERRUPTED")
            with self.assertRaises(ValueError):
                dev.request(session)
            with self.assertRaises(ValueError):
                dev.recover(session)
            recovered = dev.recover(session, owner_stopped=True)
            self.assertIsNone(recovered["pending"])
            self.assertEqual(recovered["generations"][-1]["decision"], "interrupted")
            self.assertEqual(recovered["champion"], 0)

    def test_frozen_source_drift_and_session_lock_block_submission(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory)
            state = dev.create(plan, session, trusted_local=True)
            (session / "controller.lock").write_text("external-owner")
            with self.assertRaisesRegex(ValueError, "locked"):
                dev.submit(session, candidate, research, trusted_local=True)
            (session / "controller.lock").unlink()
            source = session / state["champions"][0]["source"] / "codec.py"
            source.write_text(CODEC + "\n# changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                dev.request(session)

    def test_cli_request_reads_saved_session(self):
        with test_directory() as directory:
            plan, session, _, _, _ = fixture(directory)
            dev.create(plan, session, trusted_local=True)
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                code = main(["dev", "request", str(session)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stream.getvalue())["target_basis"],
                             "median local measurements; no scarcity limit is enforced")

    def test_external_agent_protocol_runs_until_declared_cap(self):
        with test_directory() as directory:
            plan, session, _, _, research = fixture(directory, max_generations=1, regression_limits={})
            dev.create(plan, session, trusted_local=True)
            script = Path(directory) / "agent.py"
            script.write_text("""import json, sys
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text())
assert request['target_basis'].startswith('median')
target = Path(sys.argv[3]) / 'codec.py'
target.write_text(target.read_text().replace('LEVEL = -1', 'LEVEL = 1'))
Path(sys.argv[2]).write_bytes(Path(sys.argv[4]).read_bytes())
""")
            result = dev.run(session, [sys.executable, str(script), "{request}", "{response}",
                                       "{workspace}", str(research)], trusted_local=True)
            self.assertEqual(result["state"], "STOPPED")
            self.assertEqual(result["stop_reason"], "generation_cap")
            self.assertEqual(len(result["champions"]), 2)
            self.assertTrue(any(event["kind"] == "agent_proposal" for event in result["events"]))

    def test_stale_agent_request_cannot_be_submitted_as_next_generation(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory)
            initial = dev.create(plan, session, trusted_local=True)
            with self.assertRaisesRegex(ValueError, "earlier"):
                dev.submit(session, candidate, research, trusted_local=True, expected_generation=2)
            self.assertEqual(dev.status(session)["reserved_commands"], initial["reserved_commands"])

    def test_unresolved_cleanup_blocks_further_generations(self):
        with test_directory() as directory:
            plan, session, _, candidate, research = fixture(directory)
            dev.create(plan, session, trusted_local=True)
            with patch("chilicrisp.development.measure", return_value={"outcome": "cleanup_failure"}):
                with self.assertRaises(dev.CleanupRequired):
                    dev.submit(session, candidate, research, trusted_local=True)
            self.assertEqual(dev.status(session)["state"], "INTERRUPTED")
            self.assertEqual(dev.status(session)["champion"], 0)
            with self.assertRaises(ValueError):
                dev.request(session)


class LocalMeasurementTests(unittest.TestCase):
    def test_real_local_memory_cpu_volume_and_bounded_output(self):
        with test_directory() as directory:
            root = Path(directory)
            (root / "payload").write_bytes(b"x" * 1024)
            config = {"command_seconds": 10, "output_bytes_per_stream": 1024}
            command = [sys.executable, "-c", "import time; x=bytearray(16*1024*1024); time.sleep(.15); print(len(x))"]
            result = measure(command, root, root / "run", config, time.monotonic() + 10, ["payload"])
            self.assertEqual(result["outcome"], "pass")
            self.assertGreater(result["metrics"]["sampled_peak_rss_bytes"], 1024*1024)
            self.assertEqual(result["metrics"]["artifact_bytes"], 1024)
            self.assertEqual(result["enforcement"], "none")
            self.assertEqual(result["metric_quality"]["sampled_peak_rss_bytes"]["tier"], "screening_sample")

    def test_missing_and_escaping_artifacts_are_not_zero(self):
        with test_directory() as directory:
            root = Path(directory)
            self.assertIsNone(artifact_size(root, []))
            with self.assertRaises(ValueError):
                artifact_size(root, ["missing"])
            with self.assertRaises(ValueError):
                artifact_size(root, ["../outside"])
