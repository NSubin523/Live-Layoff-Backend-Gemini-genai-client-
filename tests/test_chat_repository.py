import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.features.chat_ai.data.dto.chat_dto import CreateChatMessage
from app.features.chat_ai.data.model.chat_message import ChatIntentType, ChatRole
from app.features.chat_ai.data.repository.chat_repository import ChatRepository
from tests.fakes_firestore import Firestore

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class ChatRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = Firestore()
        self.repo = ChatRepository()
        connection = patch('app.features.chat_ai.data.repository.chat_repository.firebase_config.db', self.db)
        connection.start()
        self.addCleanup(connection.stop)
        clock = patch('app.features.chat_ai.data.repository.chat_repository.datetime')
        self.clock = clock.start()
        self.clock.now.return_value = NOW
        self.addCleanup(clock.stop)

    def save(self, user='user-1', **changes):
        return self.repo.save(CreateChatMessage(**(dict(user_id=user, role=ChatRole.USER, text='hi') | changes)))

    def test_save_assigns_id_and_twenty_four_hour_expiry(self):
        saved = self.save()
        stored = self.db.rows['chat_history/user-1/messages'][saved.message_id]
        self.assertEqual(saved.created_at, NOW)
        self.assertEqual(saved.expires_at, NOW + timedelta(hours=24))
        self.assertEqual(stored['role'], 'user')
        self.assertIsNone(stored['intent'])
        self.assertEqual(stored['card_ids'], [])

    def test_agent_intent_and_cards_round_trip(self):
        saved = self.save(role=ChatRole.AGENT, text='Here are records', intent=ChatIntentType.LAYOFF_QUERY, card_ids=['layoff-1'])
        result = self.repo.get_history('user-1').messages[0]
        self.assertEqual(result, saved)

    def test_history_is_isolated_by_user(self):
        self.save('alice', text='Alice only')
        self.save('bob', text='Bob only')
        self.assertEqual([m.text for m in self.repo.get_history('alice').messages], ['Alice only'])

    def test_pagination_is_oldest_first_and_cursor_excludes_previous_page(self):
        for i in range(5):
            self.clock.now.return_value = NOW + timedelta(minutes=i)
            self.save(text=str(i))
        first = self.repo.get_history('user-1', limit=2)
        self.assertEqual([m.text for m in first.messages], ['3', '4'])
        self.assertTrue(first.has_more)
        self.assertEqual(first.next_before, NOW + timedelta(minutes=3))
        second = self.repo.get_history('user-1', limit=2, before=first.next_before)
        self.assertEqual([m.text for m in second.messages], ['1', '2'])
        last = self.repo.get_history('user-1', limit=2, before=second.next_before)
        self.assertEqual([m.text for m in last.messages], ['0'])
        self.assertFalse(last.has_more)
        self.assertIsNone(last.next_before)

    def test_exact_page_size_has_no_more_and_empty_history_has_no_cursor(self):
        self.save()
        result = self.repo.get_history('user-1', limit=1)
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_before)
        empty = self.repo.get_history('unknown')
        self.assertEqual(empty.messages, [])
        self.assertFalse(empty.has_more)

    def test_legacy_missing_card_ids_default_to_empty(self):
        saved = self.save()
        del self.db.rows['chat_history/user-1/messages'][saved.message_id]['card_ids']
        self.assertEqual(self.repo.get_history('user-1').messages[0].card_ids, [])

    def test_uninitialized_database_fails_both_reads_and_writes(self):
        with patch('app.features.chat_ai.data.repository.chat_repository.firebase_config.db', None):
            for operation in (lambda: self.save(), lambda: self.repo.get_history('user-1')):
                with self.assertRaisesRegex(RuntimeError, 'Database connection uninitialized'):
                    operation()
