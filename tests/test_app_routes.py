import os
import runpy
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/test'}), patch('dotenv.load_dotenv'):
    from main import app

from fastapi.testclient import TestClient


class AppRouteMigrationTests(unittest.TestCase):
    def test_cloud_can_disable_notification_delivery(self):
        with patch.dict(os.environ, {'ENABLE_NOTIFICATION_SEND': 'false'}), patch('dotenv.load_dotenv'):
            cloud_app = runpy.run_path('main.py')['app']
        response = TestClient(cloud_app).post('/api/v1/notifications/send', json={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(TestClient(cloud_app).get('/health').status_code, 200)
        self.assertIn('/api/v1/chat', cloud_app.openapi()['paths'])

    def test_feed_is_retired_but_python_features_remain_registered(self):
        paths = set(app.openapi()['paths'])
        self.assertNotIn('/api/v1/feed', paths)
        self.assertTrue({'/api/v1/chat', '/api/v1/chat/history', '/api/v1/notifications/send', '/health'} <= paths)
        self.assertEqual(TestClient(app).get('/api/v1/feed').status_code, 404)

    def test_telemetry_is_retired(self):
        paths = set(app.openapi()['paths'])
        self.assertNotIn('/api/v1/telemetry/batch', paths)
        self.assertEqual(TestClient(app).post('/api/v1/telemetry/batch', json={'events': []}).status_code, 404)
