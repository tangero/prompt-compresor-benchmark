#!/usr/bin/env bash
# Ověří každou úlohu před pilotem: na čistém snapshotu skryté testy padají
# a sada + typecheck projdou, po aplikaci referenčního řešení projde vše.
#
# Použití: scripts/check-tasks.sh <pracovní adresář> [úloha…]
# Proměnné: SOURCE_REPO (klon 3gpp-explorer), PNPM (výchozí "corepack pnpm@8.15.0").
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mkdir -p "$1" && cd "$1" && pwd); shift
export PNPM=${PNPM:-corepack pnpm@8.15.0}
tasks=("$@")
[ ${#tasks[@]} -eq 0 ] && tasks=(01-priority-queue 02-releases 03-version-decoder)

reference_patch() {
  if [ -f "$root/tasks/$1/reference.patch" ]; then echo "$root/tasks/$1/reference.patch"
  else echo "$root/tasks/$1/reference/reference.patch"; fi
}

expect() { # expect <verify.json> <hidden> <suite> <typecheck>
  python3 - "$@" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
want = dict(zip(['hidden_tests_pass', 'suite_pass', 'typecheck_pass'], [a == 'true' for a in sys.argv[2:5]]))
bad = {k: r[k] for k, v in want.items() if r[k] != v}
print('OK' if not bad else f'NEČEKANÉ: {bad}')
sys.exit(1 if bad else 0)
PY
}

status=0
for t in "${tasks[@]}"; do
  snap=$work/$t/snapshot
  rm -rf "$work/$t"
  "$root/scripts/make-snapshot.sh" "$root/tasks/$t" "$snap" || { status=1; continue; }
  (cd "$snap" && $PNPM install --frozen-lockfile > "$work/$t/install.log" 2>&1) || { echo "$t: pnpm install selhal"; status=1; continue; }

  echo "== $t: výchozí stav"
  "$root/tasks/$t/verify.sh" "$snap" "$work/$t/base"
  expect "$work/$t/base/verify.json" false true true || status=1

  echo "== $t: referenční řešení"
  (cd "$snap" && git apply "$(reference_patch "$t")") || { echo "$t: patch nejde aplikovat"; status=1; continue; }
  "$root/tasks/$t/verify.sh" "$snap" "$work/$t/reference"
  expect "$work/$t/reference/verify.json" true true true || status=1
done
exit $status
