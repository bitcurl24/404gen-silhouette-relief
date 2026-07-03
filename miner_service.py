from __future__ import annotations

import io
import json
import threading
import zipfile
from dataclasses import dataclass, field
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from generator import build_module


class PromptItem(BaseModel):
    stem: str
    image_url: str


class GenerateRequest(BaseModel):
    prompts: list[PromptItem]
    seed: int


@dataclass
class State:
    status: Literal["ready", "generating", "complete"] = "ready"
    stems: set[str] = field(default_factory=set)
    progress: int = 0
    total: int = 0
    results: dict[str, str] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


app = FastAPI(title="404gen-silhouette-relief")
state = State()
lock = threading.Lock()


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/status")
def status(replacements_remaining: int = 0) -> JSONResponse:
    with lock:
        return JSONResponse({
            "status": state.status,
            "progress": state.progress if state.status == "generating" else None,
            "total": state.total if state.status == "generating" else None,
            "payload": {
                "strategy": "silhouette-relief",
                "batch_size": state.total,
                "replacements_remaining": replacements_remaining,
            },
        })


@app.post("/generate")
def generate(req: GenerateRequest) -> JSONResponse:
    if not req.prompts:
        raise HTTPException(status_code=400, detail={"detail": "prompts must not be empty"})
    stems = {item.stem for item in req.prompts}
    with lock:
        if state.status == "generating":
            if stems == state.stems:
                return JSONResponse({"accepted": state.total})
            raise HTTPException(status_code=409, detail={"detail": "Cannot accept batch", "current_status": state.status})
        state.status = "generating"
        state.stems = stems
        state.progress = 0
        state.total = len(req.prompts)
        state.results = {}
        state.failures = {}
    for item in req.prompts:
        try:
            state.results[f"{item.stem}.js"] = build_module(item.stem, item.image_url, req.seed)
        except Exception as exc:
            state.failures[item.stem] = str(exc)
        finally:
            state.progress += 1
    state.status = "complete"
    return JSONResponse({"accepted": len(req.prompts)})


@app.get("/results")
def results() -> StreamingResponse:
    with lock:
        if state.status != "complete":
            raise HTTPException(status_code=409, detail={"detail": "Results not ready", "current_status": state.status})
        payload = dict(state.results)
        failures = dict(state.failures)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in payload.items():
            zf.writestr(name, content)
        if failures:
            zf.writestr("_failed.json", json.dumps(failures, indent=2))
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/zip")
