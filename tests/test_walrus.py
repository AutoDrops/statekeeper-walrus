import os
import pytest
from statekeeper.memory import MemoryStore
from statekeeper.walrus import MockWalrus, WalrusHTTP


def test_events_get_blob_ids_and_snapshot_restores():
    w = MockWalrus(); s = MemoryStore(walrus=w)
    s.remember("home city", "Lviv", 1); s.remember("home city", "Kyiv", 2)
    f = s.remember("diet", "vegan", 3); s.forget(f.id)
    assert all(x.blob_id for x in s.all())
    assert len(w.blobs) == 4                      # 3 remembers + 1 forget
    s2 = MemoryStore.restore(s.snapshot(), w)
    assert s2.current("home city").value == "Kyiv"
    assert [x.value for x in s2.history("home city")] == ["Lviv", "Kyiv"]
    assert s2.current("diet") is None


def test_walrus_failure_does_not_break_local_memory():
    class Down:
        def put(self, d): raise OSError("offline")
    s = MemoryStore(walrus=Down())
    assert s.remember("job", "teacher").blob_id is None
    assert s.current("job").value == "teacher"


@pytest.mark.skipif(os.environ.get("WALRUS_LIVE") != "1", reason="set WALRUS_LIVE=1 for testnet")
def test_live_testnet_roundtrip():
    w = WalrusHTTP(); s = MemoryStore(walrus=w)
    s.remember("home city", "Lviv", 1); s.remember("home city", "Kyiv", 2)
    bid = s.snapshot()
    print("snapshot blob:", bid)
    s2 = MemoryStore.restore(bid, WalrusHTTP())
    assert s2.current("home city").value == "Kyiv"
