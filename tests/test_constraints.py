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

    def test_files_left_between_runs_are_flagged(self):
        cache = ("from pathlib import Path\np = Path('cache.txt')\n"
                 "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n")
        spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"wall_seconds": 60}}
        with test_directory() as root:
            baseline = project(root, "baseline", 1024)
            caching = project(root, "caching", 1024, cache)
            report = c.check(spec, [sys.executable, "work.py"], caching, Path(root) / "out-a",
                             baseline_workspace=baseline, repeat=2, timeout=60)
            self.assertEqual(report["verdict"], "incomplete")
            self.assertEqual(report["changed_files"], ["cache.txt"])
            allowed = {**spec, "writes": ["cache.*"]}
            report = c.check(allowed, [sys.executable, "work.py"], caching, Path(root) / "out-b",
                             baseline_workspace=baseline, repeat=1, timeout=60)
            self.assertEqual(report["verdict"], "fits")
            # A file the baseline writes too is normal output, not a cache.
            both = project(root, "both", 1024, cache)
            (Path(root) / "baseline" / "work.py").write_text(
                (both / "work.py").read_text(encoding="utf-8"), encoding="utf-8")
            report = c.check(spec, [sys.executable, "work.py"], both, Path(root) / "out-c",
                             baseline_workspace=baseline, repeat=1, timeout=60)
            self.assertEqual(report["changed_files"], [])

    def test_inputs_are_all_checked_and_hidden_ones_stay_hidden(self):
        echo = "import sys\nprint(sys.argv[1:])\n"
        with test_directory() as root:
            baseline = project(root, "baseline", 1024, echo)
            same = project(root, "same", 1024, echo)
            wrong = project(root, "wrong", 1024, echo + "import sys\nif 'secret-arg' in sys.argv: print('x')\n")
            spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"wall_seconds": 60},
                    "inputs": [{"args": ["a"]}, {"args": ["secret-arg"], "hidden": True}]}
            report = c.check(spec, [sys.executable, "work.py"], same, Path(root) / "out-same",
                             baseline_workspace=baseline, repeat=1, timeout=60, same_output=True)
            self.assertEqual(report["verdict"], "fits")
            self.assertEqual([i["label"] for i in report["inputs"]], ["input 1", "input 2 (hidden)"])
            out = Path(root) / "out-wrong"
            report = c.check(spec, [sys.executable, "work.py"], wrong, out,
                             baseline_workspace=baseline, repeat=1, timeout=60, same_output=True)
            self.assertEqual(report["verdict"], "broken")
            self.assertIn("input 2 (hidden): Candidate stdout differs from the baseline", report["findings"])
            for path in out.rglob("*.json"):
                self.assertNotIn("secret-arg", path.read_text(encoding="utf-8"), path)
            self.assertNotIn("secret-arg", c.render(spec, report))

    def test_where_names_the_allocating_line(self):
        hog = "import sys\nkeep = [bytes(1000) for _ in range(20000)]\nprint(len(keep), sys.argv[1:])\n"
        with test_directory() as root:
            candidate = Path(root) / "candidate"
            candidate.mkdir()
            (candidate / "hog.py").write_text(hog, encoding="utf-8")
            spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"wall_seconds": 60},
                    "inputs": [{"args": ["x"]}]}
            report = c.check(spec, [sys.executable, "hog.py"], candidate, Path(root) / "out",
                             repeat=1, timeout=60, where=True)
            self.assertEqual(report["verdict"], "fits")
            top = report["where"]["sites"][0]
            self.assertEqual((top["file"], top["line"]), ("hog.py", 2))
            self.assertIn("`hog.py:2`", c.render(spec, report))
            report = c.check(spec, ["git", "--version"], candidate, Path(root) / "out-2", repeat=1,
                             timeout=60, where=True)
            self.assertTrue(any("needs a Python command" in f for f in report["findings"]))

    def test_instrument_finds_script_or_module(self):
        from chilicrisp.where import instrument, WRAPPER
        self.assertEqual(instrument(["python3", "-u", "a.py", "x"]), ["python3", "-u", "-c", WRAPPER, "a.py", "x"])
        self.assertEqual(instrument(["py", "-3", "-m", "pkg", "x"]), ["py", "-3", "-c", WRAPPER, "-m", "pkg", "x"])
        self.assertIsNone(instrument(["node", "a.js"]))
        self.assertIsNone(instrument(["python", "-c", "print(1)"]))

    def test_ratchet_saves_tightens_and_catches_regressions(self):
        spec = {"schema_version": "1.0", "name": "t", "story": "s", "budgets": {"wall_seconds": 60}}
        with test_directory() as root:
            candidate = project(root, "candidate", 1024)
            ratchet = Path(root) / "ratchet.json"
            first = c.check(spec, [sys.executable, "work.py"], candidate, Path(root) / "out-1", repeat=1,
                            timeout=60, ratchet=ratchet)
            self.assertEqual(first["verdict"], "fits")
            saved = json.loads(ratchet.read_text(encoding="utf-8"))
            self.assertGreater(saved["metrics"]["wall_seconds"], 0)
            saved["metrics"]["wall_seconds"] = 0.0001
            ratchet.write_text(json.dumps(saved), encoding="utf-8")
            second = c.check(spec, [sys.executable, "work.py"], candidate, Path(root) / "out-2", repeat=1,
                             timeout=60, ratchet=ratchet)
            self.assertEqual(second["verdict"], "over_budget")
            self.assertEqual(second["ratchet"]["regressed"], ["wall_seconds"])
            self.assertEqual(json.loads(ratchet.read_text(encoding="utf-8"))["metrics"]["wall_seconds"], 0.0001)
            with self.assertRaisesRegex(ValueError, "not a ratchet"):
                c.check({**spec, "name": "other"}, [sys.executable, "work.py"], candidate, Path(root) / "out-3",
                        repeat=1, timeout=60, ratchet=ratchet)

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



class EnforcedNamespaceTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(argv)
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def test_main_help_hides_enforced_commands(self):
        _, text, _ = self.run_cli(["-h"])
        self.assertIn("enforced", text)
        for name in ("pressure-map", "cpu-sweep", "frontier"):
            self.assertNotIn(f"\n    {name}", text)

    def test_enforced_lists_its_commands(self):
        code, text, _ = self.run_cli(["enforced"])
        self.assertEqual(code, 0)
        for name in ("runner", "frontier", "recover", "build", "cpu-sweep", "pressure-map"):
            self.assertIn(name, text)
        code, _, err = self.run_cli(["enforced", "check"])
        self.assertEqual(code, 2)
        self.assertIn("unknown enforced command: check", err)

    def test_enforced_and_legacy_names_both_dispatch(self):
        with test_directory() as root:
            for argv in (["enforced", "pressure-map", root], ["pressure-map", root]):
                code, text, _ = self.run_cli(argv)
                self.assertEqual(code, 0, argv)
                self.assertIsInstance(json.loads(text), dict)


if __name__ == "__main__":
    unittest.main()
