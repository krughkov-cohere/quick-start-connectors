import os
import cohere
from cohere_compass.clients import CompassClient
from dotenv import load_dotenv

load_dotenv()

co = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
compass_client = CompassClient(
    index_url=os.environ["COMPASS_INDEX_URL"],
    bearer_token=os.environ.get("COMPASS_BEARER_TOKEN"),
)
INDEX_NAME = os.environ["COMPASS_INDEX_NAME"]


def search(query: str, response_language: str = "English") -> list[dict]:
    """
    Run a query in any language against the Compass index.
    Returns a Cohere-connector-compatible documents array.
    response_language is passed through as metadata on each result
    so the caller (North or Chat API) can instruct Command to respond
    in the correct language.
    """
    hits = compass_client.search_chunks(
        index_name=INDEX_NAME,
        query=query,
        top_k=10,
    ).hits

    if not hits:
        return []

    reranked = co.rerank(
        model="rerank-v4.0-pro",
        query=query,
        documents=[r.content.get("text", "") for r in hits],
        top_n=3,
    )

    return [
        {
            "id": f"doc:{i}",
            "text": hits[r.index].content.get("text", ""),
            "title": hits[r.index].content.get("title", ""),
            "source": hits[r.index].content.get("source", ""),
            "response_language": response_language,
        }
        for i, r in enumerate(reranked.results)
    ]
