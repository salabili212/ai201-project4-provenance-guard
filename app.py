from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timezone
from signals import llm_signal

app = Flask(__name__)

# Simple in-memory audit log for now (we'll make this more structured in Milestone 4/5)
audit_log = []

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    # Run Signal 1 (Groq LLM)
    llm_score = llm_signal(text)

    # Placeholder confidence + label until Milestone 4 adds Signal 2 + real scoring
    confidence = llm_score
    attribution = "likely_ai" if confidence >= 0.5 else "likely_human"
    label = "placeholder label — real label logic comes in Milestone 5"

    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "status": "classified"
    }
    audit_log.append(entry)

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "label": label
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit_log})


if __name__ == "__main__":
    app.run(debug=True, port=5000)