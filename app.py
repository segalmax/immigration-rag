"""
app.py — Flask RAG API
Exposes /health and /ask endpoints.
Retrieves relevant chunks from OpenSearch, builds a prompt, and calls Claude via Bedrock.

TODO: implement actual route logic once AWS infra is provisioned.
"""
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/health")
def health():
    """Liveness probe — returns 200 when the app is running."""
    return jsonify({"status": "ok"})


@app.route("/ask", methods=["POST"])
def ask():
    """
    POST /ask  {"question": "..."}
    1. Embed the question with Titan (bedrock_utils.embed)
    2. Retrieve top-k chunks from OpenSearch (opensearch_utils.search)
    3. Build a grounded prompt
    4. Call Claude via Bedrock (bedrock_utils.chat)
    5. Return {"answer": "...", "sources": [...]}
    """
    # TODO: implement
    body = request.get_json(force=True)
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    # placeholder
    return jsonify({"answer": "Not implemented yet.", "sources": []}), 501


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
