from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "tools/setup-linux.sh").read_text()
PYTHON = SCRIPT.split("python3 - <<'CHILI_WSL_CONFIG_PY'\n", 1)[1].split("\nCHILI_WSL_CONFIG_PY", 1)[0]
NAMESPACE = {"__name__": "test_import"}
exec(compile(PYTHON, "embedded-wsl-config-helper", "exec"), NAMESPACE)
enable_systemd = NAMESPACE["enable_systemd"]


class WslConfigurationTests(unittest.TestCase):
    def test_new_config_and_idempotence(self):
        result = enable_systemd("")
        self.assertEqual(result, "[boot]\nsystemd=true\n")
        self.assertEqual(enable_systemd(result), result)

    def test_preserves_other_settings_comments_and_boot_command(self):
        original = "# keep\n[boot]\ncommand=echo ready\nsystemd=false # prior\n[automount]\nroot=/drives/\n[user]\ndefault=tester\n"
        self.assertEqual(enable_systemd(original), original.replace("systemd=false", "systemd=true"))

    def test_inserts_key_before_next_section(self):
        original = "[boot]\ncommand=echo ready\n[interop]\nenabled=true\n"
        self.assertEqual(enable_systemd(original), "[boot]\ncommand=echo ready\nsystemd=true\n[interop]\nenabled=true\n")

    def test_handles_missing_final_newline(self):
        self.assertEqual(enable_systemd("[boot]"), "[boot]\nsystemd=true\n")
        self.assertEqual(enable_systemd("[user]\ndefault=tester"), "[user]\ndefault=tester\n[boot]\nsystemd=true\n")

    def test_ambiguous_configuration_rejected(self):
        for config in ("[boot]\nsystemd=false\nsystemd=true\n", "[boot]\n[boot]\n"):
            with self.subTest(config=config), self.assertRaises(ValueError):
                enable_systemd(config)


if __name__ == "__main__":
    unittest.main()
