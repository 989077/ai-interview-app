from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.ai import (  # noqa: E402
    InterviewAIError,
    evaluate_answer,
    final_report,
    generate_question,
    load_question_bank,
)

TOPICS = list(load_question_bank().keys())
FOLLOW_UP_BELOW = 7  # answers scoring under this get one follow-up question

st.set_page_config(page_title="AI Interview Practice", layout="wide")
st.title("AI Interview Practice")
st.caption("Data Analyst first. Text interviews now. Voice comes later.")


def reset_session() -> None:
    for key in ("started", "turns", "current", "report", "q_index"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.header("Session")
    role = st.selectbox("Role", ["Data Analyst"])
    level = st.selectbox("Level", ["fresher", "junior", "mid"])
    n_questions = st.slider("Number of questions", min_value=5, max_value=10, value=6)
    topic = st.selectbox("Starting topic", ["rotate"] + TOPICS)
    resume_text = st.text_area("Resume (optional)", height=120)
    job_description = st.text_area("Job description (optional)", height=120)
    if st.button("Start interview", type="primary"):
        reset_session()
        st.session_state.started = True
        st.session_state.role = role
        st.session_state.level = level
        st.session_state.n_questions = n_questions
        st.session_state.turns = []
        st.session_state.q_index = 0
        st.session_state.resume_text = resume_text
        st.session_state.job_description = job_description
        st.session_state.topic_pref = None if topic == "rotate" else topic
        st.session_state.current = None
        st.session_state.report = None
        st.rerun()
    if st.button("Reset"):
        reset_session()
        st.rerun()

if not st.session_state.get("started"):
    st.info("Pick role and level in the sidebar, then start. You need an Anthropic API key in `.env`.")
    st.markdown(
        """
**What this prototype tests**
- Honest scoring, not compliments
- Smart follow-ups on weak answers
- JSON scores you can later chart
        """
    )
    st.stop()

role = st.session_state.role
level = st.session_state.level
n_questions = st.session_state.n_questions
turns: list = st.session_state.turns

if st.session_state.report:
    report = st.session_state.report
    st.subheader("Interview report")
    st.metric("Overall score", f"{report.get('overall_score', 0)} / 10")
    st.write(report.get("summary", ""))
    col1, col2, col3 = st.columns(3)
    col1.write("**Strengths**")
    col1.write(report.get("strengths", []))
    col2.write("**Weak topics**")
    col2.write(report.get("weak_topics", []))
    col3.write("**Practice next**")
    col3.write(report.get("next_practice", []))
    st.divider()
    for i, turn in enumerate(turns, start=1):
        with st.expander(f"Q{i} · {turn.get('topic', '')} · {turn.get('score', 0)}/10"):
            st.markdown(f"**Question:** {turn['question']}")
            st.markdown(f"**Your answer:** {turn['answer']}")
            st.markdown(f"**Strengths:** {turn.get('strengths', '')}")
            st.markdown(f"**Improve:** {turn.get('improve', '')}")
            st.markdown(f"**Better answer:** {turn.get('better_answer', '')}")
    st.stop()

if st.session_state.current is None:
    with st.spinner("Preparing the next question..."):
        try:
            # Rotate by number of main questions, so follow-ups don't skip topics.
            main_count = sum(1 for t in turns if not t.get("is_follow_up"))
            if main_count == 0 and st.session_state.topic_pref:
                next_topic = st.session_state.topic_pref
            else:
                next_topic = TOPICS[main_count % len(TOPICS)]
            st.session_state.current = generate_question(
                role=role,
                level=level,
                topic=next_topic,
                history=turns,
                resume_text=st.session_state.get("resume_text", ""),
                job_description=st.session_state.get("job_description", ""),
            )
        except InterviewAIError as exc:
            st.error(str(exc))
            st.stop()

current = st.session_state.current
progress = len(turns) + 1
st.progress(len(turns) / n_questions, text=f"Question {progress} of {n_questions}")
st.markdown(f"**Topic:** `{current.get('topic', '')}` · **Difficulty:** `{current.get('difficulty', '')}`")
st.subheader(current["question"])

answer = st.text_area("Your answer", height=180, key=f"answer_{progress}")
submit = st.button("Submit answer", type="primary", disabled=not answer.strip())

if submit:
    with st.spinner("Scoring your answer..."):
        try:
            evaluation = evaluate_answer(
                current["question"],
                answer.strip(),
                role,
                level,
                context=current.get("parent"),
            )
        except InterviewAIError as exc:
            st.error(str(exc))
            st.stop()
    is_follow_up = current.get("parent") is not None
    turn = {
        "question": current["question"],
        "difficulty": current.get("difficulty"),
        "answer": answer.strip(),
        **evaluation,
        "topic": evaluation.get("topic") or current.get("topic"),
        "is_follow_up": is_follow_up,
    }
    turns.append(turn)
    st.session_state.turns = turns
    st.session_state.last_feedback = evaluation
    if len(turns) >= n_questions:
        with st.spinner("Writing your report..."):
            try:
                st.session_state.report = final_report(role, level, turns)
            except InterviewAIError as exc:
                st.session_state.report = {
                    "overall_score": round(sum(t["score"] for t in turns) / len(turns)),
                    "summary": str(exc),
                    "strengths": [],
                    "weak_topics": [],
                    "next_practice": [],
                }
        st.session_state.current = None
        st.rerun()
    # A weak answer earns ONE follow-up. After that (or after a good answer),
    # move on to a fresh question on the next topic.
    follow = evaluation.get("follow_up_question")
    if not is_follow_up and turn["score"] < FOLLOW_UP_BELOW and follow:
        st.session_state.current = {
            "question": follow,
            "topic": turn["topic"],
            "difficulty": current.get("difficulty", "medium"),
            "parent": {
                "question": turn["question"],
                "answer": turn["answer"],
                "improve": turn.get("improve", ""),
            },
        }
    else:
        st.session_state.current = None
    st.rerun()

if st.session_state.get("last_feedback") and turns:
    last = st.session_state.last_feedback
    st.divider()
    st.markdown(f"**Last score:** {last.get('score', 0)}/10")
    cols = st.columns(3)
    cols[0].metric("Correctness", last.get("correctness", 0))
    cols[1].metric("Clarity", last.get("clarity", 0))
    cols[2].metric("Depth", last.get("depth", 0))
    st.markdown(f"**Strengths:** {last.get('strengths', '')}")
    st.markdown(f"**Improve:** {last.get('improve', '')}")
