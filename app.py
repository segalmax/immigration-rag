import os
import flask
from dotenv import load_dotenv

load_dotenv()
app = flask.Flask(__name__)


@app.route("/health")
def health():
    return flask.jsonify({"status": "ok"})


@app.route("/ask", methods=["POST"])
def ask():
    raise NotImplementedError


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("PORT", 5001)))
