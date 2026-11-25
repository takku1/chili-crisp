import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

from jsonschema import ValidationError

from chilicrisp import constraints as c
from chilicrisp.__main__ import main
from test_core import test_directory

ROOT = Path(__file__).resolve().parents[1]
# Holds ~SIZE bytes for long enough to be sampled, then prints a fixed answer.
PROGRAM = "import time\nblock = bytearray({size})\ntime.sleep(0.3)\nprint('answer', 42)\n"


def project(root, name, size, extra=""):
    directory = Path(root) / name
    directory.mkdir()
    (directory / "work.py").write_text(PROGRAM.format(size=size) + extra, encoding="utf-8")
    return directory


class QuantityTests(unittest.TestCase):
    def test_units_and_relative_budgets(self):
        self.assertEqual(c.parse_quantity("16MiB", "bytes"), ("absolute", 16 * 1024**2))
        self.assertEqual(c.parse_quantity("1.5 KB", "bytes"), ("absolute", 1500))
        self.assertEqual(c.parse_quantity("250ms", "seconds"), ("absolute", 0.25))
        self.assertEqual(c.parse_quantity("25%", "bytes"), ("relative", 0.25))
        self.assertEqual(c.parse_quantity(3, "seconds"), ("absolute", 3.0))

    def test_rejects_wrong_units_and_garbage(self):
        for value, unit in (("2s", "bytes"), ("4MiB", "seconds"), ("lots", "bytes"), (True, "bytes")):
            with self.assertRaises(ValueError):
                c.parse_quantity(value, unit)


class BriefTests(unittest.TestCase):
    def test_every_profile_is_valid(self):
        for name in c.PROFILES:
            self.assertEqual(c.load(name)["name"], name)

    def test_extends_merges_budgets_and_rules(self):
        brief = c.load({"schema_version": "1.0", "name": "mine", "extends": "handheld", "story": "s",
                        "budgets": {"peak_memory_bytes": "8MiB"}, "rules": ["extra"]})
        self.assertEqual(brief["budgets"]["peak_memory_bytes"], "8MiB")
        self.assertEqual(brief["budgets"]["wall_seconds"], "1s")
        self.assertIn("extra", brief["rules"])
        self.assertTrue(brief["forbid"])

    def test_unknown_budget_and_missing_file_are_rejected(self):
        with self.assertRaises(ValidationError):
            c.load({"schema_version": "1.0", "name": "x", "story": "s", "budgets": {"ram": 1}})
        with self.assertRaises(ValueError):
            c.load("no-such-profile-or-file")

    def test_relative_budgets_resolve_only_with_baseline(self):
        brief = c.load("quarter")
        self.assertIsNone(c.resolve(brief)["peak_memory_bytes"]["limit"])
        resolved = c.resolve(brief, {"peak_memory_bytes": 400, "wall_seconds": 2})
        self.assertEqual(resolved["peak_memory_bytes"]["limit"], 100)
        self.assertEqual(resolved["wall_seconds"]["limit"], 3)

    def test_render_is_agent_readable(self):
        text = c.render("handheld")
        self.assertIn("# Constraint brief: handheld", text)
        self.assertIn("16.0 MiB", text)
        self.assertIn("(checked)", text)

    def test_render_states_measurement_limits(self):
        text = c.render("edge-function")
        self.assertIn("Peak memory across several processes is approximate", text)
        self.assertIn("A zero budget (bytes written) means none at all", text)
        self.assertNotIn("zero budget", c.render("floppy"))

    def test_brief_out_writes_markdown(self):
        with test_directory() as root:
            target = Path(root) / "nested" / "brief.md"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["brief", "quarter", "--out", str(target)]), 0)
            self.assertTrue(target.read_text(encoding="utf-8").startswith("# Constraint brief: quarter"))

    def test_scan_finds_forbidden_patterns(self):
        with test_directory() as root:
            (Path(root) / "net.py").write_text("import socket\n", encoding="utf-8")
            (Path(root) / "notes.txt").write_text("import socket\n", encoding="utf-8")
            found = c.scan(c.load("handheld"), root)
        self.assertEqual([(v["file"], v["line"]) for v in found], [("net.py", 1)])


class CheckTests(unittest.TestCase):
    def run_check(self, root, spec, candidate, baseline=None, **options):
        return c.check(spec, [sys.executable, "work.py"], candidate, Path(root) / "out",
                       baseline_workspace=baseline, repeat=options.pop("repeat", 2), timeout=60, **options)

    def test_smaller_candidate_fits_a_relative_budget(self):
        with test_directory() as root:
            baseline = project(root, "baseline", 160 * 1024**2)
            candidate = project(root, "candidate", 1024)
            report = self.run_check(root, "quarter", candidate, baseline, same_output=True)
            self.assertEqual(report["verdict"], "fits", report["findings"])
            memory = report["budgets"]["peak_memory_bytes"]
            self.assertLess(memory["measured"], memory["limit"])
            self.assertTrue((Path(root) / "out" / "report.json").is_file())

    def test_unchanged_program_is_over_budget(self):
        with test_directory() as root:
            baseline = project(root, "baseline", 160 * 1024**2)
            report = self.run_check(root, "quarter", baseline, baseline)
            self.assertEqual(report["verdict"], "over_budget")
            self.assertEqual(report["budgets"]["peak_memory_bytes"]["status"], "over")

    def test_relative_budget_without_baseline_is_incomplete(self):
        with test_directory() as root:
            candidate = project(root, "candidate", 1024)
            report = self.run_check(root, "half", candidate, repeat=1)
            self.assertEqual(report["verdict"], "incomplete")

    def test_changed_output_failure_and_rule_break_are_broken(self):
        with test_directory() as root:
            baseline = project(root, "baseline", 1024)
            changed = project(root, "changed", 1024, "print('extra')\n")
            failing = project(root, "failing", 1024, "raise SystemExit(3)\n")
            networked = project(root, "networked", 1024, "import socket\n")
            spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"wall_seconds": 60},
                    "forbid": [{"pattern": "socket", "glob": "*.py", "why": "offline"}]}
            for directory in (changed, failing, networked):
                report = c.check(spec, [sys.executable, "work.py"], directory, Path(root) / ("out-" + directory.name),
                                 baseline_workspace=baseline, repeat=1, timeout=60, same_output=True)
                self.assertEqual(report["verdict"], "broken", directory.name)

    def test_zero_budget_on_sampled_counter_is_flagged(self):
        with test_directory() as root:
            candidate = project(root, "candidate", 1024)
            spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"io_write_bytes": "0B"}}
            report = c.check(spec, [sys.executable, "work.py"], candidate, Path(root) / "out", repeat=1, timeout=60)
            entry = report["budgets"]["io_write_bytes"]
            if entry["status"] == "within":
                self.assertTrue(any("counter is sampled" in f for f in report["findings"]))

    def test_cli_splits_command_after_double_dash(self):
        with test_directory() as root:
            candidate = project(root, "candidate", 1024)
            brief = Path(root) / "brief.json"
            brief.write_text(json.dumps({"schema_version": "1.0", "name": "t", "story": "s",
                                         "budgets": {"wall_seconds": "60s"}}), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["check", str(brief), "--workspace", str(candidate), "--repeat", "1",
                             "--out", str(Path(root) / "out"), "--", sys.executable, "work.py"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["verdict"], "fits")


if __name__ == "__main__":
    unittest.main()
