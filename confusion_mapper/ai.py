"""
ChatGPT-based AI rater: distractor classification and question generation.

Moved unmodified from the "SECTION 4, CHATGPT / AI RATER" block of the
pre-2.6.0 single-file confusion_mapper.py during the v2.6.0 package
reorganization. No logic changed.
"""

import json

# Graceful fallback if openai not installed
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # noqa: N816 -- keeps the name importable when openai is absent.
    # This line is new in v2.6.0. The original single-file module left `OpenAI`
    # unbound on ImportError, which was harmless there because nothing at
    # module level ever touched it. `confusion_mapper/__init__.py` now
    # re-exports `OpenAI` at package level for API parity, so the name has
    # to exist even when the import failed; every guarded call site below
    # still checks OPENAI_AVAILABLE before ever using it, so this changes
    # no runtime behavior.
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
    # Graceful degradation
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

        # Strip markdown fences if present
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


