"""Walrus storage backend for StateKeeper.

SQLite stays the fast local index; every memory event (remember / supersede /
forget) is also written as a JSON blob to Walrus, and the blob id is stored
next to the fact. A full snapshot can be published and later restored on any
machine from its blob id alone ("portable memory").

Default endpoints are the public Walrus *testnet* publisher/aggregator, which
need no wallet or key. Mainnet requires your own publisher (paid in WAL/SUI).
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from typing import Optional

TESTNET_PUBLISHER = "https://publisher.walrus-testnet.walrus.space"
TESTNET_AGGREGATOR = "https://aggregator.walrus-testnet.walrus.space"
UA = {"User-Agent": "statekeeper/0.2"}  # default urllib UA is rejected (HTTP 403)


class WalrusHTTP:
    """Minimal client for the Walrus HTTP API (PUT /v1/blobs, GET /v1/blobs/<id>)."""

    def __init__(self, publisher: Optional[str] = None, aggregator: Optional[str] = None,
                 epochs: int = 1, timeout: float = 60):
        self.publisher = (publisher or os.environ.get("WALRUS_PUBLISHER", TESTNET_PUBLISHER)).rstrip("/")
        self.aggregator = (aggregator or os.environ.get("WALRUS_AGGREGATOR", TESTNET_AGGREGATOR)).rstrip("/")
        self.epochs, self.timeout = epochs, timeout

    def put(self, data: bytes) -> dict:
        req = urllib.request.Request(f"{self.publisher}/v1/blobs?epochs={self.epochs}",
                                     data=data, method="PUT", headers=UA)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            info = json.loads(r.read())
        if "newlyCreated" in info:
            obj = info["newlyCreated"]["blobObject"]
            return {"blob_id": obj["blobId"], "object_id": obj["id"], "cost": info["newlyCreated"].get("cost")}
        if "alreadyCertified" in info:
            return {"blob_id": info["alreadyCertified"]["blobId"], "object_id": None, "cost": 0}
        raise RuntimeError(f"unexpected publisher response: {info}")

    def get(self, blob_id: str) -> bytes:
        req = urllib.request.Request(f"{self.aggregator}/v1/blobs/{blob_id}", headers=UA)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read()


class MockWalrus:
    """Offline stand-in: content-addressed dict, same interface."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    def put(self, data: bytes) -> dict:
        bid = hashlib.sha256(data).hexdigest()[:43]
        self.blobs[bid] = data
        return {"blob_id": bid, "object_id": None, "cost": 0}

    def get(self, blob_id: str) -> bytes:
        return self.blobs[blob_id]


def backend_from_env():
    """STATEKEEPER_WALRUS=off|mock|testnet (default off)."""
    mode = os.environ.get("STATEKEEPER_WALRUS", "off").lower()
    if mode == "mock":
        return MockWalrus()
    if mode in ("testnet", "http", "on"):
        return WalrusHTTP()
    return None
