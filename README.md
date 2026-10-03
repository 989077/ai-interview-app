# AI Interview App

Practice realistic interviews as a student or fresher. First role: **Data Analyst**. First UI: **Streamlit**, so we can tune the interviewer before the Next.js rebuild.

## Core loop

1. Pick role, level, and optional resume / job description
2. AI asks a question
3. You answer
4. AI scores the answer and asks a follow-up
5. After 5–10 questions, you get a full report

## Stack (now vs later)

| Now (prototype) | Later |
| --- | --- |
| Streamlit + Claude API | Next.js + FastAPI + Supabase |

## Setup

1. Copy `.env.example` to `.env` and add your [Anthropic API key](https://console.anthropic.com/).
2. Create a virtualenv and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

3. Run the Streamlit prototype:

```powershell
streamlit run prototype\app.py
```

Never commit `.env`. API keys stay in that file only.

## Repo layout

```
backend/app/services/ai.py   # all Claude calls
backend/app/prompts/         # interviewer and scoring prompts
prototype/app.py             # Streamlit interview room
```
