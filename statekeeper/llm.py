"""LLM access: Nebius Token Factory (OpenAI-compatible) or an offline mock."""
from __future__ import annotations

import json
import os
import re

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/Llama-3_1-Nemotron-Ultra-253B-v1"

NOTE_PROMPT = (
    "Extract durable personal facts the user states about themselves in the message "
    "(preferences, plans, goals, decisions, names, places, schedules). Use short stable "
    "keys like 'home city', 'diet', 'gym days'. If the user changes something, reuse the "
    "same key. Reply with JSON only: {\"facts\": [{\"key\": str, \"value\": str}]}. "
    "Return {\"facts\": []} if nothing durable is stated.")


class MockLLM:
    """Deterministic offline stand-in so the app and tests run without a key."""
    name = "mock"
    _PATTERNS = [
        (re.compile(r"\bmy ([a-z ]{2,30}?) (?:is|are) (?:now )?([^.,!?]+?)(?= and i\b|[.,!?]|$)", re.I), None),
        (re.compile(r"\bi (?:now )?live in ([^.,!?]+?)(?= and\b|[.,!?]|$)", re.I), "home city"),
        (re.compile(r"\bi moved to ([^.,!?]+?)(?= and\b| last\b|[.,!?]|$)", re.I), "home city"),
        (re.compile(r"\bi(?: am|'m) (?:a |an )?(vegetarian|vegan|pescatarian)\b", re.I), "diet"),
        (re.compile(r"\bi work as (?:a |an )?([^.,!?]+)", re.I), "job"),
    ]

    def extract(self, text: str) -> list[dict]:
        out = []
        for pat, key in self._PATTERNS:
            for m in pat.finditer(text):
                if key is None:
                    out.append({"key": m.group(1), "value": m.group(2)})
                else:
                    out.append({"key": key, "value": m.group(1)})
        return out

    def chat(self, system: str, user: str) -> str:
        known = [l[2:] for l in system.splitlines() if l.startswith("- ")]
        if known:
            return "Here is what I remember that seems relevant: " + "; ".join(known) + "."
        return "Noted. I don't have anything relevant in memory for that yet."


class NebiusLLM:
    """Runtime calls to Nebius Token Factory via the OpenAI-compatible API."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        from openai import OpenAI
        self.name = model or os.environ.get("STATEKEEPER_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(base_url=base_url or os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
                             api_key=os.environ["NEBIUS_API_KEY"])

    def _complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        r = self.client.chat.completions.create(
            model=self.name, temperature=temperature, max_tokens=600,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (r.choices[0].message.content or "").strip()

    def extract(self, text: str) -> list[dict]:
        raw = self._complete(NOTE_PROMPT, text, temperature=0.0)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            return []
        return [f for f in data.get("facts", []) if isinstance(f, dict) and f.get("key") and f.get("value")]

    def chat(self, system: str, user: str) -> str:
        return self._complete(system, user)


def make_llm():
    if os.environ.get("STATEKEEPER_MOCK") == "1" or not os.environ.get("NEBIUS_API_KEY"):
        return MockLLM()
    return NebiusLLM()
