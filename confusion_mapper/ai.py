"""
The OpenAI wrapper. One function, classify_with_ai, which is called
in blind mode by the reliability-check session in cli.py.

The prompt is intentionally small and stable. It does not send session
context, does not send prior human labels for the same item, and does
not change based on what the human has decided so far. Keeping that
promise is why assist.py has its own classify_with_confidence function
instead of reaching into this one.
"""

import json

# let the whole package import cleanly even if openai isn't there.
# I ran into this on my friend's laptop and it was annoying.
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    # bind the name so __init__.py can re-export it; every real call site
    # below still checks OPENAI_AVAILABLE first.
    OpenAI = None  # noqa: N816
    OPENAI_AVAILABLE = False

from .taxonomy import ERROR_TYPES



def classify_with_ai(question_text, correct_answer, distractor_text, topic, api_key):
    """
    Ask ChatGPT to classify a single distractor as RF / PK / CF / INT.

    The model is prompted as a cognitive scientist. Temperature is kept low
    (0.2) for consistent, reproducible classifications.

    Returns:
        dict with keys: label (str), reasoning (str), available (bool)
    """
    # no openai library, no network. return something the caller can display.
    if not OPENAI_AVAILABLE:
        return {
            "label": "N/A",
            "reasoning": "OpenAI library not installed. Run: pip install openai",
            "available": False,
        }
    if not api_key:
        return {
            "label": "N/A",
            "reasoning": "No API key. Set OPENAI_API_KEY environment variable.",
            "available": False,
        }

    system_prompt = """You are a cognitive scientist specializing in educational psychology.
You classify MCQ distractor options into one of four cognitive error types.

Definitions:
- RF (Recall Failure): Answer is random, implausible, or reflects no memory of the topic.
- PK (Partial Knowledge): Almost right, correct direction, but model is incomplete.
- CF (Confabulation): Strong, coherent misconception. Student would select this confidently.
- INT (Interference): Correct answer for a DIFFERENT related topic, cross-topic confusion.

Respond ONLY with valid JSON, no extra text:
{
  "label": "CF",
  "reasoning": "One concise sentence grounded in cognitive science."
}"""

    user_prompt = (
        f"Topic: {topic}\n"
        f"Question: {question_text}\n"
        f"Correct answer: {correct_answer}\n"
        f"Distractor to classify: {distractor_text}"
    )

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model       = "gpt-3.5-turbo",
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens  = 120,
            temperature = 0.2,
        )
        raw = response.choices[0].message.content.strip()

        # some models wrap JSON in ```json ... ``` fences even after being
        # told not to. strip them.
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        if result.get("label") not in ERROR_TYPES:
            result["label"] = "RF"  # safe default
        result["available"] = True
        return result

    except json.JSONDecodeError:
        return {
            "label": "RF",
            "reasoning": f"Could not parse AI response.",
            "available": True,
        }
    except Exception as e:
        return {
            "label": "N/A",
            "reasoning": f"API error: {str(e)[:80]}",
            "available": False,
        }


def generate_ai_questions(topic, n, api_key):
    """
    Use ChatGPT to generate n MCQ questions with labeled distractors on topic.
    Returns list of question dicts matching BUILTIN_QUESTIONS format, or [] on failure.
    """
    if not OPENAI_AVAILABLE or not api_key:
        return []

    system_prompt = """You are an educational psychologist creating MCQ questions.
For each question, provide exactly 3 distractors, each with a cognitive error type label.

Types: RF (random/implausible), PK (almost right), CF (confident misconception), INT (topic interference).

Return ONLY a valid JSON array:
[
  {
    "id": "GQ001",
    "topic": "topic name",
    "class_level": 8,
    "question_text": "...",
    "correct_answer": "...",
    "distractors": [
      {"option": "...", "error_type": "CF", "note": "brief explanation"},
      {"option": "...", "error_type": "RF", "note": "brief explanation"},
      {"option": "...", "error_type": "PK", "note": "brief explanation"}
    ]
  }
]"""

    user_prompt = (
        f"Generate {n} MCQ question(s) on: {topic}. "
        f"Target Class 7-8 Indian students. Make distractors realistic and pedagogically interesting."
    )

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model       = "gpt-3.5-turbo",
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens  = 2000,
            temperature = 0.7,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  [Question generation error: {str(e)[:80]}]")
        return []


