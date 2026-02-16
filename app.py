from flask import Flask, request, jsonify
from appgallery_service import fetch_single_app

app = Flask(__name__)

@app.route("/")
def home():
    return "AppGallery Fetcher API Running"

@app.route("/fetch")
def fetch_app():
    app_id = request.args.get("appId")

    if not app_id:
        return jsonify({"error": "Missing appId"}), 400

    try:
        result = fetch_single_app(app_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
