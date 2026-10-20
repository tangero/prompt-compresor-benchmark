#!/usr/bin/env python3
"""Plán běhů: úlohy × konfigurace × opakování, náhodně zamíchané s pevným seedem.

Nespouštět po blocích konfigurací: prompt cache sdílí začátek promptu mezi běhy
a zvýhodnila by pozdější běhy téže konfigurace.

  runner/plan.py --seed 20261019 --out plan.json
  runner/plan.py --seed 7 --tasks 01-priority-queue --configs baseline rtk --reps 2 --out pilot.json
"""
import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALL_TASKS = sorted(p.name for p in (ROOT / 'tasks').iterdir() if p.is_dir())
MAIN_CONFIGS = ['baseline', 'caveman', 'ponytail', 'rtk', 'context-mode', 'headroom']


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--tasks', nargs='+', default=ALL_TASKS)
    ap.add_argument('--configs', nargs='+', default=MAIN_CONFIGS)
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--prefix', default='r', help='předpona run_id (pilot: p)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    runs = [
        {'task': t, 'config': c, 'repetition': r}
        for t in a.tasks for c in a.configs for r in range(1, a.reps + 1)
    ]
    random.Random(a.seed).shuffle(runs)
    for i, run in enumerate(runs):
        run['seed_position'] = i
        run['run_id'] = f"{a.prefix}{i:03d}-{run['task'][:2]}-{run['config']}-{run['repetition']}"
    plan = {'seed': a.seed, 'tasks': a.tasks, 'configs': a.configs, 'reps': a.reps, 'runs': runs}
    Path(a.out).write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(runs)} běhů → {a.out}')


if __name__ == '__main__':
    main()
