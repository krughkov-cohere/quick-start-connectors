#!/usr/bin/env python3
"""Seed the Compass index with multilingual sample data."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from cohere_compass.clients import CompassClient
from cohere_compass.clients.parser import CompassParserClient
from cohere_compass.exceptions import CompassError
from cohere_compass.models import (
    CompassDocument,
    CompassDocumentChunk,
    CompassDocumentMetadata,
)
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
INGEST_STRUCTURED_JSON = "structured_json"
INGEST_PARSER = "parser"
ENV_PREFIX = "COMPASS_MULTILINGUAL"


def env_var(name: str, default: str = "") -> str:
    prefixed = f"{ENV_PREFIX}_{name}"
    if prefixed in os.environ:
        return os.environ[prefixed]
    if name in os.environ:
        return os.environ[name]
    return default


def env_var_set(name: str) -> bool:
    prefixed = f"{ENV_PREFIX}_{name}"
    return prefixed in os.environ or name in os.environ


def load_environment() -> tuple[str, str, str]:
    load_dotenv(PROJECT_ROOT / ".env")

    missing = []
    for var in ("COMPASS_INDEX_URL", "COMPASS_INDEX_NAME"):
        if not env_var(var, "").strip():
            missing.append(f"{ENV_PREFIX}_{var}")
    if not env_var_set("COMPASS_BEARER_TOKEN"):
        missing.append(f"{ENV_PREFIX}_COMPASS_BEARER_TOKEN")
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print(
            f"\nCopy {PROJECT_ROOT / '.env-template'} to .env and fill in the values."
        )
        sys.exit(1)

    return (
        env_var("COMPASS_INDEX_URL"),
        env_var("COMPASS_BEARER_TOKEN"),
        env_var("COMPASS_INDEX_NAME"),
    )


def create_compass_client(index_url: str, bearer_token: str) -> CompassClient:
    return CompassClient(index_url=index_url, bearer_token=bearer_token)


def create_parser_client(parser_url: str, bearer_token: str) -> CompassParserClient:
    return CompassParserClient(
        parser_url=parser_url,
        bearer_token=bearer_token or None,
    )


def _is_index_exists_error(error: Exception) -> bool:
    message = str(error).lower()
    if "already exists" in message or "index exists" in message:
        return True
    from cohere_compass.exceptions import CompassClientError

    return isinstance(error, CompassClientError) and error.code == 409


def _is_index_not_found_error(error: Exception) -> bool:
    message = str(error).lower()
    if "not found" in message or "does not exist" in message:
        return True
    from cohere_compass.exceptions import CompassClientError

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


def resolve_ingest_method(entry: dict, source_path: Path) -> str:
    ingest = entry.get("ingest")
    if ingest:
        return ingest
    if source_path.suffix.lower() == ".json":
        return INGEST_STRUCTURED_JSON
    return INGEST_PARSER


def truncate_title(title: str, max_length: int = 40) -> str:
    if len(title) <= max_length:
        return title
    return title[: max_length - 3].rstrip() + "..."


def truncate_query(query: str, max_words: int = 4) -> str:
    words = query.split()
    if len(words) <= max_words:
        return query
    return " ".join(words[:max_words]) + "..."


def _format_insert_errors(errors: list[dict[str, str]] | None) -> str | None:
    if not errors:
        return None
    messages = []
    for error in errors:
        if isinstance(error, dict):
            messages.extend(str(value) for value in error.values() if value)
        else:
            messages.append(str(error))
    return "; ".join(messages) if messages else "Unknown insert error"


def _insert_json_doc(
    compass_client: CompassClient,
    index_name: str,
    entry: dict,
    source_path: Path,
) -> str | None:
    with source_path.open(encoding="utf-8") as doc_file:
        doc_data = json.load(doc_file)

    document_id = doc_data["id"]
    content = {
        "text": doc_data["text"],
        "title": doc_data["title"],
        "source": doc_data["source"],
    }
    relative_path = str(source_path.relative_to(PROJECT_ROOT))
    chunk = CompassDocumentChunk(
        chunk_id=f"{document_id}_0",
        sort_id="0",
        document_id=document_id,
        parent_document_id=document_id,
        content=content,
        path=relative_path,
    )
    doc = CompassDocument(
        metadata=CompassDocumentMetadata(
            document_id=document_id,
            filename=relative_path,
        ),
        content=content,
        chunks=[chunk],
        index_fields=["text", "title", "source"],
    )

    try:
        errors = compass_client.insert_doc(index_name=index_name, doc=doc)
    except CompassError as error:
        return str(error)

    return _format_insert_errors(errors)


def _insert_binary_doc(
    compass_client: CompassClient,
    parser_client: CompassParserClient,
    index_name: str,
    entry: dict,
    source_path: Path,
) -> str | None:
    try:
        parsed_docs = parser_client.process_file(
            filename=str(source_path),
            file_id=entry["id"],
        )
    except CompassError as error:
        return str(error)

    if not parsed_docs:
        return "Parser returned no documents"

    for doc in parsed_docs:
        if doc.metadata.document_id in ("", entry["id"]):
            doc.metadata.document_id = entry["id"]

        try:
            errors = compass_client.insert_doc(index_name=index_name, doc=doc)
        except CompassError as error:
            return str(error)

        insert_error = _format_insert_errors(errors)
        if insert_error:
            return insert_error

    return None


def seed_documents(
    compass_client: CompassClient,
    index_name: str,
    parser_client: CompassParserClient | None = None,
) -> tuple[dict[str, int], list[str]]:
    documents = load_manifest()
    counts: dict[str, int] = {}
    failures: list[str] = []
    parser_url = env_var("COMPASS_PARSER_URL", "").strip()

    for entry in documents:
        source_path = PROJECT_ROOT / entry["source_file"]
        language = entry["language"]
        language_label = LANGUAGE_LABELS.get(language, language.upper())
        title = truncate_title(entry["title"])
        ingest_method = resolve_ingest_method(entry, source_path)

        if not source_path.exists():
            error_message = f"source file not found: {entry['source_file']}"
            failures.append(f"{entry['id']}: {error_message}")
            print(f"  ❌ [{language_label}] {title} — {error_message}")
            continue

        if ingest_method == INGEST_STRUCTURED_JSON:
            error_message = _insert_json_doc(
                compass_client, index_name, entry, source_path
            )
        elif ingest_method == INGEST_PARSER:
            if not parser_url:
                error_message = (
                    f"{ENV_PREFIX}_COMPASS_PARSER_URL is required for parser ingest "
                    f"({source_path.name})"
                )
            elif parser_client is None:
                error_message = "Parser client is not initialized"
            else:
                error_message = _insert_binary_doc(
                    compass_client,
                    parser_client,
                    index_name,
                    entry,
                    source_path,
                )
        else:
            error_message = f"Unknown ingest method '{ingest_method}'"

        if error_message:
            failures.append(f"{entry['id']}: {error_message}")
            print(f"  ❌ [{language_label}] {title} — {error_message}")
            continue

        counts[language] = counts.get(language, 0) + 1
        print(f"  ✅ [{language_label}] {title}")

    if failures:
        print(f"\n❌ {len(failures)} document(s) failed to insert:")
        for failure in failures:
            print(f"   - {failure}")

    if counts:
        try:
            compass_client.refresh_index(index_name=index_name)
            print(f"Refreshed index '{index_name}'.")
        except CompassError as error:
            print(f"⚠️  Failed to refresh index '{index_name}': {error}")

    return counts, failures


def verify_search_endpoint() -> None:
    api_key = env_var("CONNECTOR_API_KEY", "")
    if not api_key:
        print(f"⚠️  Skipping verify: {ENV_PREFIX}_CONNECTOR_API_KEY is not set in .env")
        return

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
        except urllib.error.HTTPError as error:
            print(
                f"[{label}] '{truncate_query(query)}' → HTTP {error.code}: {error.reason}"
            )
            continue
        except urllib.error.URLError as error:
            print(f"[{label}] '{truncate_query(query)}' → error: {error}")
            continue

        result_count = len(body.get("results", []))
        print(f"[{label}] '{truncate_query(query)}' → {result_count} result(s)")


def print_success(index_name: str, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    counts_str = ", ".join(
        f"{count} {language.upper()}" for language, count in counts.items() if count > 0
    )
    if counts_str:
        print(
            f"✅ Done. Seeded {total} documents ({counts_str}) into index '{index_name}'"
        )
    else:
        print(f"⚠️  Done with no documents seeded into index '{index_name}'")
    print("   Run: poetry run flask --app provider --debug run --port 5000")
    print(
        "   Then: curl -X POST http://localhost:5000/search "
        f"-H 'Authorization: Bearer ${ENV_PREFIX}_CONNECTOR_API_KEY' "
        "-H 'Content-Type: application/json' "
        '-d \'{"query": "What is the central bank policy on interest rates?", '
        '"response_language": "English"}\''
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

    parser_url = env_var("COMPASS_PARSER_URL", "").strip()
    parser_client = (
        create_parser_client(parser_url, bearer_token) if parser_url else None
    )

    if args.clean:
        delete_index_if_exists(compass_client, index_name)
        time.sleep(3)  # allow Compass to finish deleting before recreate

    ensure_index(compass_client, index_name)
    counts, failures = seed_documents(compass_client, index_name, parser_client)

    if args.verify:
        verify_search_endpoint()

    print_success(index_name, counts)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

# USAGE:
# poetry run python setup.py              # seed (skip create if index exists)
# poetry run python setup.py --clean      # delete + recreate + seed
# poetry run python setup.py --verify     # seed + hit localhost:5000/search
# poetry run python setup.py --clean --verify
#
# Supported file types (via sample_data/manifest.json):
#   structured_json  — .json sample docs with text/title/source fields (manual chunks)
#   parser           — PDF, DOCX, PPT/PPTX, HTML, CSV, TXT, and other parser-supported files
#
# Routing priority:
#   1. manifest "ingest" field ("structured_json" or "parser")
#   2. file extension fallback (.json → structured_json, all others → parser)
#
# Adding a new document:
#   1. Place the file under sample_data/<lang>/ (e.g. sample_data/en/report.pdf)
#   2. Add an entry to sample_data/manifest.json with id, language, title, source_file,
#      and ingest ("structured_json" for JSON, "parser" for binary/text office files)
#   3. For parser ingest, set COMPASS_MULTILINGUAL_COMPASS_PARSER_URL in .env
#   4. Run: poetry run python setup.py --clean
#
# TODO: --dry-run  validate manifest and document files without connecting to Compass
#                  useful for CI checks and contributors adding new sample documents
