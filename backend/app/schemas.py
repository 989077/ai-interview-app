"""Request and response shapes for the API. Pydantic validates every field."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SessionCreate(BaseModel):
    role: Literal["Data Analyst"] = "Data Analyst"
    level: Literal["fresher", "junior", "mid"] = "fresher"
    n_questions: int = Field(default=6, ge=5, le=10)
    topic: str | None = Field(default=None, description="Starting topic, or null to rotate")
    resume_text: str = Field(default="", max_length=20000)
    job_description: str = Field(default="", max_length=20000)


class QuestionOut(BaseModel):
    number: int = Field(description="1-based position in the interview")
    question: str
    topic: str
    difficulty: str
    is_follow_up: bool


class SessionOut(BaseModel):
    session_id: str
    status: Literal["in_progress", "finished"]
    n_questions: int
    answered: int
    question: QuestionOut | None


class AnswerIn(BaseModel):
    answer: str = Field(max_length=4000)

    @field_validator("answer")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Answer cannot be empty")
        return value


class FeedbackOut(BaseModel):
    score: int
    correctness: int
    clarity: int
    depth: int
    topic: str
    strengths: str
    improve: str
    better_answer: str


class AnswerOut(BaseModel):
    feedback: FeedbackOut
    answered: int
    finished: bool
    next_question: QuestionOut | None


class TurnOut(BaseModel):
    question: str
    topic: str
    is_follow_up: bool
    answer: str
    score: int
    strengths: str
    improve: str
    better_answer: str


class ReportOut(BaseModel):
    overall_score: int
    summary: str
    strengths: list[str]
    weak_topics: list[str]
    next_practice: list[str]
    turns: list[TurnOut]


class HistoryItem(BaseModel):
    id: str
    created_at: str
    role: str
    level: str
    n_questions: int
    answered: int
    status: Literal["in_progress", "finished"]
    overall_score: int | None
