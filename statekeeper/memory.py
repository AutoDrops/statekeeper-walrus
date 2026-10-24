"""A small, transparent, persistent fact store written for the hackathon.

Each fact is a (key, value) pair. Writing a new value for an existing key does
not overwrite history: the old row is marked `superseded` and linked to the
row that replaced it, so the memory view can show what changed and when.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "my", "i", "me", "what", "do", "you", "to", "of",
         "and", "in", "on", "for", "it", "are", "was", "that", "this", "your", "now"}


# Tiny hand-written synonym map so everyday questions reach stable keys.
_ALIASES = {"live": {"home", "city"}, "lives": {"home", "city"}, "moved": {"home", "city"},
            "eat": {"diet"}, "food": {"diet"}, "work": {"job"}, "gym": {"gym"}}


def tokens(text: str) -> set[str]:
    out = {t for t in _WORD.findall(text.lower()) if t not in _STOP}
    for t in list(out):
        out |= _ALIASES.get(t, set())
    return out


def norm_key(key: str) -> str:
    return " ".join(_WORD.findall(key.lower()))


@dataclass
class Fact:
    id: int
    key: str
    value: str
    status: str            # "active" | "superseded" | "forgotten"
    created_at: float
    turn: int              # conversation turn the fact came from
    replaced_by: Optional[int] = None
    blob_id: Optional[str] = None   # Walrus blob holding this event, if any

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryStore:
    def __init__(self, path: str = ":memory:", walrus=None):
        self.walrus = walrus
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL, value TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at REAL NOT NULL, turn INTEGER NOT NULL DEFAULT 0,
                replaced_by INTEGER)""")
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(facts)")}
        if "blob_id" not in cols:
            self.db.execute("ALTER TABLE facts ADD COLUMN blob_id TEXT")
        self.db.commit()

    def _publish(self, event: dict) -> Optional[str]:
        """Write one memory event to Walrus; local SQLite still works if it fails."""
        if not self.walrus:
            return None
        try:
            return self.walrus.put(json.dumps(event, sort_keys=True).encode())["blob_id"]
        except Exception:
            return None

    def _row(self, r) -> Fact:
        return Fact(*r)

    def snapshot(self) -> str:
        """Publish the full fact table (with history) to Walrus; return the blob id."""
        if not self.walrus:
            raise RuntimeError("no Walrus backend configured")
        data = json.dumps({"app": "statekeeper", "version": 1,
                           "facts": [f.to_dict() for f in self.all()]}, sort_keys=True)
        return self.walrus.put(data.encode())["blob_id"]

    @classmethod
    def restore(cls, blob_id: str, walrus, path: str = ":memory:") -> "MemoryStore":
        """Rebuild a store on any machine from a snapshot blob id."""
        snap = json.loads(walrus.get(blob_id))
        st = cls(path, walrus)
        for f in snap["facts"]:
            st.db.execute("INSERT INTO facts (id,key,value,status,created_at,turn,replaced_by,blob_id) "
                          "VALUES (:id,:key,:value,:status,:created_at,:turn,:replaced_by,:blob_id)", f)
        st.db.commit()
        return st

    def remember(self, key: str, value: str, turn: int = 0) -> Fact:
        """Store a fact; supersede the current value for the same key if different."""
        key, value = norm_key(key), value.strip()
        if not key or not value:
            raise ValueError("key and value required")
        cur = self.current(key)
        if cur and cur.value.lower() == value.lower():
            return cur
        c = self.db.execute(
            "INSERT INTO facts (key, value, status, created_at, turn) VALUES (?,?, 'active', ?, ?)",
            (key, value, time.time(), turn))
        new_id = c.lastrowid
        if cur:
            self.db.execute("UPDATE facts SET status='superseded', replaced_by=? WHERE id=?",
                            (new_id, cur.id))
        bid = self._publish({"app": "statekeeper", "op": "remember", "key": key, "value": value,
                             "turn": turn, "supersedes": cur.id if cur else None, "id": new_id})
        if bid:
            self.db.execute("UPDATE facts SET blob_id=? WHERE id=?", (bid, new_id))
        self.db.commit()
        return self.get(new_id)

    def forget(self, fact_id: int) -> bool:
        c = self.db.execute("UPDATE facts SET status='forgotten' WHERE id=? AND status='active'",
                            (fact_id,))
        self.db.commit()
        if c.rowcount:
            self._publish({"app": "statekeeper", "op": "forget", "id": fact_id})
        return c.rowcount > 0

    def get(self, fact_id: int) -> Optional[Fact]:
        r = self.db.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        return self._row(r) if r else None

    def current(self, key: str) -> Optional[Fact]:
        r = self.db.execute("SELECT * FROM facts WHERE key=? AND status='active' "
                            "ORDER BY id DESC LIMIT 1", (norm_key(key),)).fetchone()
        return self._row(r) if r else None

    def active(self) -> list[Fact]:
        return [self._row(r) for r in self.db.execute(
            "SELECT * FROM facts WHERE status='active' ORDER BY id")]

    def all(self) -> list[Fact]:
        return [self._row(r) for r in self.db.execute("SELECT * FROM facts ORDER BY id")]

    def history(self, key: str) -> list[Fact]:
        return [self._row(r) for r in self.db.execute(
            "SELECT * FROM facts WHERE key=? ORDER BY id", (norm_key(key),))]

    def search(self, query: str, k: int = 5) -> list[Fact]:
        """Keyword-overlap retrieval over active facts (keys weighted 2x)."""
        q = tokens(query)
        scored = []
        for f in self.active():
            s = 2 * len(q & tokens(f.key)) + len(q & tokens(f.value))
            if s:
                scored.append((s, f.id, f))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [f for _, _, f in scored[:k]]
