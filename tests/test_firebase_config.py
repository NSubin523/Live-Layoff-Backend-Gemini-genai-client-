import unittest
from unittest.mock import Mock, patch

from app.services.firebase import firebase_config


class FirebaseInitializationTests(unittest.TestCase):
    def setUp(self):
        patches = [patch.object(firebase_config, 'db', None),
                   patch.object(firebase_config.firebase_admin, '_apps', {}),
                   patch('app.services.firebase.firebase_config.os.getenv', return_value='/synthetic/credentials.json'),
                   patch('app.services.firebase.firebase_config.Path.exists', return_value=True),
                   patch.object(firebase_config.credentials, 'Certificate'),
                   patch.object(firebase_config.firebase_admin, 'initialize_app'),
                   patch.object(firebase_config.firestore, 'client'),
                   patch('builtins.print')]
        mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.getenv, self.exists, self.certificate, self.initialize, self.client = mocks[2:7]

    def test_new_app_initializes_credentials_and_database(self):
        result = firebase_config.initialize_firebase()
        self.certificate.assert_called_once_with('/synthetic/credentials.json')
        self.initialize.assert_called_once_with(self.certificate.return_value)
        self.assertIs(result, self.client.return_value)
        self.assertIs(firebase_config.db, result)

    def test_existing_app_and_database_are_reused(self):
        database = Mock()
        with patch.object(firebase_config.firebase_admin, '_apps', {'default': Mock()}), patch.object(firebase_config, 'db', database):
            self.assertIs(firebase_config.initialize_firebase(), database)
        self.client.assert_not_called()
        self.initialize.assert_not_called()
        self.getenv.assert_not_called()

    def test_existing_app_creates_database_client_if_missing(self):
        with patch.object(firebase_config.firebase_admin, '_apps', {'default': Mock()}):
            self.assertIs(firebase_config.initialize_firebase(), self.client.return_value)
        self.client.assert_called_once()
        self.initialize.assert_not_called()

    def test_missing_credential_configuration_fails_before_initialization(self):
        self.getenv.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'GOOGLE_APPLICATION_CREDENTIALS'):
            firebase_config.initialize_firebase()
        self.initialize.assert_not_called()

    def test_missing_credential_file_fails_before_initialization(self):
        self.exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            firebase_config.initialize_firebase()
        self.initialize.assert_not_called()

    def test_invalid_credentials_and_client_failure_are_wrapped(self):
        for target in (self.certificate, self.client):
            with self.subTest(target=target):
                target.side_effect = ValueError('initialization failed')
                with self.assertRaisesRegex(RuntimeError, 'Critical error establishing Firebase client context'):
                    firebase_config.initialize_firebase()
                target.side_effect = None
