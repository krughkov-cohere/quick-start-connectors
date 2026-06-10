import cohere
from cohere_compass.clients import CompassClient
from flask import current_app as app

cohere_client = None
compass_client = None


def get_cohere_client() -> cohere.ClientV2:
    global cohere_client
    if cohere_client is None:
        cohere_client = cohere.ClientV2(api_key=app.config.get("COHERE_API_KEY"))
    return cohere_client


def get_compass_client() -> CompassClient:
    global compass_client
    if compass_client is None:
        compass_client = CompassClient(
            index_url=app.config["COMPASS_INDEX_URL"],
            bearer_token=app.config.get("COMPASS_BEARER_TOKEN"),
        )
    return compass_client
