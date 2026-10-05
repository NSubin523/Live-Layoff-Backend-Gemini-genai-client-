import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.features.chat_ai.data.repository.layoff_lookup_repository import LayoffLookupRepository


class Query:
    """Small Firestore fake with case-sensitive equality and date filters."""
    def __init__(self, rows):
        self.rows = rows

    def where(self, *, filter):
        if filter.op_string == "==":
            rows = [r for r in self.rows if r[filter.field_path] == filter.value]
        else:
            rows = [r for r in self.rows if r[filter.field_path] >= filter.value]
        return Query(rows)

    def select(self, fields):
        return Query([{k: v for k, v in r.items() if k in fields or k == "id"} for r in self.rows])

    def order_by(self, field, direction):
        return Query(sorted(self.rows, key=lambda r: r[field], reverse=True))

    def limit(self, count):
        return Query(self.rows[:count])

    def stream(self):
        return iter(SimpleNamespace(id=r["id"], to_dict=lambda r=r: r) for r in self.rows)


class CompanyLookupTests(unittest.TestCase):
    def setUp(self):
        self.repo = LayoffLookupRepository()
        self.rows = [
            {"id": name, "company_name": name, "reported_at": datetime(2026, 5, 30, tzinfo=timezone.utc)}
            for name in ["Meta", "IBM", "OpenAI", "Metaverse"]
        ]
        self.collection = patch.object(self.repo, "_collection", return_value=Query(self.rows))
        self.collection.start()
        self.addCleanup(self.collection.stop)

    def test_meta_capitalization_returns_same_record(self):
        for name in ["Meta", "META", "meta", "mEtA"]:
            with self.subTest(name=name):
                self.assertEqual([r.id for r in self.repo.find_latest_by_company(name)], ["Meta"])

    def test_acronyms_and_mixed_case_brands_preserve_stored_name(self):
        for query, stored in [("ibm", "IBM"), ("OPENAI", "OpenAI")]:
            self.assertEqual(self.repo.find_latest_by_company(query)[0].company_name, stored)

    def test_unknown_company_returns_no_records(self):
        self.assertEqual(self.repo.find_latest_by_company("Microsoft"), [])

    def test_case_fallback_preserves_date_filter(self):
        since = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.assertEqual(self.repo.find_latest_by_company("META", since=since), [])

    def test_duplicate_company_mentions_do_not_duplicate_records(self):
        self.assertEqual([r.id for r in self.repo.find_by_companies(["Meta", "META"])], ["Meta"])
