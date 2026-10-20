#!/usr/bin/env python3
"""Doplní Codex review běhům, kde selhalo (např. limit Codexu během noci).

  runner/rereview.py [results.jsonl]

Prochází platné běhy, kde nejsou dvě úspěšná hodnocení, spustí review nad uloženým
runs/<run_id>/attempt-N/review.diff a přepíše řádek v results.jsonl (záloha .bak).
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else run.RESULTS)
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    changed = 0
    for r in rows:
        if r['status'] == 'invalid':
            continue
        good = [s for s in r.get('review_scores') or [] if 'error' not in s]
        out = run.RUNS / r['run_id'] / f"attempt-{r.get('attempt', 1)}"
        if len(good) >= 2 or not (out / 'review.diff').exists():
            continue
        run.log(f"review {r['run_id']}")
        r['review_scores'], r['review_disagreement'] = run.review(r['task'], out)
        changed += 1
    if changed:
        shutil.copy(path, path.with_suffix('.jsonl.bak'))
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    run.log(f'doplněno {changed} review')


if __name__ == '__main__':
    main()
