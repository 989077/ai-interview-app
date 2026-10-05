"""FastAPI entry point. Run from the project root:

    uvicorn backend.app.main:app --reload

(or `uvicorn app.main:app --reload` from inside the backend folder)

then open http://localhost:8000/docs to try the endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import sessions

app = FastAPI(title="AI Interview App", version="0.2.0")

# Lets the Next.js frontend (Phase 3, http://localhost:3000) call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
