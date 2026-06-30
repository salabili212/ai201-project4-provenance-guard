from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timezone
from signals import llm_signal, stylometric_signal

app = Flask(__name__)

audit_log = []

def combine_scores(llm_score: float, stylometric_score: float) -> float:
    """Weighted combination per planning.md: LLM 60%, stylometrics 40%."""
    return round((llm_score * 0.6) + (stylometric_score * 0.4), 2)


def get_label(confidence: float) -> tuple[str, str]:
    """Maps confidence score to (attribution, label) per planning.md thresholds."""
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
        "status": "classified"
    }
    audit_log.append(entry)

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "label": label
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit_log})


if __name__ == "__main__":
    app.run(debug=True, port=5000)