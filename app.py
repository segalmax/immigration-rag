import os
import flask
import dotenv

dotenv.load_dotenv()
app = flask.Flask(__name__)


@app.route("/health")
def health():
    return flask.jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ["PORT"]))
