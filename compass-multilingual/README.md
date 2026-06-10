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

`setup.py` calls `refresh_index()` automatically after seeding completes.

**Step 4: Start the connector**

```bash
poetry run flask --app provider --debug run --port 5000
```

Optional verification: `poetry run python setup.py --verify` (requires Flask running: `poetry run flask --app provider --debug run --port 5000`).

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
| politique_monetaire_bce | FR | La BCE maintient sa politique monétaire restrictive face à une inflation sous-jacente persistante |
| marche_du_travail_france | FR | Le marché du travail français affiche une résilience historique malgré un ralentissement économique |
| transition_energetique | FR | La transition énergétique européenne accélère le déploiement des énergies renouvelables et la décarbonation industrielle |
| tsb_klyuchevaya_stavka | RU | Банк России сохраняет ключевую ставку на уровне 16% для сдерживания инфляционных рисков |
| inflyatsiya_potrebitelskaya | RU | Потребительская инфляция в России: динамика цен на продовольствие и непродовольственные товары |
| energeticheskiy_rynok | RU | Российский энергетический рынок: добыча нефти, экспорт газа и переориентация поставок на азиатские рынки |
| tsifrovoy_rubl | RU | Цифровой рубль: пилотный проект Банка России и перспективы внедрения новой формы национальной валюты |

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
│   ├── __init__.py         # Flask app export
│   ├── app.py              # Flask connector — /search endpoint
│   └── client.py           # Compass search + Cohere rerank logic
├── setup.py                # Index creation and document seeding
├── Dockerfile              # Container image for deployment
├── poetry.lock             # Locked dependencies
├── .gitignore              # Git ignore rules
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

The difference: running without `--clean` skips index creation if the index already exists and re-inserts all documents listed in `manifest.json` (upsert by `document_id`). Running with `--clean` deletes and recreates the index from scratch before seeding.

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| COHERE_API_KEY | Yes | Cohere API key |
| COMPASS_INDEX_URL | Yes | Base URL of your Compass instance (no trailing `/api`) |
| COMPASS_BEARER_TOKEN | Yes | Bearer token for Compass authentication |
| COMPASS_INDEX_NAME | Yes | Name of the Compass index to create and search |
| CONNECTOR_API_KEY | Yes | Secret key for authenticating requests to this connector |
| COMPASS_PARSER_URL | No | Parser endpoint — required only for PDF/DOCX/PPTX ingestion |

## 10. Using with the Cohere Platform

Once the connector is seeded and running locally, you can register it with the Cohere Platform and use it in Chat or North for grounded, cross-lingual responses.

### Deploy the Connector

The Flask server must be publicly reachable so the Cohere Platform can call your `/search` endpoint. For demos, [ngrok](https://ngrok.com/) is the quickest option:

```bash
poetry run flask --app provider --debug run --port 5000
# in a separate terminal:
ngrok http 5000
# → https://abc123.ngrok.io
```

Register the connector using the ngrok URL with the `/search` path appended (for example, `https://abc123.ngrok.io/search`).

For production, deploy the connector to a cloud VM, container service, or internal server with a stable HTTPS URL.

### Register the Connector via Cohere API

Use the Cohere Python SDK to register the connector. The `service_auth` token must match the `CONNECTOR_API_KEY` value in your `.env`:

```python
import cohere

co = cohere.Client("YOUR_COHERE_API_KEY")
connector = co.connectors.create(
    name="compass-multilingual",
    url="https://your-server-url/search",
    service_auth={
        "type": "bearer",
        "token": "your_CONNECTOR_API_KEY_value",
    },
)
print(connector.connector.id)  # save this ID
```

### Query with the Connector

Pass the connector ID in a Chat API call. Cohere queries your `/search` endpoint and uses the returned documents to generate a grounded response:

```python
response = co.chat(
    message="What is the central bank policy on interest rates?",
    connectors=[{"id": "connector-id-from-above"}],
    model="command-r-plus",
)
print(response.text)
print(response.citations)
```

### Multilingual Responses

This connector accepts a `response_language` field on the `/search` request body. Pass it via connector `options` in Chat — the platform forwards options to your connector, and each result includes `response_language` as metadata for Command:

```python
response = co.chat(
    message="Quelle est la politique de la BCE?",
    connectors=[{
        "id": "connector-id-from-above",
        "options": {"response_language": "French"},
    }],
    model="command-r-plus",
)
```

### Using in North (UI)

If North is deployed in your organization, add the connector under **Settings → Connectors → Add Connector** using the same URL and bearer token. Users can then enable it per conversation as a data source toggle for grounded, cross-lingual chat.
