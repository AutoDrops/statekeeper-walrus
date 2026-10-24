# StateKeeper

A personal assistant that remembers **what is true now**. It keeps a small, persistent,
source-linked fact store. When you change something ("I moved to Kyiv"), the old value is
marked *superseded*, not silently overwritten. You can see and edit everything it remembers.

Built for the Nebius × NVIDIA Global AI Hackathon (Personal AI track).

## Features
- **Persistent memory** (SQLite): facts as `key → value`, each linked to the turn it came from.
- **Update / supersede handling**: a new value for an existing key retires the old one and links
  `old → new`, so full history is kept.
- **Retrieval**: only the facts relevant to the current message go into the prompt, not the whole chat.
- **Transparent memory view**: the web UI shows active and superseded facts, and you can forget any fact.
- **Offline mock mode**: runs and passes tests without any API key.

## Setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q                      # offline, no key needed
python demo.py                 # CLI demo (mock unless a key is set)
export NEBIUS_API_KEY=...      # from Nebius Token Factory
export STATEKEEPER_MODEL=...   # optional, any Nemotron model id available in Token Factory
uvicorn statekeeper.app:app --port 7860   # open http://localhost:7860
```
Environment variables: `NEBIUS_API_KEY`, `STATEKEEPER_MODEL` (default
`nvidia/Llama-3_1-Nemotron-Ultra-253B-v1`), `NEBIUS_BASE_URL` (default
`https://api.tokenfactory.nebius.com/v1/`), `STATEKEEPER_DB` (default `statekeeper.db`),
`STATEKEEPER_MOCK=1` to force offline mode.

Deploy: the included `Dockerfile` runs on free tiers such as Hugging Face Spaces (Docker SDK) or Render.

## How we use Nemotron and Token Factory
Every chat turn makes two runtime calls to an NVIDIA Nemotron model served by **Nebius Token
Factory** through its OpenAI-compatible API (`statekeeper/llm.py`):
1. **Fact noting** (temperature 0, JSON output): Nemotron reads the user message and returns
   durable personal facts with stable keys, reusing a key when the user changes something.
   The store then decides whether the fact is new, unchanged, or supersedes an older value.
2. **Answering**: Nemotron answers using only the retrieved current facts, and is told to say
   so when memory does not cover the question rather than guess.

The model id is configurable, so any Nemotron model listed in Token Factory can be used.

## Prior research note
The author previously ran closed research on agent memory (ASM). Those results are **prior,
preliminary, closed research** and are **not** results of this code. On the public LongMemEval
oracle subset that approach scored below full-history prompting (49% vs 66%). StateKeeper's
memory layer was written from scratch for this hackathon and shares no code with that work.
Public evaluation data and scorer: https://github.com/AutoDrops/asm-eval

## Limitations
- Retrieval is keyword overlap plus a small synonym map; no embeddings yet.
- Mock mode uses simple regex patterns and is only for tests and demos.
- Single user, single local database.

## License
MIT

## Walrus storage (Total Recall branch)

`STATEKEEPER_WALRUS=off|mock|testnet` (default `off`). With `testnet`, every memory
event (remember / supersede / forget) is also written as a JSON blob through the public
Walrus testnet publisher, and its blob id is saved next to the fact in SQLite.
`MemoryStore.snapshot()` publishes the full history; `MemoryStore.restore(blob_id, backend)`
rebuilds it on another machine. Override endpoints with `WALRUS_PUBLISHER` / `WALRUS_AGGREGATOR`.

Live check: `WALRUS_LIVE=1 pytest -s tests/test_walrus.py -k live`.

Not done yet: Walrus Memory (MemWal) SDK integration and mainnet writes, Tatum Sui RPC.
These need a Sui wallet, a MemWal account and a Tatum API key.

### Walrus Memory (MemWal) and Tatum
- `STATEKEEPER_MEMWAL=off|mock|staging`: mirrors each memory event into Walrus Memory
  (`mock` = SDK's offline MemWalMock; `staging` = testnet relayer, needs `MEMWAL_KEY`,
  `MEMWAL_ACCOUNT_ID` from staging.memory.walrus.xyz). Can run together with `STATEKEEPER_WALRUS`.
- `TATUM_API_KEY` or `TATUM_KEY_FILE` (free tier, key kept outside the repo), `TATUM_SUI_NETWORK=testnet`: Sui GraphQL via the Tatum gateway (testnet gateway is GraphQL-only);
  live test: `TATUM_LIVE=1 pytest -s tests/test_tatum_memwal.py -k live`;
  `GET /api/onchain/<object_id>` shows whether a Walrus Blob object exists onchain.
  Without a key, a mock is used.
- This branch is testnet-only; mainnet is not wired.
