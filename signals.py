import os
from groq import Groq
from dotenv import load_dotenv

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