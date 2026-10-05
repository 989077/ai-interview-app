"""The three interview endpoints. Routes only translate HTTP <-> the session service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app import schemas
from backend.app.services import sessions
from backend.app.services.ai import InterviewAIError, InterviewConfigError

router = APIRouter(prefix="/sessions", tags=["interview"])


def _ai_error(exc: InterviewAIError) -> HTTPException:
    # Setup problems (Ollama off, bad key) are 503: the server can't work until fixed.
    # Everything else from the model is a 502: the model failed this time, try again.
    status = 503 if isinstance(exc, InterviewConfigError) else 502
    return HTTPException(status_code=status, detail=str(exc))


@router.post("", response_model=schemas.SessionOut, status_code=201)
def start_session(body: schemas.SessionCreate) -> dict:
    try:
        session = sessions.create_session(**body.model_dump())
    except sessions.InvalidTopic as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InterviewAIError as exc:
        raise _ai_error(exc) from exc
    return sessions.public_state(session)


@router.get("", response_model=list[schemas.HistoryItem])
def history(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    """Past interviews, newest first."""
    return sessions.list_history(limit)


@router.delete("/{session_id}", status_code=204)
def remove_session(session_id: str) -> None:
    try:
        sessions.delete_session(session_id)
    except sessions.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/{session_id}", response_model=schemas.SessionOut)
def session_state(session_id: str) -> dict:
    try:
        return sessions.public_state(sessions.get_session(session_id))
    except sessions.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/{session_id}/answer", response_model=schemas.AnswerOut)
def answer_question(session_id: str, body: schemas.AnswerIn) -> dict:
    try:
        session, feedback = sessions.submit_answer(session_id, body.answer)
    except sessions.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except sessions.SessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewAIError as exc:
        raise _ai_error(exc) from exc
    state = sessions.public_state(session)
    return {
        "feedback": feedback,
        "answered": state["answered"],
        "finished": state["status"] == "finished",
        "next_question": state["question"],
    }


@router.get("/{session_id}/report", response_model=schemas.ReportOut)
def session_report(session_id: str) -> dict:
    try:
        return sessions.get_report(session_id)
    except sessions.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except sessions.SessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
