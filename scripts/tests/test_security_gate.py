import json
import tempfile
import unittest
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('gate', Path(__file__).parents[1] / 'check_sarif.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SecurityGateTests(unittest.TestCase):
    def test_missing_reports_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                gate.check_reports(directory)

    def test_high_findings_block_even_when_result_level_is_warning(self):
        self.assertEqual(self.scan('8.1', [{'ruleId': 'security/query', 'level': 'warning'}]), ['security/query'])

    def test_medium_and_clean_reports_pass(self):
        self.assertEqual(self.scan('5.0', [{'ruleId': 'security/query'}]), [])
        self.assertEqual(self.scan('9.0', []), [])

    def test_rule_index_and_missing_metadata(self):
        self.assertEqual(self.scan('9.0', [{'ruleIndex': 0}]), ['security/query'])
        with self.assertRaises(ValueError):
            self.scan('9.0', [{'ruleId': 'unknown'}])

    def scan(self, severity, results):
        with tempfile.TemporaryDirectory() as directory:
            report = {'version': '2.1.0', 'runs': [{'tool': {'driver': {'rules': [
                {'id': 'security/query', 'properties': {'security-severity': severity}}
            ]}}, 'results': results}]}
            Path(directory, 'report.sarif').write_text(json.dumps(report))
            return gate.check_reports(directory)
