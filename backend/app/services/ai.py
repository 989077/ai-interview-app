from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
ROOT = Path(__file__).resolve().parents[3]

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore[misc, assignment]


class InterviewAIError(RuntimeError):
    pass


def _client() -> Anthropic:
    if Anthropic is None:
        raise InterviewAIError("Install dependencies: pip install -r backend/requirements.txt")
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise InterviewAIError(
            "Missing ANTHROPIC_API_KEY. Copy .env.example to .env and paste your key."
        )
    return Anthropic(api_key=api_key)


def _model(kind: str) -> str:
    if kind == "fast":
        return os.getenv("CLAUDE_FAST_MODEL", "claude-haiku-4-5")
    return os.getenv("CLAUDE_SCORING_MODEL", "claude-sonnet-4-5")


def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_question_bank() -> dict[str, list[str]]:
    path = PROMPTS_DIR / "question_bank.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise InterviewAIError("Claude did not return JSON.")
    return json.loads(text[start : end + 1])


def _complete(system: str, user: str, *, kind: str = "scoring") -> dict[str, Any]:
    client = _client()
    last_error: Exception | None = None
    for _ in range(2):
        try:
            message = client.messages.create(
                model=_model(kind),
                max_tokens=1200,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
            return _extract_json(text)
        except (json.JSONDecodeError, InterviewAIError) as exc:
            last_error = exc
    raise InterviewAIError(f"Could not parse Claude JSON after retry: {last_error}")


def generate_question(
    role: str,
    level: str,
    topic: str | None = None,
    history: list[dict[str, Any]] | None = None,
    resume_text: str = "",
    job_description: str = "",
) -> dict[str, Any]:
    """Ask Claude for the next interview question. Falls back to the local bank if the API fails."""
    history = history or []
    asked = [item.get("question", "") for item in history]
    system = _read_prompt("generate_question.txt").format(role=role, level=level)
    user_parts = [
        f"Preferred topic: {topic or 'rotate fairly'}.",
        f"Already asked: {json.dumps(asked, ensure_ascii=False)}",
    ]
    if resume_text.strip():
        user_parts.append(f"Resume excerpt:\n{resume_text[:4000]}")
    if job_description.strip():
        user_parts.append(f"Job description:\n{job_description[:4000]}")
    user_parts.append("Generate the next question now.")
    try:
        data = _complete(system, "\n\n".join(user_parts), kind="fast")
        question = str(data.get("question", "")).strip()
        if not question:
            raise InterviewAIError("Empty question")
        return {
            "question": question,
            "topic": str(data.get("topic") or topic or "sql"),
            "difficulty": str(data.get("difficulty") or "medium"),
        }
    except InterviewAIError:
        bank = load_question_bank()
        topic_key = topic if topic in bank else next(iter(bank))
        for candidate in bank[topic_key]:
            if candidate not in asked:
                return {"question": candidate, "topic": topic_key, "difficulty": "medium"}
        return {
            "question": bank[topic_key][0],
            "topic": topic_key,
            "difficulty": "medium",
        }


def evaluate_answer(question: str, answer: str, role: str, level: str = "fresher") -> dict[str, Any]:
    system = _read_prompt("evaluate_answer.txt").format(role=role, level=level)
    user = f"Question:\n{question}\n\nCandidate answer:\n{answer}"
    data = _complete(system, user, kind="scoring")
    for key in ("score", "correctness", "clarity", "depth"):
        data[key] = max(0, min(10, int(data.get(key, 0))))
    for key in ("strengths", "improve", "better_answer", "follow_up_question", "topic"):
        data[key] = str(data.get(key, "")).strip()
    return data


def final_report(role: str, level: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(t.get("score", 0)) for t in turns]
    avg = round(sum(scores) / len(scores)) if scores else 0
    system = _read_prompt("final_report.txt").format(role=role, level=level)
    user = json.dumps({"turns": turns, "average_score": avg}, ensure_ascii=False)
    data = _complete(system, user, kind="scoring")
    data["overall_score"] = max(0, min(10, int(data.get("overall_score", avg))))
    return data
