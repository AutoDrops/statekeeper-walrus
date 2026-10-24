#!/bin/bash
# Leak check. Exit 1 on any private-term hit or secret-looking string.
cd "$(dirname "$0")/.."
PAT_FILE="${LEAK_PATTERNS_FILE:-/workspace/free-api/private/leak_patterns.txt}"  # private list, kept outside the repo
[ -s "$PAT_FILE" ] || { echo "LEAK CHECK: pattern file missing"; exit 2; }
PAT=$(cat "$PAT_FILE")
SECRET='sk-[A-Za-z0-9]{16,}|NEBIUS_API_KEY=[^.\s]{8,}|api_key="[^"]{8,}"'
FILES=$(find . -type f ! -path './.venv/*' ! -path './.git/*' ! -path '*/__pycache__/*' ! -path './tools/leak_check.sh' ! -name '*.db')
echo "Scanned files:"; echo "$FILES"
if grep -n -i -E "$PAT" $FILES; then echo "LEAK CHECK: CORE TERMS FOUND"; exit 1; fi
if grep -n -E "$SECRET" $FILES; then echo "LEAK CHECK: SECRET-LIKE STRING FOUND"; exit 1; fi
echo "LEAK CHECK: 0 hits (patterns)"
# Also fail if any local free-tier key value appears in the repo (value is never printed).
for KEYFILE in ${LEAK_KEY_DIR:-/workspace/free-api/keys}/*; do
if [ -s "$KEYFILE" ] && grep -rqF -f "$KEYFILE" --exclude-dir=.venv --exclude-dir=.git --exclude-dir=__pycache__ . ; then
  echo "LEAK CHECK: KEY VALUE FOUND ($(basename $KEYFILE))"; exit 1; fi; done
echo "LEAK CHECK: key-file scan clean"
