from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timezone
from signals import llm_signal, stylometric_signal
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

audit_log = []
# Tracks current status of each content_id so /appeal can update it
content_store = {}


def combine_scores(llm_score: float, stylometric_score: float) -> float:
    return round((llm_score * 0.6) + (stylometric_score * 0.4), 2)


def get_label(confidence: float) -> tuple[str, str]:
    if confidence >= 0.75:
        attribution = "likely_ai"
        label = "This content shows strong indicators of AI generation. Multiple signals suggest it was likely written by an AI tool rather than a human."
    elif confidence >= 0.40:
        attribution = "uncertain"
        label = "We're not confident enough to make a determination. This content shows mixed signals and could be either AI-generated or human-written."
    else:
        attribution = "likely_human"
        label = "This content shows strong indicators of human authorship. Our analysis did not detect significant signs of AI generation."
    return attribution, label


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    llm_score = llm_signal(text)
    stylometric_score = stylometric_signal(text)
    confidence = combine_scores(llm_score, stylometric_score)
    attribution, label = get_label(confidence)

    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "status": "classified",
        "appeal_reasoning": None
    }
    audit_log.append(entry)
    content_store[content_id] = entry

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "label": label
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if content_id not in content_store:
        return jsonify({"error": "content_id not found"}), 404

    # Update the original entry's status
    content_store[content_id]["status"] = "under_review"
    content_store[content_id]["appeal_reasoning"] = creator_reasoning

    # Log the appeal as a new entry too, linked to the original
    appeal_entry = {
        "content_id": content_id,
        "type": "appeal",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_attribution": content_store[content_id]["attribution"],
        "original_confidence": content_store[content_id]["confidence"]
    }
    audit_log.append(appeal_entry)

    return jsonify({
        "message": "Appeal received and content status updated to under_review.",
        "content_id": content_id,
        "status": "under_review"
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit_log})


if __name__ == "__main__":
    app.run(debug=True, port=5000)