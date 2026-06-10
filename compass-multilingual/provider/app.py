import logging

from connexion.exceptions import Unauthorized
from flask import abort, current_app as app

from . import UpstreamProviderError, provider

logger = logging.getLogger(__name__)


def search(body):
    logger.debug(f'Search request: {body["query"]}')
    response_language = body.get("response_language", "English")
    if isinstance(response_language, str):
        response_language = response_language.strip() or "English"
    else:
        response_language = "English"

    try:
        data = provider.search(body["query"], response_language=response_language)
        logger.info(f"Found {len(data)} results")
    except UpstreamProviderError as error:
        logger.error(f"Upstream search error: {error.message}")
        abort(502, error.message)

    return {"results": data}, 200, {"X-Connector-Id": app.config.get("APP_ID")}


def apikey_auth(token):
    if token != str(app.config.get("CONNECTOR_API_KEY")):
        raise Unauthorized()
    return {}
