"""Proposal transports must preserve failures and reject observed tool execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_core import test_directory

spec = importlib.util.spec_from_file_location('model_transport',
    Path(__file__).resolve().parents[1] / 'tools/propose-model.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class ModelTransportTests(unittest.TestCase):
    def test_rate_limit_response_is_preserved_and_rejected(self):
        with test_directory() as directory:
            work = Path(directory) / 'work'
            work.mkdir()
            response = json.dumps({'subtype': 'success', 'is_error': True,
                                   'api_error': 'usage_limit_reached'})
            completed = subprocess.CompletedProcess([], 1, response, '')
            with patch.object(transport.subprocess, 'run', return_value=completed):
                with self.assertRaisesRegex(ValueError, 'Claude proposal failed'):
                    transport.run_claude('claude', 'prompt', 'sonnet', 10, 1, work)
            self.assertEqual((Path(directory) / 'provider-stdout.txt').read_text(), response)

    def test_codex_schema_pins_files_and_tool_execution_rejects(self):
        with test_directory() as directory:
            work = Path(directory) / 'work'
            work.mkdir()

            def provider(command, **kwargs):
                (work / 'proposal.json').write_text('{}')
                event = {'type': 'item.completed', 'item': {'type': 'unknown_future_tool'}}
                return subprocess.CompletedProcess(command, 0, json.dumps(event), '')

            with patch.object(transport.subprocess, 'run', side_effect=provider):
                with self.assertRaisesRegex(ValueError, 'used tools'):
                    transport.run_codex('codex', 'prompt', 'test-model', 10, work, ['program.c'])
            schema = json.loads((work / 'proposal.schema.json').read_text())
            files = schema['properties']['files']
            self.assertEqual(files['required'], ['program.c'])
            self.assertFalse(files['additionalProperties'])
            self.assertEqual(set(files['properties']), {'program.c'})


if __name__ == '__main__':
    unittest.main()
