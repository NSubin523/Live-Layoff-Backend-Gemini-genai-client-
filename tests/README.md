# Backend unit tests

From the backend project root, with its virtual environment active:

```bash
python -B -m unittest discover -s tests -v
```

Run just feed ingestion and persistence tests:

```bash
python -B -m unittest tests.test_feed -v
```

The suite uses standard-library `unittest`, in-memory Firestore fakes, and mocked
Gemini, Firebase authentication/initialization, and SQLAlchemy sessions. It does
not make API calls, connect to databases, or require real credentials. Telemetry
imports use a dummy database URL without opening a connection.

Coverage includes feed event creation/merging at the 30-day boundary, history
pagination and user isolation, layoff filtering, telemetry commit/rollback,
model response validation, authentication failures, Firebase startup, and the
existing conversation/streaming regressions. These tests validate backend logic,
not live model quality or Firestore index configuration.
