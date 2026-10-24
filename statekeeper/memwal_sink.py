"""Optional Walrus Memory (MemWal) sink.

Mirrors each StateKeeper memory event into Walrus Memory as a short text memory
(encrypted on Walrus under the user's MemWalAccount). SQLite stays the source of
truth for supersede/forget.

STATEKEEPER_MEMWAL=off|mock|staging|live   (default off)
  live    - hosted relayer (default mainnet, free: relayer pays storage); credentials from
            MEMWAL_KEY_FILE / MEMWAL_ACCOUNT_ID_FILE
  mock    - the SDK's own offline MemWalMock (no network)
  staging - Walrus Memory testnet relayer; needs MEMWAL_KEY + MEMWAL_ACCOUNT_ID
            (from staging.memory.walrus.xyz), read from the environment only.
Mainnet is deliberately not wired in this branch.
"""
from __future__ import annotations

import asyncio
import json
import os

STAGING_RELAYER = "https://relayer-staging.memory.walrus.xyz"
MAINNET_RELAYER = "https://relayer.memory.walrus.xyz"   # Foundation-hosted; relayer pays WAL/SUI


def _read(path_env: str):
    p = os.environ.get(path_env)
    if p and os.path.exists(p):
        with open(p) as fh:
            return fh.read().strip()
    return None


def event_text(event: dict) -> str:
    if event.get("op") == "remember":
        t = f"User's current {event['key']}: {event['value']}."
        return t + (" (replaces an earlier value)" if event.get("supersedes") else "")
    if event.get("op") == "forget":
        return f"User asked to forget memory #{event['id']}."
    return json.dumps(event, sort_keys=True)


class MemWalSink:
    """Same put() interface as the Walrus backends; get() is not supported."""

    def __init__(self, client, namespace: str = "statekeeper"):
        self.client, self.namespace = client, namespace
        self._loop = asyncio.new_event_loop()   # one loop so the SDK's HTTP client is reused

    def run(self, coro):
        return self._loop.run_until_complete(coro)

    def put(self, data: bytes) -> dict:
        text = event_text(json.loads(data))
        r = self.run(self.client.remember_and_wait(text, namespace=self.namespace))
        return {"blob_id": r.blob_id, "object_id": None, "cost": None}

    def get(self, blob_id: str) -> bytes:
        raise NotImplementedError("MemWal is recalled semantically; use SQLite or a Walrus snapshot")

    def recall(self, query: str, limit: int = 5) -> list[str]:
        r = self.run(self.client.recall(query, limit=limit, namespace=self.namespace))
        return [m.text for m in r.results]


class Fanout:
    """Write each event to several backends (e.g. Walrus blobs + MemWal); first blob id wins."""

    def __init__(self, *backends):
        self.backends = [b for b in backends if b]

    def put(self, data: bytes) -> dict:
        res = None
        for b in self.backends:
            try:
                r = b.put(data)
                res = res or r
            except Exception:
                pass
        if res is None:
            raise RuntimeError("all backends failed")
        return res

    def get(self, blob_id: str) -> bytes:
        for b in self.backends:
            try:
                return b.get(blob_id)
            except Exception:
                continue
        raise KeyError(blob_id)


def memwal_from_env():
    mode = os.environ.get("STATEKEEPER_MEMWAL", "off").lower()
    if mode == "mock":
        from memwal.mock import MemWalMock
        return MemWalSink(MemWalMock.create(namespace="statekeeper"))
    if mode == "staging":
        from memwal import MemWal
        key, acct = os.environ.get("MEMWAL_KEY"), os.environ.get("MEMWAL_ACCOUNT_ID")
        if not key or not acct:
            raise RuntimeError("STATEKEEPER_MEMWAL=staging needs MEMWAL_KEY and MEMWAL_ACCOUNT_ID")
        return MemWalSink(MemWal.create(key=key, account_id=acct, server_url=STAGING_RELAYER,
                                        namespace="statekeeper"))
    if mode == "live":
        # Credentials are read from files outside the repo; never printed or stored.
        from memwal import MemWal
        key, acct = _read("MEMWAL_KEY_FILE"), _read("MEMWAL_ACCOUNT_ID_FILE")
        if not key or not acct:
            raise RuntimeError("STATEKEEPER_MEMWAL=live needs MEMWAL_KEY_FILE and MEMWAL_ACCOUNT_ID_FILE")
        return MemWalSink(MemWal.create(key=key, account_id=acct,
                                        server_url=os.environ.get("MEMWAL_SERVER_URL", MAINNET_RELAYER),
                                        namespace=os.environ.get("MEMWAL_NAMESPACE", "statekeeper-demo")),
                          namespace=os.environ.get("MEMWAL_NAMESPACE", "statekeeper-demo"))
    return None
