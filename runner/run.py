#!/usr/bin/env python3
"""Řídicí skript benchmarku.

  runner/run.py plan.json [--budget 200] [--only RUN_ID…] [--dry-run]

Pro každý běh plánu, který ještě nemá platný řádek v results.jsonl:
  1. kontejner z obrazu cc-bench-<NN>-<config> v izolované síti (ven jen přes gateway),
  2. `claude -p` s prompt.md úlohy, stream-json do runs/<run_id>/stream.jsonl,
  3. statistiky nástroje, transkript, diff (před verify, typecheck zanechává soubory),
  4. skryté testy + verify.sh uvnitř kontejneru,
  5. Codex review na hostiteli (2×, při neshodě > 1 bod 3×),
  6. řádek do results.jsonl, kontrola rozpočtu.

Neplatné běhy (`invalid`: neověřená aktivace, chyba harnessu, limit předplatného)
se zapíšou s důvodem a opakují; skutečné neúspěchy (max_turns, timeout) zůstávají.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import hook_text, parse_stream  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
RESULTS = ROOT / 'results.jsonl'
NETWORK = 'cc-bench-net'
GATEWAY = 'cc-bench-gateway'
TOKEN_FILE = Path(os.environ.get('CC_BENCH_ENV', Path.home() / '.config/cc-token-bench/env'))

MODEL = 'claude-sonnet-5-5'
EFFORT = 'medium'
MAX_TURNS = 80
RUN_TIMEOUT_S = 45 * 60
RUN_BUDGET_USD = 15
MAX_INVALID_RETRIES = 3
REVIEW_DISAGREEMENT = 1
LIMIT_PAUSE_UTILIZATION = 0.85
TOOL_MARKERS = re.compile(r'caveman|ponytail|\brtk\b|headroom|context[-_ ]?mode|ctx_[a-z_]+', re.I)


def sh(cmd, check=True, **kw):
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def log(msg: str) -> None:
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)


# ---------------------------------------------------------------- infrastruktura

def ensure_gateway() -> None:
    if not TOKEN_FILE.exists():
        sys.exit(f'chybí {TOKEN_FILE} s řádkem CLAUDE_CODE_OAUTH_TOKEN=… (claude setup-token)')
    if sh(['docker', 'network', 'inspect', NETWORK], check=False).returncode:
        sh(['docker', 'network', 'create', '--internal', NETWORK])
    st = sh(['docker', 'inspect', '-f', '{{.State.Running}}', GATEWAY], check=False)
    if st.stdout.strip() == 'true':
        return
    sh(['docker', 'rm', '-f', GATEWAY], check=False)
    sh(['docker', 'run', '-d', '--name', GATEWAY, '--network', NETWORK, '--env-file', str(TOKEN_FILE), 'cc-bench-gateway'])
    sh(['docker', 'network', 'connect', 'bridge', GATEWAY])
    time.sleep(1)


def gateway_log_lines() -> int:
    r = sh(['docker', 'exec', GATEWAY, 'sh', '-c', 'wc -l < /var/log/nginx/bench.jsonl 2>/dev/null || echo 0'], check=False)
    return int((r.stdout or '0').strip() or 0)


def gateway_log_since(n: int) -> str:
    r = sh(['docker', 'exec', GATEWAY, 'sh', '-c', f'tail -n +{n + 1} /var/log/nginx/bench.jsonl 2>/dev/null'], check=False)
    return r.stdout


def dexec(name, cmd, user='node', timeout=None, stdin=None, stdout=None):
    full = ['docker', 'exec', '-i', '-u', user, '-w', '/work', name, 'bash', '-c', cmd]
    return subprocess.run(full, text=True, input=stdin, stdout=stdout or subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def versions() -> dict:
    v = {}
    for img in sorted(set(sh(['docker', 'images', '--format', '{{.Repository}}'], check=False).stdout.split())):
        if re.match(r'cc-bench-\d\d-', img):
            cfg = img.split('-', 3)[3]
            if cfg not in v:
                r = sh(['docker', 'run', '--rm', '--network', 'none', img, 'bash', '-c',
                        'claude --version; cat /home/node/tools/VERSION 2>/dev/null || echo -'], check=False)
                lines = r.stdout.strip().splitlines()
                v[cfg] = {'cc_version': lines[0] if lines else None, 'tool_version': lines[1] if len(lines) > 1 else None}
    return v


# ---------------------------------------------------------------- jeden běh

CLAUDE_CMD = (
    f'timeout {RUN_TIMEOUT_S} claude -p --model {MODEL} --effort {EFFORT} --max-turns {MAX_TURNS} '
    f'--max-budget-usd {RUN_BUDGET_USD} --output-format stream-json --verbose '
    f'--permission-mode bypassPermissions < /bench/prompt.md'
)


def start_container(run_id: str, image: str, config: str) -> str:
    name = f'cc-bench-run-{run_id}'
    sh(['docker', 'rm', '-f', name], check=False)
    base_url = 'http://localhost:8787' if config == 'headroom' else f'http://{GATEWAY}:8787'
    sh(['docker', 'run', '-d', '--name', name, '--network', NETWORK, '--memory', '6g',
        '-e', f'ANTHROPIC_BASE_URL={base_url}',
        '-e', 'CLAUDE_CODE_OAUTH_TOKEN=injected-by-gateway',
        '-e', 'NO_PROXY=localhost,127.0.0.1',
        image, 'sleep', 'infinity'])
    dexec(name, 'mkdir -p /bench && chown node:node /bench', user='root')
    if config == 'headroom':
        dexec(name, f'nohup headroom proxy --port 8787 --anthropic-api-url http://{GATEWAY}:8787 '
                    f'--log-file /tmp/headroom.jsonl > /tmp/headroom.out 2>&1 &')
        for _ in range(60):
            if dexec(name, 'curl -sf localhost:8787/health >/dev/null').returncode == 0:
                break
            time.sleep(1)
    return name


def tool_stats(name: str, config: str, out: Path) -> dict:
    cmds = {
        'rtk': 'rtk gain --all --format json',
        'headroom': 'curl -s localhost:8787/stats',
        'caveman': 'ls -la ~/.claude/.caveman-active ~/.claude/.caveman-sessions 2>&1',
        'ponytail': 'ls -la ~/.claude/.ponytail-active 2>&1',
        'context-mode': 'ls -laR ~/.claude/context-mode 2>&1 | head -50',
        'claude-md-lean': 'git -C /work show base:CLAUDE.md | wc -c',
        'claude-md-full': 'git -C /work show base:CLAUDE.md | wc -c',
    }
    stats = {}
    if config in cmds:
        r = dexec(name, cmds[config])
        (out / 'tool_stats.txt').write_text(r.stdout + r.stderr)
        try:
            stats['raw'] = json.loads(r.stdout)
        except (json.JSONDecodeError, ValueError):
            stats['raw'] = r.stdout[-4000:]
    if config == 'headroom':
        r = dexec(name, 'curl -s localhost:8787/health')
        try:
            stats['health'] = json.loads(r.stdout)
        except (json.JSONDecodeError, ValueError):
            stats['health'] = r.stdout[-1000:]
        subprocess.run(['docker', 'cp', f'{name}:/tmp/headroom.jsonl', str(out / 'headroom.jsonl')], capture_output=True)
        subprocess.run(['docker', 'cp', f'{name}:/tmp/headroom.out', str(out / 'headroom.out')], capture_output=True)
    return stats


def context_limit(res: dict) -> bool:
    text = f"{res.get('result') or ''} {res.get('terminal_reason') or ''} {res.get('stop_reason') or ''}".lower()
    return bool(res.get('is_error')) and any(k in text for k in (
        'prompt is too long', 'context window', 'context_length', 'model_context_window_exceeded', 'too many tokens'))


def big_data_access(task: str, m: dict) -> dict:
    """Sáhl agent na objemná data úlohy? Vzory v tasks/<task>/big-data.json: {jméno: regex}.
    Pro každý vzor počet volání nástrojů, jejichž vstup ho obsahuje, a součet znaků jejich výsledků."""
    path = ROOT / 'tasks' / task / 'big-data.json'
    if not path.exists():
        return {}
    out = {}
    for label, rx in json.loads(path.read_text()).items():
        hits = [c for c in m.get('tool_calls', []) if re.search(rx, c['input'])]
        out[label] = {'calls': len(hits), 'result_chars': sum(c['result_chars'] for c in hits)}
    return out


def check_activation(config: str, m: dict, stats: dict) -> tuple[bool, str]:
    """Ověří, že nástroj v běhu skutečně působil. Bez ověření = invalid."""
    init = m['init']
    hooks = hook_text(m)
    mcp = [s.get('name', '') for s in (init.get('mcp_servers') or [])]
    plugins = [p.get('name', '') for p in (init.get('plugins') or []) if p.get('path') != 'builtin']
    if config == 'baseline':
        ok = not plugins and not mcp
        return ok, f'plugins={plugins} mcp={mcp}'
    if config == 'caveman':
        ok = 'CAVEMAN MODE ACTIVE' in hooks or 'smart caveman' in hooks
        return ok, 'caveman banner v SessionStart hooku' if ok else 'banner Cavemana v hook výstupu nenalezen'
    if config == 'ponytail':
        ok = 'PONYTAIL MODE ACTIVE' in hooks or 'lazy senior developer' in hooks
        return ok, 'ponytail banner v SessionStart hooku' if ok else 'banner Ponytailu v hook výstupu nenalezen'
    if config == 'rtk':
        summary = (stats.get('raw') or {}).get('summary', {}) if isinstance(stats.get('raw'), dict) else {}
        n = summary.get('total_commands', 0)
        bash = m['tool_uses'].get('Bash', 0)
        # Bez jediného příkazu v Bashi RTK neměl co zachytit; běh je platný, jen bez efektu.
        return n > 0 or bash == 0, f'rtk total_commands={n} bash_calls={bash}'
    if config == 'context-mode':
        connected = [s for s in (init.get('mcp_servers') or []) if 'context' in s.get('name', '') and s.get('status') == 'connected']
        calls = {k: v for k, v in m['tool_uses'].items() if 'context' in k.lower() or k.startswith('mcp__') and 'ctx_' in k}
        return bool(connected), f'mcp={connected} ctx_calls={calls}'
    if config == 'headroom':
        raw = stats.get('raw') if isinstance(stats.get('raw'), dict) else {}
        h = stats.get('health') if isinstance(stats.get('health'), dict) else {}
        n = (raw.get('summary') or {}).get('api_requests') or (h.get('stats') or {}).get('total_requests') or 0
        return n > 0, f'headroom api_requests={n}'
    if config in ('claude-md-lean', 'claude-md-full'):
        size = stats.get('raw') if isinstance(stats.get('raw'), int) else 0
        ok = size < 20000 if config == 'claude-md-lean' else size > 60000
        return ok, f'CLAUDE.md v base: {size} B'
    return True, 'bez kontroly aktivace'


def capture_diff(name: str, out: Path) -> dict:
    dexec(name, 'git add -A -N . >/dev/null 2>&1; true')
    full = dexec(name, 'git diff base --no-color -- . ":(exclude)*.tsbuildinfo"').stdout
    (out / 'diff.patch').write_text(full)
    numstat = dexec(name, 'git diff base --numstat -- . ":(exclude)*.tsbuildinfo"').stdout
    loc_code = loc_docs = 0
    files = []
    for line in numstat.splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        a, d, path = parts
        n = (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
        files.append(path)
        if path.startswith('docs/') or path.endswith('.md'):
            loc_docs += n
        else:
            loc_code += n
    review_diff = dexec(name, 'git diff base --no-color -- . ":(exclude)docs/**" ":(exclude)*.md" ":(exclude)*.tsbuildinfo"').stdout
    redacted, leaks = TOOL_MARKERS.subn('[redacted]', review_diff)
    (out / 'review.diff').write_text(redacted)
    commits = dexec(name, 'git rev-list --count base..HEAD').stdout.strip()
    return {'diff_loc_code': loc_code, 'diff_loc_docs': loc_docs, 'files_changed': files,
            'leak_markers': leaks, 'agent_commits': int(commits or 0)}


def verify(name: str, task: str, out: Path) -> dict:
    dexec(name, 'mkdir -p /bench/tasks /bench/scripts', user='root')
    subprocess.run(['docker', 'cp', str(ROOT / 'tasks' / task), f'{name}:/bench/tasks/{task}'], check=True)
    subprocess.run(['docker', 'cp', str(ROOT / 'scripts' / 'verify-lib.sh'), f'{name}:/bench/scripts/verify-lib.sh'], check=True)
    dexec(name, 'chown -R node:node /bench', user='root')
    r = dexec(name, f'PNPM=pnpm STEP_TIMEOUT=1200 bash /bench/tasks/{task}/verify.sh /work /bench/verify', timeout=4000)
    (out / 'verify.out').write_text(r.stdout + r.stderr)
    subprocess.run(['docker', 'cp', f'{name}:/bench/verify', str(out / 'verify')], capture_output=True)
    try:
        return json.loads((out / 'verify' / 'verify.json').read_text())
    except (OSError, json.JSONDecodeError):
        return {'hidden_tests_pass': False, 'suite_pass': False, 'typecheck_pass': False, 'verify_error': True}


def review(task: str, out: Path) -> tuple[list, bool]:
    diff = out / 'review.diff'
    if not diff.read_text().strip():
        return [], False
    scores = []
    for i in range(3):
        if i == 2 and not disagreement(scores):
            break
        dest = out / f'review-{random.getrandbits(32):08x}.json'
        r = subprocess.run([str(ROOT / 'review' / 'run-review.sh'), str(ROOT / 'tasks' / task / 'prompt.md'), str(diff), str(dest)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            scores.append({k: v['score'] for k, v in json.loads(dest.read_text()).items()} | {'file': dest.name})
        else:
            scores.append({'error': (r.stderr or r.stdout)[-500:]})
    return scores, disagreement(scores)


def disagreement(scores: list) -> bool:
    ok = [s for s in scores if 'error' not in s][:2]
    if len(ok) < 2:
        return False
    return any(abs(ok[0][k] - ok[1][k]) > REVIEW_DISAGREEMENT for k in ok[0] if k != 'file')


def limit_info(m: dict) -> dict:
    ev = [e.get('rate_limit_info', {}) for e in m['rate_limit_events']]
    if not ev:
        return {}
    first, last = ev[0], ev[-1]
    w = lambda x, k: ((x.get('unifiedWindows') or {}).get(k) or {}).get('utilization')  # noqa: E731
    return {'five_hour_before': w(first, 'five_hour'), 'five_hour_after': w(last, 'five_hour'),
            'seven_day_before': w(first, 'seven_day'), 'seven_day_after': w(last, 'seven_day'),
            'status': last.get('status'), 'resets_at': last.get('resetsAt')}


def run_one(run: dict, attempt: int, meta: dict) -> dict:
    run_id, task, config = run['run_id'], run['task'], run['config']
    nn = task[:2]
    out = RUNS / run_id / f'attempt-{attempt}'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    image = f'cc-bench-{nn}-{config}'
    row = {**{k: run[k] for k in ('run_id', 'seed_position', 'task', 'config', 'repetition')},
           'attempt': attempt, 'started_at': now(), 'model': MODEL, 'effort': EFFORT,
           'cc_version': meta.get(config, {}).get('cc_version'), 'tool_version': meta.get(config, {}).get('tool_version'),
           'auth_mode': 'oauth-subscription', 'image': image}
    name = None
    try:
        name = start_container(run_id, image, config)
        subprocess.run(['docker', 'cp', str(ROOT / 'tasks' / task / 'prompt.md'), f'{name}:/bench/prompt.md'], check=True)
        gw_before = gateway_log_lines()
        t0 = time.time()
        with open(out / 'stream.jsonl', 'w') as f:
            p = subprocess.run(['docker', 'exec', '-u', 'node', '-w', '/work', name, 'bash', '-c', CLAUDE_CMD],
                               stdout=f, stderr=subprocess.PIPE, text=True, timeout=RUN_TIMEOUT_S + 120)
        wall = time.time() - t0
        (out / 'stderr.txt').write_text(p.stderr)
        (out / 'gateway.jsonl').write_text(gateway_log_since(gw_before))
        m = parse_stream(out / 'stream.jsonl')
        (out / 'metrics.json').write_text(json.dumps(m, indent=1, ensure_ascii=False))
        subprocess.run(['docker', 'cp', f'{name}:/home/node/.claude/projects', str(out / 'transcripts')], capture_output=True)

        stats = tool_stats(name, config, out)
        active, activation_note = check_activation(config, m, stats)
        diff = capture_diff(name, out)
        res = m['result']
        usage = res.get('usage') or {}

        if p.returncode == 124:
            status = 'timeout'
        elif (res.get('subtype') or '').endswith('max_turns'):
            status = 'max_turns'
        elif (res.get('subtype') or '').endswith('max_budget_usd'):
            status = 'max_budget'
        elif context_limit(res):
            # Agent přeplnil kontext (např. cat na velký soubor): regulérní neúspěch se spotřebou.
            status = 'context_limit'
        elif not m['has_result'] or res.get('is_error') or res.get('api_error_status'):
            status = 'invalid'
        else:
            status = 'ok'
        invalid_reason = None
        if status == 'invalid':
            invalid_reason = f"claude: subtype={res.get('subtype')} api_error={res.get('api_error_status')} rc={p.returncode}"
        elif not active:
            status, invalid_reason = 'invalid', f'aktivace neověřena: {activation_note}'

        gw_lines = [json.loads(x) for x in (out / 'gateway.jsonl').read_text().splitlines() if x.strip()]
        row.update({
            'status': status, 'invalid_reason': invalid_reason,
            'cost_usd': res.get('total_cost_usd'),
            'input_tokens': usage.get('input_tokens'),
            'cache_read_tokens': usage.get('cache_read_input_tokens'),
            'cache_write_tokens': usage.get('cache_creation_input_tokens'),
            'output_tokens': usage.get('output_tokens'),
            'thinking_tokens': (usage.get('output_tokens_details') or {}).get('thinking_tokens'),
            'cache_write_1h_tokens': (usage.get('cache_creation') or {}).get('ephemeral_1h_input_tokens'),
            'cache_write_5m_tokens': (usage.get('cache_creation') or {}).get('ephemeral_5m_input_tokens'),
            'model_usage': res.get('modelUsage'),
            'duration_s': round((res.get('duration_ms') or wall * 1000) / 1000, 1),
            'duration_api_s': round((res.get('duration_api_ms') or 0) / 1000, 1),
            'wall_s': round(wall, 1),
            'turns': res.get('num_turns'),
            'api_calls': m['api_call_count'],
            'tool_uses': m['tool_uses'],
            'tool_result_chars': m['tool_result_chars'],
            'tool_result_chars_total': m['tool_result_chars_total'],
            'tool_result_chars_max': m.get('tool_result_chars_max'),
            'compactions': m.get('compactions'),
            'big_data_access': big_data_access(task, m),
            'assistant_text_chars': m['assistant_text_chars'],
            'thinking_chars': m['thinking_chars'],
            'permission_denials': len(res.get('permission_denials') or []),
            'subagents_spawned': (res.get('subagent_stats') or {}).get('spawned'),
            'gateway_requests': len(gw_lines),
            'gateway_req_bytes': sum(x.get('req_bytes', 0) for x in gw_lines),
            'gateway_resp_bytes': sum(x.get('resp_bytes', 0) for x in gw_lines),
            'subscription_limits': limit_info(m),
            'init_model': m['init'].get('model'),
            'init_effort_active': m['init'].get('per_turn_effort_active'),
            'activation_verified': active, 'activation_note': activation_note,
            'tool_stats': stats,
            **diff,
        })

        if status != 'invalid':
            row.update(verify(name, task, out))
            row['review_scores'], row['review_disagreement'] = review(task, out)
    except Exception as e:  # chyba harnessu → invalid, běh se zopakuje
        row.update({'status': 'invalid', 'invalid_reason': f'harness: {type(e).__name__}: {e}'})
    finally:
        if name:
            sh(['docker', 'rm', '-f', name], check=False)
    row['finished_at'] = now()
    (out / 'row.json').write_text(json.dumps(row, indent=1, ensure_ascii=False))
    return row


# ---------------------------------------------------------------- smyčka

def load_results() -> list:
    if not RESULTS.exists():
        return []
    return [json.loads(x) for x in RESULTS.read_text().splitlines() if x.strip()]


def spent(rows) -> float:
    return sum(r.get('cost_usd') or 0 for r in rows)


def wait_for_limit(rows) -> None:
    lim = next((r['subscription_limits'] for r in reversed(rows) if r.get('subscription_limits')), None)
    if not lim:
        return
    util = lim.get('five_hour_after') or 0
    if util >= LIMIT_PAUSE_UTILIZATION or lim.get('status') == 'rejected':
        wait = max(0, (lim.get('resets_at') or 0) - time.time()) + 60
        log(f'pětihodinový limit na {util:.0%}, čekám {wait / 60:.0f} min na reset')
        time.sleep(wait)


def hit_limit(row: dict) -> bool:
    lim = row.get('subscription_limits') or {}
    reason = row.get('invalid_reason') or ''
    return lim.get('status') == 'rejected' or 'api_error=429' in reason or 'rate_limit' in reason


def wait_for_reset(row: dict) -> None:
    resets = (row.get('subscription_limits') or {}).get('resets_at') or 0
    wait = max(resets - time.time(), 0) + 120 if resets else 30 * 60
    log(f'limit předplatného vyčerpán, čekám {wait / 60:.0f} min')
    time.sleep(wait)


def single_instance() -> None:
    """Jen jeden runner naráz: dva by sdílely jména kontejnerů a navzájem si je mazaly
    (stalo se 2026-10-20, ověření pak běželo na čistém snapshotu)."""
    import fcntl
    (ROOT / 'build').mkdir(exist_ok=True)
    global _LOCK
    _LOCK = open(ROOT / 'build' / 'run.lock', 'w')
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('jiný runner už běží (build/run.lock)')


def main() -> None:
    global RESULTS
    if '--dry-run' not in sys.argv:
        single_instance()
    ap = argparse.ArgumentParser()
    ap.add_argument('plan')
    ap.add_argument('--budget', type=float, default=200.0)
    ap.add_argument('--stop-at', type=float, default=0.8, help='podíl rozpočtu, kde se runner zastaví')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--results', default=str(RESULTS), help='soubor výsledků (pilot: results-pilot.jsonl)')
    a = ap.parse_args()
    RESULTS = Path(a.results)

    plan = json.loads(Path(a.plan).read_text())
    rows = load_results()
    done = {r['run_id'] for r in rows if r['status'] != 'invalid'}
    todo = [r for r in plan['runs'] if r['run_id'] not in done and (not a.only or r['run_id'] in a.only)]
    log(f'plán {a.plan}: {len(plan["runs"])} běhů, hotovo {len(done)}, zbývá {len(todo)}, utraceno {spent(rows):.2f} USD')
    if a.dry_run:
        for r in todo:
            print(r['run_id'])
        return

    ensure_gateway()
    meta = versions()
    (RUNS).mkdir(exist_ok=True)
    (RUNS / f'versions-{datetime.now():%Y%m%d-%H%M%S}.json').write_text(json.dumps(meta, indent=1))

    for run in todo:
        for attempt in range(1, MAX_INVALID_RETRIES + 2):
            if spent(rows) >= a.budget * a.stop_at:
                log(f'STOP: utraceno {spent(rows):.2f} USD ≥ {a.stop_at:.0%} rozpočtu {a.budget:.0f} USD')
                return
            wait_for_limit(rows)
            log(f'{run["run_id"]} pokus {attempt}')
            row = run_one(run, attempt, meta)
            rows.append(row)
            with RESULTS.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            log(f'  → {row["status"]} {row.get("cost_usd")} USD, {row.get("duration_s")} s, '
                f'hidden={row.get("hidden_tests_pass")} {row.get("invalid_reason") or ""}')
            if row['status'] != 'invalid':
                break
            if hit_limit(row):
                wait_for_reset(row)
    log(f'hotovo, utraceno {spent(rows):.2f} USD')


if __name__ == '__main__':
    main()
