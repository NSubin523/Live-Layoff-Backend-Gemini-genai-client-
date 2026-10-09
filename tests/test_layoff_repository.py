import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.features.chat_ai.data.repository.layoff_lookup_repository import LayoffLookupRepository
from tests.fakes_firestore import Firestore

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class LayoffRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = Firestore({'layoffs': {
            'new': dict(company_name='Meta', industry='Software', reported_at=NOW, impact_count=42, status='Confirmed'),
            'other': dict(company_name='Bank', industry='Finance', reported_at=NOW - timedelta(days=1)),
            'old': dict(company_name='Meta', industry='Software', reported_at=NOW - timedelta(days=90)),
        }})
        self.repo = LayoffLookupRepository()
        connection = patch('app.features.chat_ai.data.repository.layoff_lookup_repository.firebase_config.db', self.db)
        connection.start()
        self.addCleanup(connection.stop)

    def test_latest_is_sorted_limited_and_filtered_by_date(self):
        self.assertEqual([r.id for r in self.repo.find_latest(limit=2)], ['new', 'other'])
        self.assertEqual([r.id for r in self.repo.find_latest(since=NOW - timedelta(days=7))], ['new', 'other'])

    def test_industry_filters_preserve_order_limit_and_date_window(self):
        self.assertEqual([r.id for r in self.repo.find_by_industry('Software')], ['new', 'old'])
        self.assertEqual([r.id for r in self.repo.find_by_industry('Software', limit=1)], ['new'])
        self.assertEqual([r.id for r in self.repo.find_by_industry('Software', since=NOW - timedelta(days=7))], ['new'])
        self.assertEqual(self.repo.find_by_industry('Unknown'), [])

    def test_multiple_companies_merge_newest_first_with_per_company_limit(self):
        self.assertEqual([r.id for r in self.repo.find_by_companies(['Bank', 'Meta'], limit_per_company=1)], ['new', 'other'])

    def test_sparse_documents_map_optional_fields_to_none(self):
        record = self.repo.find_by_industry('Finance')[0]
        self.assertEqual(record.company_name, 'Bank')
        self.assertIsNone(record.impact_count)
        self.assertIsNone(record.logo_url)
        self.assertIsNone(record.status)

    def test_empty_results_and_uninitialized_database(self):
        self.db.rows['layoffs'] = {}
        self.assertEqual(self.repo.find_latest(), [])
        with patch('app.features.chat_ai.data.repository.layoff_lookup_repository.firebase_config.db', None):
            with self.assertRaisesRegex(RuntimeError, 'Database connection uninitialized'):
                self.repo.find_latest()
