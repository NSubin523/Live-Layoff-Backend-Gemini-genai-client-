from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from google.cloud.firestore_v1.base_query import FieldFilter
from app.services.firebase import firebase_config
from app.features.feed.data.model.company_layoff_extraction import CompanyLayoffExtraction


class FeedRepository:
    """
    Handles all data persistence mutations and historical lookup logic
    for layoff events inside the Firestore collection.
    """

    def __init__(self):
        # Bind reference straight to our global firestore entity collection
        self.collection_name = "layoffs"

    def check_and_save_layoff(self, ai_data: CompanyLayoffExtraction) -> dict:
        """
        Queries Firestore for an existing company event, applies the 30-day
        lookback evaluation rule, and either updates or creates a document record.
        """
        try:
            db = firebase_config.db
            # 1. Historical Lookup: Find the latest record matching this company name
            existing_records = db.collection(self.collection_name).where(
                filter=FieldFilter("company_name", "==", ai_data.company_name)
            ).order_by("reported_at", direction="DESCENDING").limit(1).get()

            timestamp_now = datetime.now(timezone.utc)

            # 2. Build the primary document data dictionary mapping
            doc_payload = {
                "company_name": ai_data.company_name,
                "impact_count": ai_data.impact_count,
                "status": ai_data.status,
                "industry": ai_data.industry,
                "location": ai_data.location,
                "company_site": ai_data.company_url,
                "summary": ai_data.summary,
                "trend_direction": ai_data.trend_direction,
                "logo_url": f"https://logo.clearbit.com/{ai_data.company_url}",
                "updated_at": timestamp_now  # Track exactly when our system last touched this file
            }

            # 3. Time Window Evaluation Check
            if existing_records:
                latest_record = existing_records[0].to_dict()
                latest_record_id = existing_records[0].id
                latest_reported_date = latest_record["reported_at"]

                # Calculate days between the system time and the historical record
                time_difference = timestamp_now - latest_reported_date

                if time_difference < timedelta(days=30):
                    # SCENARIO A: It is an update to an active news wave. Merge metrics.
                    db.collection(self.collection_name).document(latest_record_id).update(doc_payload)
                    return {"status": "success", "action": "merged_update", "id": latest_record_id}

            # SCENARIO B: Brand new event discovery or older historical dataset (>30 days old)
            # Establish fresh independent tracking timestamps and a new unique UUID
            doc_payload["reported_at"] = timestamp_now
            doc_payload["created_at"] = timestamp_now

            new_doc_ref = db.collection(self.collection_name).document()
            new_doc_ref.set(doc_payload)

            return {"status": "success", "action": "created_new_layoff_event", "id": new_doc_ref.id}

        except Exception as error:
            raise RuntimeError(f"FeedRepository data write transaction failed: {str(error)}")

    def generate_data_for_layoff_feed(self, limit: int = 25) -> List[Dict[str, Any]]:
        db = firebase_config.db
        if db is None:
            raise RuntimeError("Database connection uninitialized")

        docs = (db.collection(self.collection_name)
               .order_by("reported_at", direction="DESCENDING")
               .limit(limit)
               .stream())

        feed = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id
            feed.append(doc_data)

        if not feed:
            return [] #Firestore collection is currently empty

        return feed
