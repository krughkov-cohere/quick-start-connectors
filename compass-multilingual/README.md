# Compass Multilingual Connector

A Cohere Compass connector that indexes and retrieves documents in English, French, and Russian using cross-lingual semantic search.

## What This Connector Demonstrates

- Cross-lingual semantic search: query in any supported language, retrieve relevant documents regardless of the language they were written in
- Multilingual embeddings using Cohere embed-multilingual-v3.0
- Response language control: the caller specifies the desired response language via the `response_language` field in the request body
- Support for 10 sample documents across 3 languages on the theme of global economics and monetary policy

## Prerequisites

- Python 3.11+
- Poetry
- A running Cohere Compass instance
- A Cohere API key with access to embed-multilingual-v3.0 and Command

## Quick Start

**Step 1: Clone and install**

```bash
git clone https://github.com/cohere-ai/quick-start-connectors.git
cd quick-start-connectors/compass-multilingual
poetry install
```

**Step 2: Configure environment**

```bash
cp .env-template .env
# Edit .env and fill in:
# COHERE_API_KEY, COMPASS_INDEX_URL, COMPASS_BEARER_TOKEN,
# COMPASS_INDEX_NAME, CONNECTOR_API_KEY
```

**Step 3: Seed the index**

```bash
poetry run python setup.py
```

**Step 4: Start the connector**

```bash
poetry run flask --app provider --debug run --port 5000
```

**Step 5: Test a search**

```bash
curl -X POST http://localhost:5000/search \
  -H "Authorization: Bearer $CONNECTOR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the central bank policy on interest rates?", "response_language": "English"}'
```

Expected response shape:

```json
{
  "results": [
    {
      "id": "doc:0",
      "title": "...",
      "text": "...",
      "source": "...",
      "response_language": "English"
    }
  ]
}
```

## Sample Data

| ID | Language | Title |
|----|----------|-------|
| ecb_rate_decision | EN | ECB Governing Council Holds Key Interest Rates Steady Amid Disinflation Progress |
| us_inflation_outlook | EN | Federal Reserve Signals Cautious Approach to Rate Cuts as US Inflation Remains Above Target |
| global_supply_chain | EN | Global Supply Chain Disruptions Persist as Red Sea Shipping Routes Face Extended Dislocation |
| politique_monetaire_bce | FR | La BCE maintient sa politique monétaire restrictive face aux pressions inflationnistes persistantes |
| marche_du_travail_france | FR | Le marché du travail français affiche une résilience surprenante malgré le ralentissement économique |
| transition_energetique | FR | La transition énergétique européenne s'accélère malgré les tensions sur les prix de l'énergie |
| tsb_klyuchevaya_stavka | RU | Банк России сохраняет ключевую ставку на уровне 16% для сдерживания инфляционных рисков |
| inflyatsiya_potrebitelskaya | RU | Потребительская инфляция в России: динамика, структура и прогноз Банка России |
| energeticheskiy_rynok | RU | Российский энергетический рынок: добыча, экспорт и влияние санкций |
| tsifrovoy_rubl | RU | Цифровой рубль: пилотный проект Банка России и перспективы внедрения |

All documents are stored as JSON in `sample_data/<lang>/` and follow this schema:

```json
{
  "id": "string",
  "title": "string",
  "source": "string",
  "language": "string (en | fr | ru)",
  "text": "string"
}
```

## Project Structure

```
compass-multilingual/
├── provider/
│   ├── app.py              # Flask connector — /search endpoint
│   └── client.py           # Compass search + Cohere rerank logic
├── setup.py                # Index creation and document seeding
├── .env-template           # Environment variable template
├── pyproject.toml          # Dependencies
├── sample_data/
│   ├── manifest.json       # Document registry with ingest routing
│   ├── en/                 # English documents (3)
│   ├── fr/                 # French documents (3)
│   └── ru/                 # Russian documents (4)
```

## How It Works

1. `setup.py` reads `manifest.json` and inserts each document into a Compass index as a single `CompassDocumentChunk` with `title`, `text`, and `source` fields
2. The `provider` package exposes a `/search` endpoint that accepts a query and `response_language`, calls Compass search, reranks with `rerank-v4.0-pro`, and returns ranked results
3. Compass uses embed-multilingual-v3.0 to embed both documents and queries, enabling semantic matching across languages without translation
4. The `response_language` field is passed through to each result so the Cohere platform can instruct Command to respond in the requested language

## Adding New Documents

1. Create a JSON file in `sample_data/<lang>/` following the schema above
2. Add an entry to `sample_data/manifest.json` with:
   - `id`, `language`, `title`, `source_file`
   - `"ingest": "structured_json"` for JSON files
   - `"ingest": "parser"` for PDF, DOCX, PPTX, HTML (requires `COMPASS_PARSER_URL` in `.env`)
3. Re-seed the index:

```bash
poetry run python setup.py
```

To wipe the index and start fresh (removes all documents):

```bash
poetry run python setup.py --clean
```

The difference: running without `--clean` skips creation if the index exists and only seeds missing documents. Running with `--clean` deletes and recreates the index from scratch.

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| COHERE_API_KEY | Yes | Cohere API key |
| COMPASS_INDEX_URL | Yes | Base URL of your Compass instance (no trailing `/api`) |
| COMPASS_BEARER_TOKEN | Yes | Bearer token for Compass authentication |
| COMPASS_INDEX_NAME | Yes | Name of the Compass index to create and search |
| CONNECTOR_API_KEY | Yes | Secret key for authenticating requests to this connector |
| COMPASS_PARSER_URL | No | Parser endpoint — required only for PDF/DOCX/PPTX ingestion |
