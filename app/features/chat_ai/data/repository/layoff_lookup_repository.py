from datetime import datetime, timezone
from typing import List, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from app.features.chat_ai.data.dto.chat_dto import LayoffRecord
from app.services.firebase import firebase_config

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class LayoffLookupRepository:
    """Read-only lookups against the shared 'layoffs' collection (owned by feed).

    Chat never writes here — it only grounds answers in existing records.
    Company lookup resolves capitalization against existing stored names
    when the exact query has no results.
    """

    collection_name = "layoffs"

    def _collection(self):
        db = firebase_config.db
        if db is None:
            raise RuntimeError("Database connection uninitialized")
        return db.collection(self.collection_name)

    def _to_record(self, doc) -> LayoffRecord:
        data = doc.to_dict()
        return LayoffRecord(
            id=doc.id,
            company_name=data.get("company_name") or "",
            impact_count=data.get("impact_count"),
            status=data.get("status"),
            industry=data.get("industry"),
            location=data.get("location"),
            company_site=data.get("company_site"),
            summary=data.get("summary"),
            trend_direction=data.get("trend_direction"),
            logo_url=data.get("logo_url"),
            reported_at=data.get("reported_at"),
        )

    def _apply_since(self, query, since: Optional[datetime]):
        if since is not None:
            query = query.where(filter=FieldFilter("reported_at", ">=", since))
        return query

    def find_latest_by_company(
        self,
        company_name: str,
        limit: int = 3,
        since: Optional[datetime] = None,
    ) -> List[LayoffRecord]:
        records = self._find_exact_company(company_name, limit, since)
        if records:
            return records

        # Existing documents have no normalized search field. Resolve their
        # spelling without changing display names or relying on model casing.
        # This fallback reads the collection's company-name projection;
        # a normalized indexed field + backfill is preferable at larger scale.
        key = company_name.strip().casefold()
        names = {
            name
            for doc in self._collection().select(["company_name"]).stream()
            if isinstance(name := (doc.to_dict() or {}).get("company_name"), str)
            and name.strip().casefold() == key
            and name != company_name
        }
        for name in sorted(names):
            records.extend(self._find_exact_company(name, limit, since))
        records.sort(key=lambda r: r.reported_at or _EPOCH, reverse=True)
        return records[:limit]

    def _find_exact_company(
        self, company_name: str, limit: int, since: Optional[datetime]
    ) -> List[LayoffRecord]:
        query = self._collection().where(
            filter=FieldFilter("company_name", "==", company_name)
        )
        query = self._apply_since(query, since)
        docs = query.order_by("reported_at", direction="DESCENDING").limit(limit).stream()
        return [self._to_record(d) for d in docs]

    def find_by_companies(
        self,
        companies: List[str],
        limit_per_company: int = 3,
        since: Optional[datetime] = None,
    ) -> List[LayoffRecord]:
        # Avoid duplicate records when the model repeats a company with
        # different capitalization. Results are merged newest-first.
        records: List[LayoffRecord] = []
        seen = set()
        for name in companies:
            key = name.strip().casefold()
            if key in seen:
                continue
            seen.add(key)
            records.extend(self.find_latest_by_company(name, limit_per_company, since))
        records.sort(key=lambda r: r.reported_at or _EPOCH, reverse=True)
        return records

    def find_latest(
        self,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> List[LayoffRecord]:
        """Most recent layoff records, no company/industry filter.
        Single-field order_by — no composite index needed."""
        query = self._apply_since(self._collection(), since)
        docs = query.order_by("reported_at", direction="DESCENDING").limit(limit).stream()
        return [self._to_record(d) for d in docs]

    def find_by_industry(
        self,
        industry: str,
        limit: int = 5,
        since: Optional[datetime] = None,
    ) -> List[LayoffRecord]:
        # NOTE: where(industry ==) + order_by(reported_at) needs a composite
        # index on (industry, reported_at). If it's missing, Firestore raises
        # with a console link to create it — one click.
        query = self._collection().where(filter=FieldFilter("industry", "==", industry))
        query = self._apply_since(query, since)
        docs = query.order_by("reported_at", direction="DESCENDING").limit(limit).stream()
        return [self._to_record(d) for d in docs]
