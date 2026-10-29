import json
import unittest

from jsonschema import ValidationError
from chilicrisp.oracles import check_ocean
from chilicrisp.runner import ROOT, validate


def output():
    # Representative values from the saved run; tests deliberately alter them.
    return "\n".join([
        "grid=180x80; seasonal solve=0.365s; energy+transport=2.248ms/1800 world seconds; retained ocean field buffers=2.32MiB",
        "relative budget residuals: water=0.000e0, initial salt=5.985e-16, committed heat=1.971e-15",
        *[f"season {i}: SolveReport {{ iterations: 496, relative_residual: 8.3e-8, converged: true }}" for i in range(4)]
    ]) + "\n"


class OceanOracleTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "examples/worldgame-ocean-oracle.json").read_text())

    def test_timing_and_solver_iteration_changes_are_not_physics_failures(self):
        text = output().replace("0.365s", "0.111s").replace("2.248ms", "1.100ms").replace("iterations: 496", "iterations: 120")
        self.assertTrue(check_ocean(text, self.policy)["pass_checks"])

    def test_missing_duplicate_unconverged_and_nonfinite_records_fail(self):
        cases = [output().replace("salt=5.985e-16", "salt=2e-12"),
                 output().replace("converged: true", "converged: false", 1),
                 output().replace("8.3e-8", "NaN"),
                 output().replace("8.3e-8", "1e309"),
                 output().replace("8.3e-8", "2e-7"),
                 output().replace("season 3:", "season 2:"),
                 output().replace("grid=180x80", "grid=90x40"),
                 output().replace("water=0.000e0", "water=-1e-15"),
                 "\n".join(output().splitlines()[:-1]), output() + "unexpected output\n"]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_ocean(text, self.policy)

    def test_exactly_one_oracle_mode_is_required(self):
        manifest = json.loads((ROOT / "examples/experiment.json").read_text())
        workload = manifest["workloads"][0]
        workload["oracle"] = dict(kind="worldgame_ocean_v1", policy_path="owner-policy.json", policy_hash="0" * 64)
        with self.assertRaises(ValidationError):
            validate(manifest, "experiment")
        del workload["expected_stdout_hash"]
        validate(manifest, "experiment")
        del workload["oracle"]
        with self.assertRaises(ValidationError):
            validate(manifest, "experiment")


if __name__ == "__main__":
    unittest.main()
