# Provenance Guard — Planning

## Detection Signals

**Signal 1: LLM-based classification (Groq, llama-3.3-70b-versatile)**
Measures holistic semantic and stylistic coherence — whether the text's voice, structure, and reasoning patterns resemble typical AI output (e.g. hedging language, generic transitions, overly balanced argumentation). Output: a score between 0 and 1, where 1 = strongly AI-like.
Blind spot: skilled human writers with formal/technical writing styles can trigger false positives; heavily edited ("humanized") AI text can evade this signal.

**Signal 2: Stylometric heuristics (pure Python)**
Measures quantifiable structural properties: sentence length variance, type-token ratio (vocabulary diversity), and punctuation density. Output: a score between 0 and 1, where 1 = strongly AI-like (more uniform/structured).
Blind spot: short text samples don't provide enough data for meaningful variance calculations; humans writing in controlled/formal registers (legal, academic) can appear artificially uniform.

**Combining signals:** `confidence = (llm_score * 0.6) + (stylometric_score * 0.4)`
The LLM signal is weighted higher because it captures semantic meaning, which is generally a stronger indicator than structural patterns alone.

## Uncertainty Representation

- `0.00 – 0.40` → **Likely Human-Written**
- `0.40 – 0.75` → **Uncertain**
- `0.75 – 1.00` → **Likely AI-Generated**

The uncertain band is intentionally wide (0.35 points) because false positives (labeling a human as AI) are more harmful than false negatives on a creative platform.

## Transparency Label Variants

| Confidence Range | Label Text |
|---|---|
| 0.75–1.00 (Likely AI) | "This content shows strong indicators of AI generation. Multiple signals suggest it was likely written by an AI tool rather than a human." |
| 0.40–0.75 (Uncertain) | "We're not confident enough to make a determination. This content shows mixed signals and could be either AI-generated or human-written." |
| 0.00–0.40 (Likely Human) | "This content shows strong indicators of human authorship. Our analysis did not detect significant signs of AI generation." |

## Appeals Workflow

Any creator can appeal a classification on their own content via `POST /appeal`, providing `content_id` and `creator_reasoning`. On receipt, the system: (1) updates the content's status to `"under_review"`, (2) logs the appeal text alongside the original classification entry in the audit log, (3) returns a confirmation to the creator. A human reviewer opening the appeal queue would see the original text, both signal scores, the confidence score, the label shown, and the creator's stated reasoning side-by-side.

## Anticipated Edge Cases

1. **Non-native English speakers writing formally** — their more uniform sentence structure and "textbook-correct" phrasing can trigger both signals toward "AI-like" despite being entirely human-written.
2. **Short-form content (e.g. short poems, micro-fiction)** — insufficient text length makes stylometric variance calculations unreliable, pushing the stylometric signal toward noisy/meaningless scores.

## Architecture

\`\`\`
SUBMISSION FLOW
================
        [raw text + creator_id]
                │
                ▼
         POST /submit
                │
    ┌───────────┴───────────┐
    ▼                       ▼
Signal 1: Groq LLM    Signal 2: Stylometrics
(semantic score 0-1)  (structural score 0-1)
    │                       │
    └───────────┬───────────┘
                ▼
      Confidence Scorer
   (weighted combination)
                │
                ▼
      Transparency Label
                │
                ▼
          Audit Log (write)
                │
                ▼
      Response → creator


APPEAL FLOW
================
[content_id + creator_reasoning]
                │
                ▼
         POST /appeal
                │
                ▼
 Update status → "under_review"
                │
                ▼
Audit Log (append appeal entry)
                │
                ▼
      Response → confirmation
\`\`\`

Submission flow: text enters through `/submit`, runs through both detection signals in parallel, gets combined into a single confidence score, mapped to a label, logged, and returned. Appeal flow: a creator references an existing `content_id`, the system updates its status and appends the appeal to the same audit log entry chain.

## AI Tool Plan

- **M3 (submission endpoint + Signal 1):** Will provide the Detection Signals section + diagram to the AI tool, ask it to generate the Flask app skeleton and the Groq signal function, then verify by testing the function directly with sample inputs before wiring into the endpoint.
- **M4 (Signal 2 + confidence scoring):** Will provide Detection Signals + Uncertainty Representation sections + diagram, ask for the stylometric function and scoring logic, then verify thresholds match this spec exactly using the 4 test inputs (clear AI, clear human, 2 borderline).
- **M5 (production layer):** Will provide Transparency Label + Appeals Workflow sections + diagram, ask for the label-generation function and `/appeal` endpoint, then verify all 3 label variants are reachable and an appeal correctly updates status + log.