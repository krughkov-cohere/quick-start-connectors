# Compass Multilingual Connector

Connects Cohere North and the Chat API to a Cohere Compass index,
enabling cross-lingual retrieval — query in any language, retrieve
documents in any language, respond in any language.

## How It Works

1. Accepts a query (any language) and optional `response_language`
2. Retrieves top chunks from Compass via semantic search
3. Reranks with `rerank-v4.0-pro` (100+ language support)
4. Returns reranked chunks as Cohere-compatible documents

## Setup

```bash
cp .env-template .env
# fill in your values in .env
poetry install
poetry run flask --app provider --debug run --port 5000
```

## Environment Variables

| Variable | Description |
|---|---|
| COHERE_API_KEY | Your Cohere API key |
| COMPASS_INDEX_URL | Your Compass instance URL |
| COMPASS_BEARER_TOKEN | Compass bearer token (if required) |
| COMPASS_INDEX_NAME | Name of the Compass index to search |
| CONNECTOR_API_KEY | Bearer token to secure this connector |

## Request Format

```json
POST /search
{
  "query": "What is the inflation policy?",
  "response_language": "English"
}
```

## Response Format

```json
{
  "results": [
    {
      "text": "...",
      "title": "...",
      "source": "...",
      "response_language": "English"
    }
  ]
}
```
