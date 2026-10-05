"""Interview flow: what to ask next, when to follow up, when to finish.

Sessions live in a Python dict for now. Phase 4 replaces this with a database;
the functions below are the only place that needs to change.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.services import ai

FOLLOW_UP_BELOW = 7  # answers scoring under this get one follow-up question


class SessionNotFound(KeyError):
    pass


class SessionStateError(RuntimeError):
    """The request doesn't fit the session's current state (finished, busy, not finished)."""


class InvalidTopic(ValueError):
    pass


@dataclass
class Session:
    id: str
    role: str
    level: str
    n_questions: int
    topic_pref: str | None
    resume_text: str
    job_description: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    current: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    busy: bool = False  # True while a slow model call is running for this session
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_SESSIONS: dict[str, Session] = {}
_STORE_LOCK = threading.Lock()


def _topics() -> list[str]:
    return list(ai.load_question_bank().keys())


def _next_fresh_question(s: Session) -> dict[str, Any]:
    topics = _topics()
    main_count = sum(1 for t in s.turns if not t["is_follow_up"])
    if main_count == 0 and s.topic_pref:
        topic = s.topic_pref
    else:
        topic = topics[main_count % len(topics)]
    question = ai.generate_question(
        role=s.role,
        level=s.level,
        topic=topic,
        history=s.turns,
        resume_text=s.resume_text,
        job_description=s.job_description,
    )
    return {**question, "is_follow_up": False, "parent": None}


def _public_question(s: Session) -> dict[str, Any] | None:
    if s.current is None:
        return None
    return {
        "number": len(s.turns) + 1,
        "question": s.current["question"],
        "topic": s.current.get("topic", ""),
        "difficulty": s.current.get("difficulty", "medium"),
        "is_follow_up": s.current["is_follow_up"],
    }


def public_state(s: Session) -> dict[str, Any]:
    return {
        "session_id": s.id,
        "status": "finished" if s.report else "in_progress",
        "n_questions": s.n_questions,
        "answered": len(s.turns),
        "question": _public_question(s),
    }


def get_session(session_id: str) -> Session:
    with _STORE_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise SessionNotFound(session_id)
    return session


def create_session(
    *,
    role: str,
    level: str,
    n_questions: int,
    topic: str | None,
    resume_text: str,
    job_description: str,
) -> Session:
    if topic is not None and topic not in _topics():
        raise InvalidTopic(f"Unknown topic '{topic}'. Choose one of: {', '.join(_topics())}")
    session = Session(
        id=uuid.uuid4().hex,
        role=role,
        level=level,
        n_questions=n_questions,
        topic_pref=topic,
        resume_text=resume_text,
        job_description=job_description,
    )
    # Ask the model first. If it fails (Ollama not running), no half-made session is stored.
    session.current = _next_fresh_question(session)
    with _STORE_LOCK:
        _SESSIONS[session.id] = session
    return session


def submit_answer(session_id: str, answer: str) -> tuple[Session, dict[str, Any]]:
    session = get_session(session_id)
    with session.lock:
        if session.busy:
            raise SessionStateError("The previous answer is still being scored. Wait a moment.")
        if session.report is not None or session.current is None:
            raise SessionStateError("This interview is already finished.")
        session.busy = True
    try:
        current = session.current
        evaluation = ai.evaluate_answer(
            current["question"],
            answer,
            session.role,
            session.level,
            context=current.get("parent"),
        )
        is_follow_up = current["is_follow_up"]
        turn = {
            "question": current["question"],
            "difficulty": current.get("difficulty"),
            "answer": answer,
            **evaluation,
            "topic": evaluation.get("topic") or current.get("topic", ""),
            "is_follow_up": is_follow_up,
        }

        finished = len(session.turns) + 1 >= session.n_questions
        next_question: dict[str, Any] | None = None
        report: dict[str, Any] | None = None

        # Do every slow model call BEFORE changing the session, so a failure
        # leaves the interview exactly where it was and the user can retry.
        if finished:
            report = ai.final_report(session.role, session.level, session.turns + [turn])
        else:
            follow = evaluation.get("follow_up_question")
            if not is_follow_up and turn["score"] < FOLLOW_UP_BELOW and follow:
                next_question = {
                    "question": follow,
                    "topic": turn["topic"],
                    "difficulty": current.get("difficulty", "medium"),
                    "is_follow_up": True,
                    "parent": {
                        "question": turn["question"],
                        "answer": answer,
                        "improve": turn.get("improve", ""),
                    },
                }
            else:
                # _next_fresh_question counts main questions, so include this turn.
                session.turns.append(turn)
                try:
                    next_question = _next_fresh_question(session)
                finally:
                    session.turns.pop()

        session.turns.append(turn)
        session.current = None if finished else next_question
        session.report = report
        return session, evaluation
    finally:
        session.busy = False


def get_report(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session.report is None:
        raise SessionStateError("The interview is not finished yet.")
    return {
        **session.report,
        "turns": [
            {
                "question": t["question"],
                "topic": t.get("topic", ""),
                "is_follow_up": t["is_follow_up"],
                "answer": t["answer"],
                "score": t["score"],
                "strengths": t.get("strengths", ""),
                "improve": t.get("improve", ""),
                "better_answer": t.get("better_answer", ""),
            }
            for t in session.turns
        ],
    }
