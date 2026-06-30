import os
from groq import Groq
from dotenv import load_dotenv
import re
import statistics

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def llm_signal(text: str) -> float:
    """
    Sends text to Groq and asks it to assess whether it reads as
    AI-generated or human-written. Returns a score between 0 and 1,
    where 1 = strongly AI-like.
    """
    prompt = f"""You are an expert at detecting AI-generated text.
Analyze the following text and estimate the probability that it was
written by an AI rather than a human.

Respond with ONLY a single number between 0 and 1 (e.g. 0.73).
Do not include any explanation, words, or punctuation other than the number.

Text:
\"\"\"
{text}
\"\"\"
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    try:
        score = float(raw)
        score = max(0.0, min(1.0, score))  # clamp to [0,1]
    except ValueError:
        score = 0.5  # fallback if the model doesn't return a clean number

    return score


if __name__ == "__main__":
    # Quick manual test
    test_ai = "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications."
    test_human = "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it."

    print("AI-like text score:", llm_signal(test_ai))
    print("Human-like text score:", llm_signal(test_human))

    

def stylometric_signal(text: str) -> float:
    """
    Computes structural/statistical properties of the text and combines
    them into a single score between 0 and 1, where 1 = strongly AI-like
    (more uniform sentence length, less vocabulary diversity).
    """
    # Split into sentences (basic split on . ! ?)
    sentences = re.split(r'(?<=[.!?]) +', text.strip())
    sentences = [s for s in sentences if s]

    words = re.findall(r"\b\w+\b", text.lower())

    if len(sentences) < 2 or len(words) < 5:
        # Not enough data to compute meaningful variance — return neutral score
        return 0.5

    # --- Metric 1: Sentence length variance (in words) ---
    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
    length_variance = statistics.pvariance(sentence_lengths)
    # Low variance = more uniform = more AI-like.
    # Normalize: assume variance of 0-50 is the realistic range
    uniformity_score = max(0.0, min(1.0, 1 - (length_variance / 50)))

    # --- Metric 2: Type-token ratio (vocabulary diversity) ---
    ttr = len(set(words)) / len(words)
    # Lower TTR (less diverse vocabulary) = more AI-like
    # AI text tends toward TTR ~0.4-0.6 on longer passages, human can vary more
    diversity_score = max(0.0, min(1.0, 1 - ttr))

    # --- Metric 3: Punctuation density ---
    punctuation_count = len(re.findall(r"[,;:\-—]", text))
    punctuation_density = punctuation_count / len(words)
    # AI text tends to have more "even" punctuation usage; very low or very
    # high density both lean toward "less typical of casual human writing"
    punctuation_score = max(0.0, min(1.0, punctuation_density * 5))

    # Combine the three metrics (equal weight for now)
    combined = (uniformity_score + diversity_score + punctuation_score) / 3
    return round(combined, 2)


if __name__ == "__main__":
    test_ai = "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
    test_human = "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"

    print("AI-like text stylometric score:", stylometric_signal(test_ai))
    print("Human-like text stylometric score:", stylometric_signal(test_human))