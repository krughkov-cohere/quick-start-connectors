#!/usr/bin/env python3
"""Seed the Compass index with multilingual sample data."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from cohere_compass.clients import CompassClient
from cohere_compass.exceptions import CompassClientError, CompassError
from cohere_compass.models import CompassDocument, CompassDocumentMetadata
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
MANIFEST_PATH = PROJECT_ROOT / "sample_data" / "manifest.json"

VERIFY_QUERIES = [
    (
        "English",
        "What is the central bank policy on interest rates?",
        "English",
    ),
    (
        "French",
        "Quels sont les effets de l'inflation sur le marché du travail?",
        "French",
    ),
    (
        "Russian",
        "Какова ситуация на энергетическом рынке?",
        "Russian",
    ),
]

LANGUAGE_LABELS = {"en": "EN", "fr": "FR", "ru": "RU"}


def load_environment() -> tuple[str, str, str]:
    load_dotenv(PROJECT_ROOT / ".env")

    missing = []
    for var in ("COMPASS_INDEX_URL", "COMPASS_INDEX_NAME"):
        if not os.environ.get(var, "").strip():
            missing.append(var)
    if "COMPASS_BEARER_TOKEN" not in os.environ:
        missing.append("COMPASS_BEARER_TOKEN")
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print(f"\nCopy {PROJECT_ROOT / '.env-template'} to .env and fill in the values.")
        sys.exit(1)

    return (
        os.environ["COMPASS_INDEX_URL"],
        os.environ["COMPASS_BEARER_TOKEN"],
        os.environ["COMPASS_INDEX_NAME"],
    )


def create_compass_client(index_url: str, bearer_token: str) -> CompassClient:
    return CompassClient(index_url=index_url, bearer_token=bearer_token)


def _is_index_exists_error(error: Exception) -> bool:
    message = str(error).lower()
    if "already exists" in message or "index exists" in message:
        return True
    return isinstance(error, CompassClientError) and error.code == 409


def _is_index_not_found_error(error: Exception) -> bool:
    message = str(error).lower()
    if "not found" in message or "does not exist" in message:
        return True
    return isinstance(error, CompassClientError) and error.code == 404


def ensure_index(compass_client: CompassClient, index_name: str) -> None:
    try:
        compass_client.create_index(index_name=index_name)
        print(f"Created index '{index_name}'.")
    except (CompassError, Exception) as error:
        if _is_index_exists_error(error):
            print(f"Index '{index_name}' already exists, skipping creation.")
        else:
            raise


def delete_index_if_exists(compass_client: CompassClient, index_name: str) -> None:
    try:
        compass_client.delete_index(index_name=index_name)
        print(f"Deleted index '{index_name}'.")
    except (CompassError, Exception) as error:
        if _is_index_not_found_error(error):
            print(f"Index '{index_name}' does not exist, skipping deletion.")
        else:
            raise


def load_manifest() -> list[dict]:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)["documents"]


def truncate_title(title: str, max_length: int = 40) -> str:
    if len(title) <= max_length:
        return title
    return title[: max_length - 3].rstrip() + "..."


def truncate_query(query: str, max_words: int = 4) -> str:
    words = query.split()
    if len(words) <= max_words:
        return query
    return " ".join(words[:max_words]) + "..."


def seed_documents(compass_client: CompassClient, index_name: str) -> dict[str, int]:
    documents = load_manifest()
    counts = {"en": 0, "fr": 0, "ru": 0}

    for entry in documents:
        source_path = PROJECT_ROOT / entry["source_file"]
        with source_path.open(encoding="utf-8") as doc_file:
            doc_data = json.load(doc_file)

        doc = CompassDocument(
            metadata=CompassDocumentMetadata(document_id=doc_data["id"]),
            content={
                "text": doc_data["text"],
                "title": doc_data["title"],
                "source": doc_data["source"],
            },
        )
        compass_client.insert_doc(index_name=index_name, doc=doc)

        language = entry["language"]
        counts[language] = counts.get(language, 0) + 1
        language_label = LANGUAGE_LABELS.get(language, language.upper())
        print(f"  ✅ [{language_label}] {truncate_title(entry['title'])}")

    return counts


def verify_search_endpoint() -> None:
    api_key = os.environ.get("CONNECTOR_API_KEY", "")

    for label, query, response_language in VERIFY_QUERIES:
        payload = json.dumps(
            {"query": query, "response_language": response_language}
        ).encode("utf-8")
        request = urllib.request.Request(
            "http://localhost:5000/search",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as error:
            print(f"[{label}] '{truncate_query(query)}' → error: {error}")
            continue

        result_count = len(body.get("results", []))
        print(f"[{label}] '{truncate_query(query)}' → {result_count} result(s)")


def print_success(index_name: str, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    counts_str = ", ".join(
        f"{v} {k.upper()}" for k, v in counts.items() if v > 0
    )
    print(f"✅ Done. Seeded {total} documents ({counts_str}) into index '{index_name}'")
    print("   Run: poetry run flask --app provider --debug run --port 5000")
    print(
        "   Then: curl -X POST http://localhost:5000/search "
        "-H 'Authorization: Bearer $CONNECTOR_API_KEY' "
        "-H 'Content-Type: application/json' "
        "-d '{\"query\": \"What is the central bank policy on interest rates?\", "
        "\"response_language\": \"English\"}'"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Compass multilingual connector index with sample data."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the index and recreate it before seeding.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After seeding, POST test queries to the local /search endpoint.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index_url, bearer_token, index_name = load_environment()
    compass_client = create_compass_client(index_url, bearer_token)

    if args.clean:
        delete_index_if_exists(compass_client, index_name)

    ensure_index(compass_client, index_name)
    counts = seed_documents(compass_client, index_name)

    if args.verify:
        verify_search_endpoint()

    print_success(index_name, counts)


if __name__ == "__main__":
    main()

# USAGE:
# poetry run python setup.py              # seed (skip create if index exists)
# poetry run python setup.py --clean      # delete + recreate + seed
# poetry run python setup.py --verify     # seed + hit localhost:5000/search
# poetry run python setup.py --clean --verify
#
# TODO: --dry-run  validate manifest and document files without connecting to Compass
#                  useful for CI checks and contributors adding new sample documents
