import os
import urllib.request
import xml.etree.ElementTree as ET

import time
from dotenv import load_dotenv

# Initialize the environment wrapper context first
load_dotenv()

from app.services.firebase.firebase_config import initialize_firebase
from app.features.feed.service.feed_ingestion_service import FeedIngestionService
from app.features.feed.data.repository.feed_repository import FeedRepository


def fetch_live_news_snippets(limit: int = 50) -> list:
    """
    Scrapes the live Google News RSS stream tracking the keyword 'layoffs',
    extracting up to the requested limit of raw text summaries.
    """
    print(f"📡 Querying live web news feed for 'layoffs' (Limit: {limit})...")
    rss_url = "https://news.google.com/rss/search?q=layoffs&hl=en-US&gl=US&ceid=US:en"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        req = urllib.request.Request(rss_url, headers=headers)

        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        articles = []

        for item in root.findall('.//item')[:limit]:
            title = item.find('title').text if item.find('title') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""

            combined_context = f"Headline: {title}. Context Snippet: {description}"
            articles.append(combined_context)

        return articles
    except Exception as e:
        print(f"⚠️ Web scraping fetch failed: {str(e)}")
        return []


def execute_live_production_seed():
    """
    Scrapes actual web news, processes the entries dynamically through Gemini Flash,
    and updates the Firestore document collection securely.
    """
    print("Initializing cloud database connectivity configurations...")
    initialize_firebase()

    ingestion_service = FeedIngestionService()
    repository = FeedRepository()

    # Fetch real live messy data straight from the web infrastructure
    live_scraped_stories = fetch_live_news_snippets(limit=50)

    if not live_scraped_stories:
        print("❌ No news snippets collected from the web. Pipeline terminating.")
        return

    print(f"\n🚀 Successfully ingested {len(live_scraped_stories)} raw web entries.")
    print("Piping live streams through the Gemini compilation sequence...")

    for idx, raw_story in enumerate(live_scraped_stories, 1):
        print(f"\n--- Processing Live Web Entry #{idx} ---")
        try:
            print("Forwarding raw text block to Gemini AI compiler layer...")
            extracted_schema = ingestion_service.process_raw_story(raw_story)

            if not extracted_schema.company_name or extracted_schema.company_name.lower() in ["unknown", "string"]:
                print("⏩ Gemini could not identify a distinct company event in this article summary. Skipping.")
                continue

            print(f"✅ Gemini Parsed Live Data! Enterprise: {extracted_schema.company_name}")
            print(
                f"   Status: {extracted_schema.status} | Extracted Context Timeline: {extracted_schema.approximate_date}")

            print("Committing to FeedRepository storage engine...")
            db_result = repository.check_and_save_layoff(extracted_schema)
            print(f"💾 Storage Operation Complete: {db_result['action']}")

            time.sleep(4) #Sleep before next execution to bypass rate limiting

        except Exception as err:
            print(f"❌ Processing aborted on Item #{idx}: {str(err)}")
            time.sleep(6)


if __name__ == "__main__":
    execute_live_production_seed()