"""Tatum Sui RPC client (free tier). Reads onchain status of Walrus blob objects
and wallet balances. Key from env TATUM_API_KEY; without it, a mock is used.

TATUM_SUI_NETWORK=testnet (default) -> https://sui-testnet.gateway.tatum.io/graphql
Mainnet is intentionally not the default in this branch.
"""
from __future__ import annotations

import json
import os
import urllib.request

# Verified 24.10.2026 via the gateway's /_methods: sui-testnet exposes only GraphQL at /graphql
# (JSON-RPC on the testnet gateway returns 404). Mainnet also lists JSON-RPC; GraphQL is used for both.
GATEWAYS = {"testnet": "https://sui-testnet.gateway.tatum.io/graphql",
            "mainnet": "https://sui-mainnet.gateway.tatum.io/graphql"}

_OBJ = ("query($id: SuiAddress!) { object(address: $id) { version "
        "asMoveObject { contents { type { repr } } } } }")
_BAL = "query($a: SuiAddress!) { address(address: $a) { balance { totalBalance } } }"


class TatumSui:
    def __init__(self, api_key: str, network: str = "testnet", timeout: float = 20):
        self.url, self._key, self.timeout = GATEWAYS[network], api_key, timeout

    def __repr__(self):  # never expose the key
        return f"TatumSui(url={self.url!r})"

    def query(self, query: str, variables: dict | None = None) -> dict:
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "content-type": "application/json", "x-api-key": self._key,
            "User-Agent": "statekeeper/0.2"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read())
        if out.get("errors"):
            raise RuntimeError(out["errors"])
        return out["data"]

    def checkpoint(self) -> int:
        return int(self.query("{ checkpoint { sequenceNumber } }")["checkpoint"]["sequenceNumber"])

    def object_status(self, object_id: str) -> dict:
        """Return {exists, type, version} for a Sui object, e.g. a Walrus Blob object."""
        o = self.query(_OBJ, {"id": object_id}).get("object")
        if not o:
            return {"exists": False, "type": None, "version": None}
        t = ((o.get("asMoveObject") or {}).get("contents") or {}).get("type") or {}
        return {"exists": True, "type": t.get("repr"), "version": o.get("version")}

    def balance(self, address: str) -> int:
        a = self.query(_BAL, {"a": address}).get("address") or {}
        return int((a.get("balance") or {}).get("totalBalance") or 0)


class MockTatumSui:
    """Offline stand-in used when TATUM_API_KEY is absent."""

    def __init__(self, known: dict | None = None):
        self.known = known or {}

    def object_status(self, object_id: str) -> dict:
        t = self.known.get(object_id)
        return {"exists": t is not None, "type": t, "version": "1" if t else None}

    def balance(self, address: str) -> int:
        return 0


def tatum_from_env():
    key = os.environ.get("TATUM_API_KEY")
    kf = os.environ.get("TATUM_KEY_FILE")          # e.g. a mode-600 file outside the repo
    if not key and kf and os.path.exists(kf):
        with open(kf) as fh:
            key = fh.read().strip()
    if not key:
        return MockTatumSui()
    return TatumSui(key, os.environ.get("TATUM_SUI_NETWORK", "testnet"))
