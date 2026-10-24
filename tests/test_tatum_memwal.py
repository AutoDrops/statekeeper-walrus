import time
import os
import pytest
from memwal.mock import MemWalMock
from statekeeper.memory import MemoryStore
from statekeeper.memwal_sink import MemWalSink, Fanout, event_text
from statekeeper.tatum import MockTatumSui, TatumSui, tatum_from_env
from statekeeper.walrus import MockWalrus


def test_memwal_mock_mirrors_events_and_recalls():
    sink = MemWalSink(MemWalMock.create(namespace="statekeeper"))
    s = MemoryStore(walrus=sink)
    for i, (k, v) in enumerate([("home city", "Lviv"), ("home city", "Kyiv"), ("diet", "vegan"),
                                ("gym days", "Mon Thu"), ("coffee", "flat white"), ("pet", "cat"),
                                ("job", "teacher"), ("language", "Ukrainian"), ("sport", "running"),
                                ("budget", "500 per month")]):
        s.remember(k, v, i)
    assert all(f.blob_id for f in s.all())          # 10 memories, each with a blob id
    hits = sink.recall("home city Kyiv")
    assert any("Kyiv" in h for h in hits)


def test_event_text():
    assert event_text({"op": "remember", "key": "home city", "value": "Kyiv", "supersedes": 1}) \
        == "User's current home city: Kyiv. (replaces an earlier value)"


def test_fanout_survives_one_backend_failure():
    class Down:
        def put(self, d): raise OSError
        def get(self, b): raise OSError
    w = MockWalrus(); s = MemoryStore(walrus=Fanout(Down(), w))
    f = s.remember("job", "teacher")
    assert f.blob_id in w.blobs


def test_tatum_mock_when_no_key(monkeypatch):
    monkeypatch.delenv("TATUM_API_KEY", raising=False)
    t = tatum_from_env()
    assert isinstance(t, MockTatumSui) and t.object_status("0x1")["exists"] is False
    assert MockTatumSui({"0xab": "walrus::blob::Blob"}).object_status("0xab")["exists"]


def _load_key():
    """TATUM_API_KEY from env, else from the local key file (never printed)."""
    k = os.environ.get("TATUM_API_KEY")
    f = os.environ.get("TATUM_KEY_FILE", "/workspace/free-api/keys/tatum_testnet.key")
    if not k and os.path.exists(f):
        k = open(f).read().strip()
    return k


@pytest.mark.skipif(os.environ.get("TATUM_LIVE") != "1", reason="set TATUM_LIVE=1 (free testnet key)")
def test_tatum_live_testnet_reads_walrus_blob_object():
    from statekeeper.walrus import WalrusHTTP
    t = TatumSui(_load_key(), "testnet")
    assert t.checkpoint() > 0
    obj = WalrusHTTP().put(f'{{"app":"statekeeper","op":"tatum-live-check","t":{time.time()}}}'.encode())["object_id"]
    st = t.object_status(obj)
    print("walrus blob object:", obj, st["type"])
    assert st["exists"] and st["type"].endswith("::blob::Blob")
