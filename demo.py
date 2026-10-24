"""Tiny CLI demo. Runs offline (mock) unless NEBIUS_API_KEY is set."""
from statekeeper.agent import Agent
from statekeeper.llm import make_llm
from statekeeper.memory import MemoryStore

agent = Agent(MemoryStore(), make_llm())
for msg in ["I live in Lviv and I'm vegetarian.", "My gym days are Monday and Thursday.",
            "Update: I moved to Kyiv.", "Where do I live and what do I eat?"]:
    r = agent.handle(msg)
    print(f"> {msg}\n  {r['reply']}\n  wrote={[(f['key'], f['value']) for f in r['written']]}")
print("\nMemory view:")
for f in agent.store.all():
    print(f"  #{f.id} {f.key} = {f.value} [{f.status}]" + (f" -> #{f.replaced_by}" if f.replaced_by else ""))
