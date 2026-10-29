import json
from pathlib import Path
import sys
import unittest

from chilicrisp.__main__ import main
from chilicrisp.project import compare, initialize, load_project
from test_core import test_directory


class ProjectTests(unittest.TestCase):
    def fixture(self, directory):
        baseline = Path(directory) / "baseline"
        candidate = Path(directory) / "candidate"
        baseline.mkdir()
        candidate.mkdir()
        for root in (baseline, candidate):
            (root / "check.py").write_text("from pathlib import Path\nassert Path('value').read_text() == 'good'\n")
            (root / "value").write_text("good")
        config = initialize(baseline, [sys.executable, "check.py"])
        return baseline, candidate, config

    def test_real_candidate_pass_and_rejection_preserve_inputs(self):
        with test_directory() as directory:
            baseline, candidate, config = self.fixture(directory)
            record, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["decision"], "public_tests_passed")
            self.assertEqual(json.loads(record.read_text())["state"], "FINALIZED")
            self.assertEqual(result["evaluations"]["baseline"]["source_hash"],
                             result["evaluations"]["candidate"]["source_hash"])
            (candidate / "value").write_text("bad")
            _, rejected = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(rejected["decision"], "candidate_rejected")
            self.assertEqual((baseline / "value").read_text(), "good")
            self.assertEqual((candidate / "value").read_text(), "bad")

    def test_baseline_failure_stops_candidate(self):
        with test_directory() as directory:
            baseline, candidate, config = self.fixture(directory)
            (baseline / "value").write_text("bad")
            _, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["decision"], "baseline_failed")
            self.assertEqual(result["evaluations"]["candidate"]["commands"], [])

    def test_budgets_and_build_failure(self):
        with test_directory() as directory:
            baseline, candidate, config = self.fixture(directory)
            settings = json.loads(config.read_text())
            settings["command_seconds"] = .1
            settings["build"] = [sys.executable, "-c", "import time; time.sleep(5)"]
            config.write_text(json.dumps(settings))
            _, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["evaluations"]["baseline"]["outcome"], "timeout")
            self.assertEqual(len(result["evaluations"]["baseline"]["commands"]), 1)

    def test_output_limit_and_missing_executable(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            settings = json.loads(config.read_text())
            settings["output_bytes_per_stream"] = 100
            settings["test"] = [sys.executable, "-c", "print('x' * 50000)"]
            config.write_text(json.dumps(settings))
            _, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            observation = result["evaluations"]["baseline"]["commands"][0]
            self.assertEqual(observation["outcome"], "output_limit")
            self.assertTrue(observation["capture"]["stdout"]["truncated"])
            settings["test"] = [str(Path(directory) / "does-not-exist")]
            config.write_text(json.dumps(settings))
            _, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["evaluations"]["baseline"]["outcome"], "runner_failure")

    def test_configuration_and_execution_boundaries(self):
        with test_directory() as directory:
            baseline, candidate, config = self.fixture(directory)
            with self.assertRaises(FileExistsError):
                initialize(baseline, [sys.executable, "check.py"])
            with self.assertRaisesRegex(ValueError, "trusted-local"):
                compare(config, candidate, Path(directory) / "runs")
            with self.assertRaisesRegex(ValueError, "excluded"):
                compare(config, candidate, baseline / "runs", trusted_local=True)
            settings, root = load_project(config)
            self.assertEqual(root, baseline.resolve())
            self.assertEqual(settings["test"], [sys.executable, "check.py"])

    def test_cli_returns_failure_for_rejected_candidate(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            (candidate / "value").write_text("bad")
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                code = main(["compare", str(config), "--candidate", str(candidate),
                             "--output", str(Path(directory) / "runs"), "--trusted-local"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stream.getvalue())["decision"], "candidate_rejected")
