"""Write exactly 10 synthetic demo memories via the hosted MemWal relayer, then recall.
Run: STATEKEEPER_MEMWAL=live MEMWAL_KEY_FILE=... MEMWAL_ACCOUNT_ID_FILE=... python tools/memwal_live_demo.py
Prints only blob ids and recalled text, never credentials."""
import asyncio, json, sys
sys.path.insert(0, ".")
from statekeeper.memory import MemoryStore
from statekeeper.memwal_sink import memwal_from_env

FACTS = [("demo city", "Lviv"), ("demo city", "Kyiv"), ("demo diet", "vegetarian"),
         ("demo gym days", "Monday and Thursday"), ("demo coffee", "flat white"),
         ("demo pet", "a cat named Pixel"), ("demo language", "learning Spanish"),
         ("demo sport", "running 5 km"), ("demo budget", "200 per month for groceries"),
         ("demo reminder", "water plants on Sunday")]

sink = memwal_from_env()
health = sink.run(sink.client.health())
print("relayer health:", getattr(health, "status", health))
s = MemoryStore(walrus=sink)
written = 0
for i, (k, v) in enumerate(FACTS):
    f = s.remember(k, v, i)
    written += bool(f.blob_id)
    print(f"{i+1:2d} {k} = {v} -> blob {f.blob_id}")
print("written with blob id:", written, "/", len(FACTS))
for q in ["Which city does the demo user live in now?", "What pet does the demo user have?"]:
    print("recall:", q, "->", sink.recall(q, limit=3))
