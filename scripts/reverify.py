#!/usr/bin/env python3
"""Znovu ověří uložené diffy běhů v obrazu s unzip (bez agenta, bez sítě).

  scripts/reverify.py [--task 02] [--jobs 3]

Na čistý snapshot úlohy aplikuje runs/<run_id>/attempt-N/diff.patch, spustí verify.sh
a výsledek zapíše do runs/<run_id>/attempt-N/reverify/ a do results.jsonl jako pole
reverify_* (původní hodnoty zůstávají, záloha .jsonl.bak).
"""
import argparse
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'results.jsonl'


def sh(*a, **kw):
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


IPC_FLAKE = 'Unable to deserialize cloned data'


def one(r: dict, image: str, tries: int = 3) -> dict:
    """Opakuje ověření, jen když sada padla na chybě IPC spouštěče testů Node (ne na řešení)."""
    for i in range(1, tries + 1):
        res = one_try(r, image)
        log = ROOT / 'runs' / r['run_id'] / f"attempt-{r.get('attempt', 1)}" / 'reverify' / 'suite.log'
        flake = log.exists() and IPC_FLAKE in log.read_text(errors='replace')
        if res.get('reverify_suite_pass') is not False or not flake:
            break
    res['reverify_tries'] = i
    return res


def one_try(r: dict, image: str) -> dict:
    out = ROOT / 'runs' / r['run_id'] / f"attempt-{r.get('attempt', 1)}"
    dest = out / 'reverify'
    shutil.rmtree(dest, ignore_errors=True)
    name = f"reverify-{r['run_id']}"
    sh('docker', 'rm', '-f', name)
    sh('docker', 'run', '-d', '--name', name, '--network', 'none', '--memory', '6g', image, 'sleep', 'infinity')
    try:
        sh('docker', 'exec', '-u', 'root', name, 'mkdir', '-p', '/bench/tasks', '/bench/scripts')
        sh('docker', 'cp', str(out / 'diff.patch'), f'{name}:/bench/diff.patch')
        sh('docker', 'cp', str(ROOT / 'tasks' / r['task']), f"{name}:/bench/tasks/{r['task']}")
        sh('docker', 'cp', str(ROOT / 'scripts' / 'verify-lib.sh'), f'{name}:/bench/scripts/verify-lib.sh')
        sh('docker', 'exec', '-u', 'root', name, 'chown', '-R', 'node:node', '/bench')
        ap = sh('docker', 'exec', '-u', 'node', '-w', '/work', name, 'bash', '-c',
                'test ! -s /bench/diff.patch || git apply --whitespace=nowarn /bench/diff.patch')
        if ap.returncode:
            return {'reverify_error': 'git apply: ' + ap.stderr[-300:]}
        sh('docker', 'exec', '-u', 'node', '-w', '/work', name, 'bash', '-c',
           f"PNPM=pnpm STEP_TIMEOUT=1200 bash /bench/tasks/{r['task']}/verify.sh /work /bench/verify", timeout=4000)
        sh('docker', 'cp', f'{name}:/bench/verify', str(dest))
        v = json.loads((dest / 'verify.json').read_text())
        return {f'reverify_{k}': v[k] for k in ('hidden_tests_pass', 'suite_pass', 'typecheck_pass')}
    except Exception as e:  # noqa: BLE001
        return {'reverify_error': str(e)[-300:]}
    finally:
        sh('docker', 'rm', '-f', name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', default='02')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--failed-only', action='store_true',
                    help='jen běhy, kde sada padla (spouštěč testů Node občas padá na IPC chybě při zátěži)')
    a = ap.parse_args()
    rows = [json.loads(x) for x in RESULTS.read_text().splitlines() if x.strip()]
    todo = [r for r in rows if r['task'].startswith(a.task) and r['status'] != 'invalid'
            and not (a.failed_only and r.get('reverify_suite_pass'))]
    task = todo[0]['task']
    image = f'cc-bench-reverify-{a.task}'
    b = sh('docker', 'build', '-q', '-t', image, '--build-arg', f'TASK_IMAGE=cc-bench-task-{a.task}', str(ROOT / 'docker' / 'reverify'))
    if b.returncode:
        raise SystemExit(b.stderr)
    if a.failed_only:
        return run_all(todo, rows, image, a.jobs)
    # kontrola prostředí: referenční řešení musí projít celou sadou
    ref = ROOT / 'tasks' / task / 'reference' / 'reference.patch'
    if not ref.exists():
        ref = ROOT / 'tasks' / task / 'reference.patch'
    tmp = ROOT / 'runs' / f'_reference-{a.task}' / 'attempt-1'
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref, tmp / 'diff.patch')
    res = one({'run_id': f'_reference-{a.task}', 'attempt': 1, 'task': task}, image)
    print('reference', res, flush=True)
    if not res.get('reverify_suite_pass'):
        raise SystemExit('referenční řešení v obrazu neprošlo, prostředí není v pořádku')
    run_all(todo, rows, image, a.jobs)


def run_all(todo, rows, image, jobs):
    with ThreadPoolExecutor(jobs) as ex:
        for r, res in zip(todo, ex.map(lambda r: one(r, image), todo)):
            r['reverify_attempts'] = r.get('reverify_attempts', 0) + 1
            r.update(res)
            print(r['run_id'], res, flush=True)
    # results.jsonl mohl mezitím doplnit runner: přepíše se jen pole reverify_* u známých run_id
    current = [json.loads(x) for x in RESULTS.read_text().splitlines() if x.strip()]
    upd = {r['run_id']: {k: v for k, v in r.items() if k.startswith('reverify_')} for r in rows}
    for r in current:
        r.update(upd.get(r['run_id'], {}))
    shutil.copy(RESULTS, RESULTS.with_suffix('.jsonl.bak'))
    RESULTS.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in current))


if __name__ == '__main__':
    main()
