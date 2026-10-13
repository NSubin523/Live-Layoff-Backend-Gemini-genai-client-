"""Fail CI on high/critical security findings in CodeQL's SARIF reports."""
import json
import sys
from pathlib import Path


def check_reports(directory):
    reports = list(Path(directory).rglob('*.sarif'))
    if not reports:
        raise ValueError('CodeQL produced no SARIF reports')
    findings = []
    for report in reports:
        document = json.loads(report.read_text())
        if document.get('version') != '2.1.0' or not document.get('runs'):
            raise ValueError(f'Invalid SARIF report: {report.name}')
        for run in document['runs']:
            rules = run['tool']['driver'].get('rules', [])
            by_id = {rule['id']: rule for rule in rules}
            for result in run.get('results', []):
                rule = by_id.get(result.get('ruleId'))
                if rule is None and 'ruleIndex' in result:
                    rule = rules[result['ruleIndex']]
                if rule is None:
                    raise ValueError('Finding has no matching rule metadata')
                severity = rule.get('properties', {}).get('security-severity')
                if severity is not None and float(severity) >= 7:
                    findings.append(rule['id'])
    return findings


if __name__ == '__main__':
    findings = check_reports(sys.argv[1])
    if findings:
        raise SystemExit('High/critical CodeQL findings: ' + ', '.join(sorted(set(findings))))
    print('No high/critical CodeQL security findings')
