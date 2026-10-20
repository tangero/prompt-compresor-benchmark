#!/usr/bin/env bash
# Noční běh bez dozoru: pojistka → plný plán → analýza.
#
#   scripts/night.sh [plan.json]
#
# 1. Pojistka: první běh baseline úlohy 02 a 03 z plánu (regulérní běhy, počítají se).
#    Pokračuje se jen tehdy, když oba doběhly s platným stavem, verify zapsal výsledky
#    a review vrátilo skóre. Jinak stop, nic dalšího se neutratí.
# 2. Plný plán (run.py přeskočí hotové běhy, po pádu se znovu spustí, max. 3×).
# 3. Analýza do analysis/out.
# Stav průběžně v build/NIGHT-STATUS.md, log v build/night.log.
# Mac nesmí usnout: celý běh drží caffeinate.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
plan=${1:-plan.json}
log=build/night.log
status=build/NIGHT-STATUS.md
mkdir -p build

say() { echo "[$(date '+%F %T')] $*" | tee -a "$log"; }
state() { printf '# Noční běh\n\nAktualizováno: %s\n\n%s\n' "$(date '+%F %T')" "$*" > "$status"; say "$*"; }

if [ -z "${CAFFEINATED:-}" ] && command -v caffeinate >/dev/null; then
  CAFFEINATED=1 exec caffeinate -dimsu "$0" "$@"
fi

docker info >/dev/null 2>&1 || { state "STOP: Docker neběží."; exit 1; }
for img in $(python3 -c "import json;p=json.load(open('$plan'));print(' '.join(sorted({'cc-bench-%s-%s'%(r['task'][:2],r['config']) for r in p['runs']})))") cc-bench-gateway; do
  docker image inspect "$img" >/dev/null 2>&1 || { state "STOP: chybí obraz $img (scripts/build-images.sh)."; exit 1; }
done

# ---- 1. pojistka
gate=$(python3 - "$plan" <<'PY'
import json, sys
runs = json.load(open(sys.argv[1]))['runs']
pick = [next(r['run_id'] for r in runs if r['task'].startswith(t) and r['config'] == 'baseline') for t in ('02', '03')]
print(' '.join(pick))
PY
)
state "Pojistka: $gate"
python3 runner/run.py "$plan" --only $gate >> "$log" 2>&1
if ! python3 - $gate <<'PY'
import json, sys
want = set(sys.argv[1:])
rows = [json.loads(l) for l in open('results.jsonl') if l.strip()]
ok = {r['run_id'] for r in rows if r['run_id'] in want and r['status'] != 'invalid'
      and 'hidden_tests_pass' in r and any('error' not in s for s in r.get('review_scores') or [])}
missing = want - ok
for r in rows:
    if r['run_id'] in want:
        print(r['run_id'], r['status'], r.get('cost_usd'), r.get('hidden_tests_pass'), r.get('invalid_reason'))
sys.exit(1 if missing else 0)
PY
then
  state "STOP po pojistce: kontrolní běhy úloh 02/03 neprošly harnessem. Podrobnosti v $log a results.jsonl."
  exit 1
fi
state "Pojistka prošla, spouštím plný plán."

# ---- 2. plný plán
for attempt in 1 2 3; do
  python3 runner/run.py "$plan" >> "$log" 2>&1 && break
  say "run.py skončil chybou (pokus $attempt), znovu za 60 s"
  sleep 60
done
summary=$(python3 - "$plan" <<'PY'
import json, sys
from collections import Counter
plan = json.load(open(sys.argv[1]))['runs']
rows = [json.loads(l) for l in open('results.jsonl') if l.strip()]
valid = {r['run_id'] for r in rows if r['status'] != 'invalid'}
st = Counter(r['status'] for r in rows)
print(f"hotovo {len(valid & {r['run_id'] for r in plan})}/{len(plan)} běhů, stavy {dict(st)}, "
      f"utraceno {sum(r.get('cost_usd') or 0 for r in rows):.2f} USD")
PY
)

# ---- 3. doplnění review, která v noci selhala, a analýza
python3 runner/rereview.py results.jsonl >> "$log" 2>&1
if command -v uv >/dev/null; then
  uv run -q --with matplotlib analysis/analyze.py results.jsonl --out analysis/out >> "$log" 2>&1
else
  python3 analysis/analyze.py results.jsonl --out analysis/out >> "$log" 2>&1
fi
state "HOTOVO: $summary. Souhrn: analysis/out/summary.md"
