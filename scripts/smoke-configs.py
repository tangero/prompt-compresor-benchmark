#!/usr/bin/env python3
"""Levná kontrola aktivace všech konfigurací před během (cca 0,2 USD na konfiguraci).

  scripts/smoke-configs.py [--task 01] [config…]

Pro každou konfiguraci: kontejner jako v runneru, krátký prompt s jedním příkazem
v Bashi, stejná kontrola aktivace jako v runner/run.py. Výsledky do build/smoke/.
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'runner'))
import run  # noqa: E402
from metrics import parse_stream  # noqa: E402

PROMPT = 'Run `git status --short | head -5` and `ls apps` with the Bash tool, then reply with one short sentence.'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', default='01')
    ap.add_argument('configs', nargs='*', default=run.__dict__.get('MAIN_CONFIGS') or
                    ['baseline', 'caveman', 'ponytail', 'rtk', 'context-mode', 'headroom'])
    a = ap.parse_args()
    run.ensure_gateway()
    out_root = ROOT / 'build' / 'smoke'
    ok_all = True
    for cfg in a.configs:
        out = out_root / cfg
        out.mkdir(parents=True, exist_ok=True)
        name = run.start_container(f'smoke-{cfg}', f'cc-bench-{a.task}-{cfg}', cfg)
        try:
            cmd = (f'claude -p --model {run.MODEL} --effort {run.EFFORT} --max-turns 6 --output-format stream-json '
                   f'--verbose --permission-mode bypassPermissions {shlex.quote(PROMPT)}')
            with open(out / 'stream.jsonl', 'w') as f:
                subprocess.run(['docker', 'exec', '-u', 'node', '-w', '/work', name, 'bash', '-c', cmd],
                               stdout=f, stderr=subprocess.PIPE, text=True, timeout=600)
            m = parse_stream(out / 'stream.jsonl')
            stats = run.tool_stats(name, cfg, out)
            active, note = run.check_activation(cfg, m, stats)
            res = m['result']
            ok_all &= active and res.get('subtype') == 'success'
            print(f"{cfg:13} {'OK ' if active else 'CHYBA'} {res.get('subtype')} {res.get('total_cost_usd')} USD "
                  f"tools={m['tool_uses']} | {note}")
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
