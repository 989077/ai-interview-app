from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

load_dotenv(ROOT / ".env")

try:
    import anthropic
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]
    Anthropic = None  # type: ignore[misc, assignment]

MAX_ANSWER_CHARS = 4000


class InterviewAIError(RuntimeError):
    """Something went wrong talking to the AI model. The message is safe to show the user."""


class InterviewConfigError(InterviewAIError):
    """Setup problem (bad API key, Ollama not running, model not pulled). Retrying or the fallback bank won't help."""


def _provider() -> str:
    """Which engine answers: "ollama" (free, local, default) or "anthropic" (Claude API)."""
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()


def _call_ollama(system: str, user: str) -> str:
    """Send one chat request to a local Ollama server and return the reply text."""
    model = _ollama_model()
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",  # forces valid JSON output
            "options": {"temperature": 0.3},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{_ollama_url()}/api/chat", data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", "")
        except Exception:  # noqa: BLE001
            pass
        if exc.code == 404:
            raise InterviewConfigError(
                f"Ollama does not have the model '{model}'. Run: ollama pull {model}"
            ) from exc
        raise InterviewAIError(f"Ollama error ({exc.code}): {detail or exc.reason}") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise InterviewAIError(
            "Ollama took too long to answer. The first request loads the model, so try again."
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise InterviewAIError(
                "Ollama took too long to answer. The first request loads the model, so try again."
            ) from exc
        raise InterviewConfigError(
            f"Cannot reach Ollama at {_ollama_url()}. Start the Ollama app, "
            f"then run: ollama pull {model}"
        ) from exc
    return str(body.get("message", {}).get("content", ""))


def _call_anthropic(system: str, user: str, kind: str) -> str:
    """Send one request to the Claude API and return the reply text."""
    client = _client()
    try:
        message = client.messages.create(
            model=_model(kind),
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as exc:
        raise InterviewConfigError(
            "Claude rejected your API key. Check ANTHROPIC_API_KEY in .env."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise InterviewAIError("Rate limit reached. Wait a minute and try again.") from exc
    except anthropic.APIConnectionError as exc:
        raise InterviewAIError("Could not reach the Claude API. Check your internet.") from exc
    except anthropic.APIStatusError as exc:
        # Includes "credit balance too low" and "model not found".
        raise InterviewAIError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
    return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")


def _client() -> Anthropic:
    if Anthropic is None:
        raise InterviewConfigError("Install dependencies: pip install -r backend/requirements.txt")
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise InterviewConfigError(
            "Missing ANTHROPIC_API_KEY. Copy .env.example to .env and paste your key."
        )
    return Anthropic(api_key=api_key)


def _model(kind: str) -> str:
    if kind == "fast":
        return os.getenv("CLAUDE_FAST_MODEL", "claude-haiku-4-5")
    return os.getenv("CLAUDE_SCORING_MODEL", "claude-sonnet-5-5")


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


def _to_score(value: Any, default: int = 0) -> int:
    """Turn whatever Claude returned (7, 7.4, "7", "7/10") into an int from 0 to 10."""
    try:
        if isinstance(value, str):
            match = re.search(r"\d+(?:\.\d+)?", value)
            if not match:
                return default
            value = float(match.group())
        return max(0, min(10, round(float(value))))
    except (TypeError, ValueError):
        return default


def _complete(system: str, user: str, *, kind: str = "scoring") -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(2):  # one retry, only for unreadable JSON
        if _provider() == "anthropic":
            text = _call_anthropic(system, user, kind)
        else:
            text = _call_ollama(system, user)
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, InterviewAIError) as exc:
            last_error = exc
    raise InterviewAIError(f"Could not read the model's JSON after a retry: {last_error}")


def generate_question(
    role: str,
    level: str,
    topic: str | None = None,
    history: list[dict[str, Any]] | None = None,
    resume_text: str = "",
    job_description: str = "",
) -> dict[str, Any]:
    """Ask Claude for the next interview question.

    Falls back to the local bank if Claude is temporarily unavailable or returns junk.
    Setup problems (missing or bad API key) are raised, not hidden.
    """
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
    except InterviewConfigError:
        raise
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


def evaluate_answer(
    question: str,
    answer: str,
    role: str,
    level: str = "fresher",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one answer. `context` carries the original question and answer when this is a follow-up."""
    system = _read_prompt("evaluate_answer.txt").format(role=role, level=level)

    # The answer is untrusted text: cap it and make sure it can't close our <answer> tag.
    safe_answer = answer.replace("</answer>", "").strip()[:MAX_ANSWER_CHARS]

    parts = [f"Question:\n{question}"]
    if context:
        parts.append(
            "This question is a follow-up. Earlier in the interview:\n"
            f"Original question: {context.get('question', '')}\n"
            f"Candidate's earlier answer: {str(context.get('answer', ''))[:1500]}\n"
            f"Weakness noted: {context.get('improve', '')}"
        )
    parts.append(f"<answer>\n{safe_answer}\n</answer>")

    data = _complete(system, "\n\n".join(parts), kind="scoring")
    for key in ("score", "correctness", "clarity", "depth"):
        data[key] = _to_score(data.get(key))
    for key in ("strengths", "improve", "better_answer", "follow_up_question", "topic"):
        data[key] = str(data.get(key, "")).strip()
    return data


def final_report(role: str, level: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [_to_score(t.get("score")) for t in turns]
    avg = round(sum(scores) / len(scores)) if scores else 0
    system = _read_prompt("final_report.txt").format(role=role, level=level)
    user = json.dumps({"turns": turns, "average_score": avg}, ensure_ascii=False)
    data = _complete(system, user, kind="scoring")
    # The score is arithmetic, so code owns it. Claude only writes the words.
    data["overall_score"] = avg
    for key in ("strengths", "weak_topics", "next_practice"):
        value = data.get(key, [])
        data[key] = value if isinstance(value, list) else [str(value)]
    data["summary"] = str(data.get("summary", "")).strip()
    return data
