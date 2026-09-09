"""Runnable demonstration API for Kivi's word-level memory system.

Endpoints:
    POST /api/observations   -- teach the system a correction
    GET  /api/memory         -- inspect current memory state
    GET  /api/observations   -- inspect the raw observation log
    POST /api/resolve        -- run ASR/formatted text through memory
    POST /api/reset          -- wipe all learned state
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.memory import MemoryStore

APP_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_ROOT / "static"

app = FastAPI(title="Kivi Word Memory")
store = MemoryStore()


class ObservationIn(BaseModel):
    heard_word: str
    corrected_word: str
    context_before: Optional[str] = None
    category: Optional[str] = None


class ResolveIn(BaseModel):
    formatted_text: str
    asr_text: Optional[str] = None


@app.post("/api/observations")
def add_observation(obs: ObservationIn):
    try:
        result = store.add_observation(
            obs.heard_word, obs.corrected_word, obs.context_before, obs.category
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "entry": result}


@app.get("/api/memory")
def get_memory():
    return {"entries": store.memory_state()}


@app.get("/api/observations")
def get_observations():
    return {"observations": store.observations()}


@app.post("/api/resolve")
def resolve(payload: ResolveIn):
    return store.resolve(payload.formatted_text, payload.asr_text)


@app.post("/api/reset")
def reset():
    store.reset()
    return {"ok": True}


# --- static frontend -------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
