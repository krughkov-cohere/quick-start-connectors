import logging

from flask import current_app as app

from . import UpstreamProviderError
from .client import get_cohere_client, get_compass_client

logger = logging.getLogger(__name__)


def search(query: str, response_language: str = "English") -> list[dict[str, str]]:
    try:
        hits = (
            get_compass_client()
            .search_chunks(
                index_name=app.config["COMPASS_INDEX_NAME"],
                query=query,
                top_k=10,
            )
            .hits
        )
    except Exception as error:
        logger.error(f"Compass search error: {error}")
        raise UpstreamProviderError(str(error)) from error

    if not hits:
        return []

    try:
        reranked = get_cohere_client().rerank(
            model="rerank-v4.0-pro",
            query=query,
            documents=[r.content.get("text", "") for r in hits],
            top_n=3,
        )
    except Exception as error:
        logger.error(f"Cohere rerank error: {error}")
        raise UpstreamProviderError(str(error)) from error

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
