import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from firebase_admin import auth
from app.features.auth.service.auth_deps import get_current_user_id


class AuthServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials='synthetic-token')

    async def test_missing_or_empty_credentials_use_guest_without_verification(self):
        with patch('app.features.auth.service.auth_deps.auth.verify_id_token') as verify:
            for credentials in (None, HTTPAuthorizationCredentials(scheme='Bearer', credentials='')):
                with self.assertLogs('app.features.auth.service.auth_deps', level='ERROR'):
                    self.assertEqual(await get_current_user_id(credentials), 'Non-User')
            verify.assert_not_called()

    async def test_valid_token_returns_verified_uid(self):
        with patch('app.features.auth.service.auth_deps.auth.verify_id_token', return_value={'uid': 'user-1'}) as verify:
            self.assertEqual(await get_current_user_id(self.credentials), 'user-1')
            verify.assert_called_once_with('synthetic-token')

    async def test_verified_token_without_uid_is_guest(self):
        with patch('app.features.auth.service.auth_deps.auth.verify_id_token', return_value={}):
            self.assertEqual(await get_current_user_id(self.credentials), 'Non-User')

    async def test_expired_invalid_and_unexpected_failures_return_unauthorized(self):
        for error, expected in [(auth.ExpiredIdTokenError('expired', None), 'expired'),
                                (auth.InvalidIdTokenError('invalid'), 'Invalid Firebase'),
                                (RuntimeError('verification failed'), 'Authentication error')]:
            with self.subTest(error=type(error).__name__):
                with patch('app.features.auth.service.auth_deps.auth.verify_id_token', side_effect=error):
                    with self.assertRaises(HTTPException) as raised:
                        await get_current_user_id(self.credentials)
                self.assertEqual(raised.exception.status_code, 401)
                self.assertIn(expected, raised.exception.detail)
