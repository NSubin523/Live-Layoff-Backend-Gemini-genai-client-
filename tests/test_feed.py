import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.features.feed.data.model.company_layoff_extraction import CompanyLayoffExtraction
from app.features.feed.data.repository.feed_repository import FeedRepository
from app.features.feed.service.feed_ingestion_service import FeedIngestionService
from tests.fakes_firestore import Firestore

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def extraction(**changes):
    return CompanyLayoffExtraction(**(dict(
        company_name='Meta', impact_count=3000, status='Confirmed', industry='Software',
        location='Bay Area', company_url='meta.com', company_category='Technology',
        summary='Meta cut jobs. Restructuring affected multiple teams.', trend_direction='increasing',
    ) | changes))


class FeedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.engine = Mock()
        with patch('app.features.feed.service.feed_ingestion_service.BaseGeminiService', return_value=self.engine):
            self.service = FeedIngestionService()

    def test_trims_story_and_returns_typed_extraction(self):
        expected = extraction()
        self.engine.generate_structured_output.return_value = expected
        result = self.service.process_raw_story('  Meta cuts jobs.\n ')
        self.assertIs(result, expected)
        kwargs = self.engine.generate_structured_output.call_args.kwargs
        self.assertTrue(kwargs['prompt'].endswith('Meta cuts jobs.'))
        self.assertIs(kwargs['response_schema'], CompanyLayoffExtraction)
        self.assertIn('Rumored', kwargs['system_instruction'])

    def test_unverified_extraction_preserves_unknown_impact_count(self):
        self.engine.generate_structured_output.return_value = extraction(status='Rumored', impact_count=None)
        result = self.service.process_raw_story('Unconfirmed reports of job cuts')
        self.assertEqual(result.status, 'Rumored')
        self.assertIsNone(result.impact_count)

    def test_model_failure_propagates(self):
        self.engine.generate_structured_output.side_effect = RuntimeError('model unavailable')
        with self.assertRaisesRegex(RuntimeError, 'model unavailable'):
            self.service.process_raw_story('A story')


class FeedRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = Firestore()
        self.repo = FeedRepository()
        connection = patch('app.features.feed.data.repository.feed_repository.firebase_config.db', self.db)
        connection.start()
        self.addCleanup(connection.stop)
        clock = patch('app.features.feed.data.repository.feed_repository.datetime')
        self.clock = clock.start()
        self.clock.now.return_value = NOW
        self.addCleanup(clock.stop)

    def test_new_company_creates_event_with_metrics_and_server_dates(self):
        result = self.repo.check_and_save_layoff(extraction())
        self.assertEqual(result['action'], 'created_new_layoff_event')
        record = self.db.rows['layoffs'][result['id']]
        self.assertEqual(record['company_name'], 'Meta')
        self.assertEqual(record['impact_count'], 3000)
        self.assertEqual(record['status'], 'Confirmed')
        self.assertEqual(record['company_site'], 'meta.com')
        for key in ('created_at', 'reported_at', 'updated_at'):
            self.assertEqual(record[key], NOW)

    def test_recent_event_updates_without_replacing_original_dates(self):
        original_date = NOW - timedelta(days=29, hours=23)
        self.db.rows['layoffs'] = {'existing': dict(company_name='Meta', reported_at=original_date, created_at=original_date)}
        result = self.repo.check_and_save_layoff(extraction(status='Rumored', impact_count=None))
        self.assertEqual(result, {'status': 'success', 'action': 'merged_update', 'id': 'existing'})
        self.assertEqual(len(self.db.rows['layoffs']), 1)
        record = self.db.rows['layoffs']['existing']
        self.assertEqual(record['reported_at'], original_date)
        self.assertEqual(record['created_at'], original_date)
        self.assertEqual(record['updated_at'], NOW)
        self.assertIsNone(record['impact_count'])

    def test_thirty_day_boundary_and_older_events_create_new_records(self):
        for age in (timedelta(days=30), timedelta(days=31)):
            with self.subTest(age=age):
                self.db.rows['layoffs'] = {'old': dict(company_name='Meta', reported_at=NOW - age)}
                result = self.repo.check_and_save_layoff(extraction())
                self.assertEqual(result['action'], 'created_new_layoff_event')
                self.assertEqual(len(self.db.rows['layoffs']), 2)
                self.assertEqual(self.db.rows['layoffs']['old']['reported_at'], NOW - age)

    def test_only_latest_matching_company_is_updated(self):
        self.db.rows['layoffs'] = {
            'other': dict(company_name='Amazon', reported_at=NOW),
            'old': dict(company_name='Meta', reported_at=NOW - timedelta(days=60)),
            'recent': dict(company_name='Meta', reported_at=NOW - timedelta(days=2)),
        }
        result = self.repo.check_and_save_layoff(extraction())
        self.assertEqual(result['id'], 'recent')
        self.assertNotIn('impact_count', self.db.rows['layoffs']['other'])
        self.assertNotIn('impact_count', self.db.rows['layoffs']['old'])

    def test_feed_returns_newest_first_respects_limit_and_adds_document_ids(self):
        self.db.rows['layoffs'] = {str(i): dict(company_name=f'Company {i}', reported_at=NOW - timedelta(days=i)) for i in range(4)}
        result = self.repo.generate_data_for_layoff_feed(limit=2)
        self.assertEqual([r['id'] for r in result], ['0', '1'])
        self.assertEqual(result[0]['company_name'], 'Company 0')
        self.assertNotIn('id', self.db.rows['layoffs']['0'])

    def test_empty_feed_returns_empty_list(self):
        self.assertEqual(self.repo.generate_data_for_layoff_feed(), [])

    def test_uninitialized_database_reports_errors(self):
        with patch('app.features.feed.data.repository.feed_repository.firebase_config.db', None):
            with self.assertRaisesRegex(RuntimeError, 'Database connection uninitialized'):
                self.repo.generate_data_for_layoff_feed()
            with self.assertRaisesRegex(RuntimeError, 'data write transaction failed'):
                self.repo.check_and_save_layoff(extraction())

    def test_write_failure_is_wrapped(self):
        document = Mock()
        document.set.side_effect = OSError('write unavailable')
        with patch('tests.fakes_firestore.Collection.document', return_value=document):
            with self.assertRaisesRegex(RuntimeError, 'data write transaction failed: write unavailable'):
                self.repo.check_and_save_layoff(extraction())
