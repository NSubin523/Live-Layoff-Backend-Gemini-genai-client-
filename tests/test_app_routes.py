import os
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/test'}), patch('dotenv.load_dotenv'):
    from main import app

from fastapi.testclient import TestClient


class AppRouteMigrationTests(unittest.TestCase):
    def test_feed_is_retired_but_python_features_remain_registered(self):
        paths = {route.path for route in app.routes}
        self.assertNotIn('/api/v1/feed', paths)
        self.assertTrue({'/api/v1/chat', '/api/v1/chat/history', '/api/v1/notifications/send', '/health'} <= paths)
        self.assertEqual(TestClient(app).get('/api/v1/feed').status_code, 404)

    def test_telemetry_is_retired(self):
        paths = {route.path for route in app.routes}
        self.assertNotIn('/api/v1/telemetry/batch', paths)
        self.assertEqual(TestClient(app).post('/api/v1/telemetry/batch', json={'events': []}).status_code, 404)
