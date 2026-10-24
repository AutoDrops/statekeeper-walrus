"""FastAPI web UI and JSON API."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .agent import Agent
from .llm import make_llm
from .memory import MemoryStore

class Msg(BaseModel):
    message: str


STATIC = Path(__file__).resolve().parent.parent / "static"


def create_app(db_path: str | None = None, llm=None) -> FastAPI:
    from .walrus import backend_from_env
    from .memwal_sink import memwal_from_env, Fanout
    from .tatum import tatum_from_env
    store = MemoryStore(db_path or os.environ.get("STATEKEEPER_DB", "statekeeper.db"),
                        _sink(backend_from_env(), memwal_from_env(), Fanout))
    tatum = tatum_from_env()
    agent = Agent(store, llm or make_llm())
    app = FastAPI(title="StateKeeper")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.post("/api/chat")
    def chat(m: Msg):
        if not m.message.strip():
            raise HTTPException(400, "empty message")
        return agent.handle(m.message)

    @app.get("/api/memory")
    def memory(include_history: bool = True):
        facts = store.all() if include_history else store.active()
        return {"model": agent.llm.name, "facts": [f.to_dict() for f in facts]}

    @app.delete("/api/memory/{fact_id}")
    def forget(fact_id: int):
        if not store.forget(fact_id):
            raise HTTPException(404, "no active fact with that id")
        return {"ok": True}

    @app.get("/api/onchain/{object_id}")
    def onchain(object_id: str):
        """Onchain status of a Sui object (e.g. a Walrus Blob) via Tatum Sui RPC."""
        return {"source": type(tatum).__name__, **tatum.object_status(object_id)}

    return app


def _sink(walrus, memwal, fanout):
    parts = [b for b in (walrus, memwal) if b]
    return fanout(*parts) if parts else None


app = create_app() if os.environ.get("STATEKEEPER_NO_AUTOAPP") != "1" else None
