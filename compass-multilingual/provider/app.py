import os
from functools import wraps
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from .client import search

load_dotenv()

app = Flask(__name__)

CONNECTOR_API_KEY = os.environ.get("CONNECTOR_API_KEY", "")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if CONNECTOR_API_KEY:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {CONNECTOR_API_KEY}":
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/search", methods=["POST"])
@require_auth
def search_endpoint():
    body = request.get_json(force=True, silent=True) or {}
    query = body.get("query", "").strip()
    response_language = body.get("response_language", "English").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        results = search(query=query, response_language=response_language)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
