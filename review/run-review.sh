#!/usr/bin/env bash
# Jedno Codex review: review/run-review.sh <task prompt.md> <diff.patch> <výstup.json>
# Codex dostane izolovaný adresář s náhodným jménem: zadání, diff, rubriku. Nic víc.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
dir=$(mktemp -d "${TMPDIR:-/tmp}/review-XXXXXXXX")
trap 'rm -rf "$dir"' EXIT
cp "$1" "$dir/task.md"; cp "$2" "$dir/diff.patch"; cp "$here/rubric.json" "$dir/rubric.json"
codex exec -m "${CODEX_MODEL:-gpt-6.1-sol}" -c model_reasoning_effort="${CODEX_EFFORT:-medium}" \
  -s read-only -C "$dir" --skip-git-repo-check --ephemeral --ignore-rules \
  --output-schema "$here/schema.json" -o "$3" - < "$here/prompt.md" > "$3.log" 2>&1
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$3"
