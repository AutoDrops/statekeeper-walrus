"""The assistant loop: note facts, retrieve relevant ones, answer."""
from __future__ import annotations

from .memory import MemoryStore

SYSTEM = ("You are StateKeeper, a concise personal assistant. Use the remembered facts below; "
          "they are the user's CURRENT state (older values were superseded). If memory does not "
          "cover the question, say so instead of guessing.\nRemembered facts:\n")


class Agent:
    def __init__(self, store: MemoryStore, llm):
        self.store, self.llm, self.turn = store, llm, 0

    def handle(self, message: str) -> dict:
        self.turn += 1
        written = []
        for f in self.llm.extract(message):
            try:
                written.append(self.store.remember(str(f["key"]), str(f["value"]), self.turn).to_dict())
            except ValueError:
                pass
        used = self.store.search(message, k=6)
        system = SYSTEM + ("\n".join(f"- {f.key}: {f.value}" for f in used) or "(none)")
        reply = self.llm.chat(system, message)
        return {"reply": reply, "written": written, "used": [f.to_dict() for f in used],
                "model": self.llm.name}
