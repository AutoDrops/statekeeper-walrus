import os
os.environ["STATEKEEPER_NO_AUTOAPP"] = "1"
from fastapi.testclient import TestClient
from statekeeper.memory import MemoryStore
from statekeeper.agent import Agent
from statekeeper.llm import MockLLM
from statekeeper.app import create_app


def test_supersede_keeps_history():
    s = MemoryStore()
    a = s.remember("Home City", "Lviv", 1)
    b = s.remember("home city", "Kyiv", 2)
    assert s.current("home city").value == "Kyiv"
    old = s.get(a.id)
    assert old.status == "superseded" and old.replaced_by == b.id
    assert [f.value for f in s.history("home city")] == ["Lviv", "Kyiv"]


def test_same_value_is_noop():
    s = MemoryStore()
    a = s.remember("diet", "vegan"); b = s.remember("diet", "Vegan")
    assert a.id == b.id and len(s.all()) == 1


def test_forget_and_search():
    s = MemoryStore()
    f = s.remember("gym days", "Monday and Thursday")
    s.remember("diet", "vegetarian")
    assert s.search("which days do I go to the gym?")[0].id == f.id
    assert s.forget(f.id) and s.search("gym days") == []


def test_persistence(tmp_path):
    p = str(tmp_path / "m.db")
    MemoryStore(p).remember("job", "teacher")
    assert MemoryStore(p).current("job").value == "teacher"


def test_agent_update_flow():
    s = MemoryStore(); ag = Agent(s, MockLLM())
    ag.handle("I live in Lviv.")
    ag.handle("I moved to Kyiv last week.")
    r = ag.handle("Which city do I live in?")
    assert "Kyiv" in r["reply"] and "Lviv" not in r["reply"]


def test_api(tmp_path):
    c = TestClient(create_app(str(tmp_path / "a.db"), MockLLM()))
    assert c.post("/api/chat", json={"message": "My favourite tea is sencha."}).status_code == 200
    facts = c.get("/api/memory").json()["facts"]
    assert facts[0]["key"] == "favourite tea"
    assert c.delete(f"/api/memory/{facts[0]['id']}").json()["ok"]
    assert c.get("/api/memory?include_history=false").json()["facts"] == []
    assert c.get("/").status_code == 200
