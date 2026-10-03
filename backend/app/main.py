"""FastAPI entry point. Unused while the Streamlit prototype is the UI."""

from fastapi import FastAPI

app = FastAPI(title="AI Interview App", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
