import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Import the real SQLAlchemy model using a dummy URL. No connection is opened,
# and dotenv loading is disabled so tests never consume local credentials.
with patch.dict(os.environ, {'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/test'}), patch('dotenv.load_dotenv'):
    from app.features.telemetry.data.dto.telemetry_event_dto import TelemetryEventCreate
    from app.features.telemetry.service.telemetry_service import TelemetryService
    from app.features.telemetry.service.telemetry_service_dependency import get_telemetry_service


class TelemetryServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = Mock()
        self.db.commit, self.db.rollback = AsyncMock(), AsyncMock()
        self.service = TelemetryService(self.db)

    async def test_empty_batch_does_not_start_transaction(self):
        await self.service.insert_batch_telemetry([])
        self.db.add_all.assert_not_called()
        self.db.commit.assert_not_awaited()
        self.db.rollback.assert_not_awaited()

    async def test_batch_preserves_payloads_and_commits_once(self):
        events = [TelemetryEventCreate(user_id='a', event_name='chat_sent', event_payload={'length': 12}),
                  TelemetryEventCreate(user_id='b', event_name='screen_opened')]
        await self.service.insert_batch_telemetry(events)
        inserted = self.db.add_all.call_args.args[0]
        self.assertEqual([(row.user_id, row.event_name, row.event_payload) for row in inserted],
                         [('a', 'chat_sent', {'length': 12}), ('b', 'screen_opened', None)])
        self.db.commit.assert_awaited_once()
        self.db.rollback.assert_not_awaited()

    async def test_commit_failure_rolls_back_and_preserves_exception(self):
        failure = RuntimeError('commit failed')
        self.db.commit.side_effect = failure
        with self.assertLogs('app.features.telemetry.service.telemetry_service', level='ERROR'):
            with self.assertRaises(RuntimeError) as raised:
                await self.service.insert_batch_telemetry([TelemetryEventCreate(user_id='a', event_name='event')])
        self.assertIs(raised.exception, failure)
        self.db.rollback.assert_awaited_once()

    async def test_add_failure_rolls_back_without_committing(self):
        self.db.add_all.side_effect = RuntimeError('add failed')
        with self.assertLogs('app.features.telemetry.service.telemetry_service', level='ERROR'):
            with self.assertRaisesRegex(RuntimeError, 'add failed'):
                await self.service.insert_batch_telemetry([TelemetryEventCreate(user_id='a', event_name='event')])
        self.db.rollback.assert_awaited_once()
        self.db.commit.assert_not_awaited()

    def test_dependency_uses_supplied_session(self):
        self.assertIs(get_telemetry_service(self.db).db, self.db)
