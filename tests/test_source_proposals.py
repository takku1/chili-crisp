import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_core import test_directory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("proposal_transport", ROOT / "tools/propose-codex.py")
TRANSPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSPORT)


class SourceTransportTests(unittest.TestCase):
    def fixture(self, directory):
        work = Path(directory)
        workspace = work / "workspace"
        workspace.mkdir()
        source = workspace / "module.py"
        source.write_text("x = 1\n")
        request = work / "request.json"
        request.write_text('{"concept": "transport fixture"}')
        response = work / "research.json"
        argv = ["propose-codex", str(request), str(response), str(workspace), "--source", "module.py", "--seconds", "1"]
        return work, source, response, argv

    def test_timeout_retains_failure_and_does_not_change_source(self):
        with test_directory() as directory:
            work, source, _, argv = self.fixture(directory)
            original = subprocess.Popen

            def fake_cli(command, **kwargs):
                return original([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

            with patch.object(sys, "argv", argv), patch.object(TRANSPORT.shutil, "which", return_value="codex"), \
                 patch.object(TRANSPORT.subprocess, "Popen", side_effect=fake_cli):
                with self.assertRaises(subprocess.TimeoutExpired):
                    TRANSPORT.main()
            metadata = json.loads((work / "proposal-metadata.json").read_text())
            self.assertIsNotNone(metadata["failure"])
            self.assertEqual(metadata["cleanup_errors"], [])
            self.assertEqual(source.read_text(), "x = 1\n")

    def run_fixture(self, unexpected_tool=False):
        with test_directory() as directory:
            work, source, response, argv = self.fixture(directory)
            marker = work / "candidate-executed"
            code = f"from pathlib import Path\nPath({str(marker)!r}).write_text('unexpected execution')\n"
            proposal = {"source": code, "hypothesis": "fixture", "mechanism": "fixture",
                "falsification": "fixture", "sources": [{"reference": "local fixture", "supports": "transport"}]}
            payload = json.dumps(proposal)
            answer = work / "source-proposal.json"
            script = ("import sys; from pathlib import Path; Path(sys.argv[1]).write_text(sys.argv[2]); "
                      + ("print('{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}')"
                         if unexpected_tool else "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1}}')"))
            original = subprocess.Popen

            def fake_cli(command, **kwargs):
                self.assertIn("read-only", command)
                self.assertIn("shell_tool", command)
                return original([sys.executable, "-c", script, str(answer), payload], **kwargs)

            with patch.object(sys, "argv", argv), patch.object(TRANSPORT.shutil, "which", return_value="codex"), \
                 patch.object(TRANSPORT.subprocess, "Popen", side_effect=fake_cli), \
                 contextlib.redirect_stdout(io.StringIO()):
                if unexpected_tool:
                    with self.assertRaises(ValueError):
                        TRANSPORT.main()
                    self.assertEqual(source.read_text(), "x = 1\n")
                    self.assertFalse(response.exists())
                else:
                    TRANSPORT.main()
                    self.assertEqual(source.read_text(), code)
                    self.assertFalse(marker.exists())
                    self.assertEqual(json.loads(response.read_text())["hypothesis"], "fixture")

    def test_valid_source_response_is_applied_without_execution(self):
        self.run_fixture()

    def test_unexpected_tool_event_rejects_proposal(self):
        self.run_fixture(unexpected_tool=True)
