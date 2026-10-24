#!/bin/bash
# Adapted ASM leak check for StateKeeper. Exit 1 on any core-term hit or secret-looking string.
cd "$(dirname "$0")/.."
PAT='extract_v[0-9]|extractor_v[0-9]|extractor\.py|build_memory|ContextBuilder|context_builder|semantic_state|SemanticState|event_store|EventStore|significance(_v2)?\.py|Significance Controller|Semantic Guard|guard\.py|ASM-CL|asmcl|asm_lab|assert_fact|update_fact|refute_fact|quote_only|set_goal|add_constraint|lift_constraint|propose_decision|discuss_decision|accept_decision|cancel_decision|supersede_decision|note_intent|set_task_status|add_cause|derive_conclusion|mark_source_disputed|source_event_id|trigger_event_id|экстрактор|Ты — |Паллетрон|Контейнерис|Термобоксель|longgen|hardgen|frozen-closed|sha256_frozen|extractor_v4_system|raw layer|5 events|сырой|by_group_micro|grader_v[0-9]|OPENROUTER_API_KEY|sk-or-'
# Change vs original: generic 'api[_-]?key' removed (the app must read NEBIUS_API_KEY);
# replaced by a check for actual secret values below.
SECRET='sk-[A-Za-z0-9]{16,}|NEBIUS_API_KEY=[^.\s]{8,}|api_key="[^"]{8,}"'
FILES=$(find . -type f ! -path './.venv/*' ! -path './.git/*' ! -path '*/__pycache__/*' ! -path './tools/leak_check.sh' ! -name '*.db')
echo "Scanned files:"; echo "$FILES"
if grep -n -i -E "$PAT" $FILES; then echo "LEAK CHECK: CORE TERMS FOUND"; exit 1; fi
if grep -n -E "$SECRET" $FILES; then echo "LEAK CHECK: SECRET-LIKE STRING FOUND"; exit 1; fi
echo "LEAK CHECK: 0 hits (patterns)"
# Also fail if any local free-tier key value appears in the repo (value is never printed).
for KEYFILE in /workspace/free-api/keys/tatum_testnet.key /workspace/free-api/keys/memwal_key.key /workspace/free-api/keys/memwal_account_id.txt; do
if [ -s "$KEYFILE" ] && grep -rqF -f "$KEYFILE" --exclude-dir=.venv --exclude-dir=.git --exclude-dir=__pycache__ . ; then
  echo "LEAK CHECK: KEY VALUE FOUND ($(basename $KEYFILE))"; exit 1; fi; done
echo "LEAK CHECK: key-file scan clean"
