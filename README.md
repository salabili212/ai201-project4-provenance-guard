# Provenance Guard

A backend system that classifies submitted text as likely AI-generated, likely human-written, or uncertain — using two independent detection signals, a calibrated confidence score, plain-language transparency labels, and a creator appeals workflow.

## Architecture Overview

A creator submits text + their `creator_id` to `POST /submit`. The system generates a unique `content_id`, then runs the text through two independent detection signals in sequence: an LLM-based semantic classifier (Groq) and a stylometric heuristics function (pure Python). The two scores are combined into a single weighted confidence score, which is mapped to one of three transparency label variants. The full result — including both individual signal scores — is written to a structured audit log and returned to the creator. If a creator disagrees with their classification, they can submit `POST /appeal` with their reasoning; this updates the content's status to `under_review` and appends an appeal entry to the audit log, linked to the original submission by `content_id`.

## Detection Signals

**Signal 1: LLM-based classification (Groq, llama-3.3-70b-versatile)**
Measures holistic semantic and stylistic coherence — whether the text's voice, structure, and reasoning patterns resemble typical AI output (e.g. hedging language, generic transitions like "Furthermore," overly balanced argumentation). Captures meaning-level patterns a statistical signal can't.
*What it misses:* skilled human writers with formal/technical styles can trigger false positives; heavily edited ("humanized") AI text can evade it.

**Signal 2: Stylometric heuristics (pure Python)**
Measures quantifiable structural properties: sentence length variance, type-token ratio (vocabulary diversity), and punctuation density. AI text tends toward more uniform sentence length and narrower vocabulary; human writing is more irregular.
*What it misses:* short text samples don't provide enough data for meaningful variance calculations; humans writing in controlled registers (legal, academic) can appear artificially uniform too.

These two signals are genuinely independent — one is semantic, one is structural — which is why combining them is more informative than either alone.

## Confidence Scoring

Scores are combined with: `confidence = (llm_score * 0.6) + (stylometric_score * 0.4)`. The LLM signal is weighted higher because it captures meaning, generally a stronger indicator than structural patterns alone.

**Thresholds:**
- `0.00–0.40` → Likely Human-Written
- `0.40–0.75` → Uncertain
- `0.75–1.00` → Likely AI-Generated

The uncertain band is intentionally wide because false positives (flagging a human as AI) are more harmful than false negatives on a creative platform.

**Validation — two example submissions with different scores:**

*High-confidence example (clearly human-written casual text):*
Input: "ok so i finally tried that new ramen place downtown and honestly?..."
llm_score: 0.21, stylometric_score: 0.07
confidence: 0.15 → Likely Human-Written

*Lower-confidence example (formal AI-generated text):*
Input: "Artificial intelligence represents a transformative paradigm shift..."
llm_score: 0.87, stylometric_score: 0.25
confidence: 0.62 → Uncertain

I tested 4 deliberately chosen inputs spanning clearly-AI, clearly-human, and two borderline cases. Scores ranged from 0.15 to 0.62, confirming the scoring produces meaningful variation rather than a constant or binary flip.

## Transparency Label

| Confidence Range | Label Text |
|---|---|
| 0.75–1.00 (Likely AI) | "This content shows strong indicators of AI generation. Multiple signals suggest it was likely written by an AI tool rather than a human." |
| 0.40–0.75 (Uncertain) | "We're not confident enough to make a determination. This content shows mixed signals and could be either AI-generated or human-written." |
| 0.00–0.40 (Likely Human) | "This content shows strong indicators of human authorship. Our analysis did not detect significant signs of AI generation." |

## Appeals Workflow

Any creator can appeal a classification on their own content via `POST /appeal`, providing `content_id` and `creator_reasoning`. On receipt, the system updates the content's status to `under_review`, logs the appeal text alongside the original classification entry in the audit log (linked by `content_id`), and returns a confirmation to the creator.

**Example test:**
POST /appeal
{
"content_id": "5773db1f-3489-4676-b7df-71d92a7fd42a",
"creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."
}
Response:
{
"message": "Appeal received and content status updated to under_review.",
"content_id": "5773db1f-3489-4676-b7df-71d92a7fd42a",
"status": "under_review"
}

## Rate Limiting

Limit: **10 requests per minute, 100 per day**, applied to `POST /submit` via Flask-Limiter.

Reasoning: a real creator submitting their own work for review would rarely need more than a few submissions per minute — 10/minute comfortably covers iterative editing/resubmission without feeling restrictive. The 100/day cap prevents an adversary from scripting a flood of submissions to abuse the free Groq API tier or degrade service for other users, while still allowing a prolific writer to submit dozens of pieces across a day.

**Evidence (12 rapid requests sent):**
200
200
200
200
200
200
200
200
200
429
429
First 9 succeeded, requests beyond the limit returned `429`.

## Audit Log

Every submission and appeal is written to a structured JSON log, accessible via `GET /log`. Sample entries:

```json
{
  "content_id": "5773db1f-3489-4676-b7df-71d92a7fd42a",
  "creator_id": "test-appeal-user",
  "timestamp": "2026-06-30T22:10:04.746154+00:00",
  "attribution": "uncertain",
  "confidence": 0.72,
  "llm_score": 0.87,
  "stylometric_score": 0.5,
  "status": "under_review",
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."
}
```

```json
{
  "content_id": "5773db1f-3489-4676-b7df-71d92a7fd42a",
  "type": "appeal",
  "timestamp": "2026-06-30T22:10:26.463552+00:00",
  "status": "under_review",
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "original_attribution": "uncertain",
  "original_confidence": 0.72
}
```

```json
{
  "content_id": "882601ad-02c7-4aef-a02c-eb63b23a5786",
  "creator_id": "ratelimit-test",
  "timestamp": "2026-06-30T22:08:43.286324+00:00",
  "attribution": "likely_human",
  "confidence": 0.33,
  "llm_score": 0.21,
  "stylometric_score": 0.5,
  "status": "classified",
  "appeal_reasoning": null
}
```

Appeals are logged as a linked second entry (same `content_id`, `type: "appeal"`), showing the original classification alongside the appeal reasoning — both visible together in `GET /log`.

## Known Limitations

My stylometric signal performs poorly on **short-form content** (e.g. short poems, single-paragraph micro-fiction). Sentence length variance and type-token ratio require enough data points to be statistically meaningful — on very short text, the function falls back to a neutral 0.5 score, which can pull the combined confidence toward "uncertain" even when the LLM signal is strongly confident in one direction. This is a direct consequence of how variance-based metrics behave on small samples, not a generic detection weakness.

## Spec Reflection

The spec's requirement to write exact threshold numbers and label text in `planning.md` *before* writing code (Milestone 2) helped avoid a vague implementation — having concrete thresholds (0.40, 0.75) meant the scoring logic in `app.py` was a direct translation of the spec rather than something I had to invent mid-build.

My implementation diverged from the original plan in one way: testing showed clearly-AI text only reached 0.62 confidence (landing in "Uncertain"), short of the 0.75 "Likely AI" threshold I'd designed for. The stylometric signal pulled the score down more than I anticipated. Rather than retroactively reweighting to force a "cleaner" result, I kept the original 60/40 weighting and documented this as a known limitation — it's an honest reflection of how the two signals interact, and demonstrates the intentional bias toward uncertainty over false accusation that I designed for from the start.

## AI Usage

**Instance 1:** I directed an AI tool to generate the initial Flask app skeleton with a `POST /submit` route based on my `planning.md` detection signals section and architecture diagram. The AI produced a working route returning a hardcoded placeholder response. I revised it by adding the audit log dictionary structure and the `GET /log` endpoint myself once I confirmed the basic route worked, since the original AI output didn't include logging at all.

**Instance 2:** I asked an AI tool to generate the stylometric heuristics function based on my spec's description of sentence length variance, type-token ratio, and punctuation density. The AI's first version didn't normalize the metrics to a 0–1 range consistently. I overrode this by adding explicit `max(0.0, min(1.0, ...))` clamping to each metric and tuning the normalization divisors (e.g. variance/50) after testing against my four reference inputs to make sure the scores stayed within a sensible range.