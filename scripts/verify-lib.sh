# Společné funkce pro tasks/*/verify.sh. Načítá se přes `source`.
#
# Volání verify.sh: verify.sh <adresář snapshotu> <výstupní adresář>
# Do výstupního adresáře zapíše logy jednotlivých kroků a verify.json.

set -uo pipefail

WORK=$(cd "$1" && pwd)
OUT=$(mkdir -p "$2" && cd "$2" && pwd)
TASK_DIR=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
STEP_TIMEOUT=${STEP_TIMEOUT:-900}
TIMEOUT_CMD=()
command -v timeout >/dev/null && TIMEOUT_CMD=(timeout "$STEP_TIMEOUT")

# step <název> <příkaz…>: spustí příkaz v $WORK, log do $OUT/<název>.log,
# výsledek (true/false) do proměnné R_<název>.
step() {
  local name=$1; shift
  local started=$SECONDS
  (cd "$WORK" && ${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"} "$@") > "$OUT/$name.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then printf -v "R_$name" true; else printf -v "R_$name" false; fi
  echo "[$name] rc=$rc $((SECONDS - started))s"
}

# copy_hidden <soubor v hidden-tests/> <cílová cesta ve snapshotu>
copy_hidden() {
  mkdir -p "$(dirname "$WORK/$2")"
  cp "$TASK_DIR/hidden-tests/$1" "$WORK/$2"
}

# Změnil nebo smazal agent existující testovací soubory? (jen informace do dat)
# TESTS_EXPECTED_TO_CHANGE: mezerou oddělené cesty, které má agent podle zadání rozšířit.
TESTS_EXPECTED_TO_CHANGE=${TESTS_EXPECTED_TO_CHANGE:-}
tests_touched() {
  (cd "$WORK" && git diff --name-status base -- '*.test.ts' '*.test.tsx' '*.spec.ts' \
    | awk -v skip=" $TESTS_EXPECTED_TO_CHANGE " '$1 == "D" || ($1 != "A" && index(skip, " " $2 " ") == 0)' \
    | wc -l | tr -d ' ')
}

write_result() {
  local hidden=${R_hidden:-false} suite=${R_suite:-false} tc=${R_typecheck:-false}
  cat > "$OUT/verify.json" <<JSON
{"hidden_tests_pass": $hidden, "suite_pass": $suite, "typecheck_pass": $tc, "existing_tests_modified": $(tests_touched)}
JSON
  cat "$OUT/verify.json"
}

PNPM=${PNPM:-pnpm}
