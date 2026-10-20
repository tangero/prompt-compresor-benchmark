#!/usr/bin/env python3
"""Analýza results.jsonl: souhrnné tabulky, CSV a grafy pro článek.

  uv run --with matplotlib analysis/analyze.py [results.jsonl] [--out analysis/out]

Cena se počítá z total_cost_usd (přepočet podle ceníku API; na předplatném orientační).
Porovnává se medián ceny konfigurace proti baseline téže úlohy. Neúspěšné běhy
(max_turns, timeout, max_budget, context_limit) se započítávají, `invalid` se vynechávají a jen počítají.
Ceny po kategoriích tokenů jsou přepočet podle sazeb níže (USD za 1M tokenů).

Studená cena (cost_cold_usd): běhy sdílejí cache promptů napříč během (TTL 1 h), takže
první volání běhu často čte prefix, který zapsal dřívější běh se stejnou konfigurací.
Kolik ušetří, závisí na pořadí v plánu, ne na nástroji. Studená cena přeceňuje každé takové
„cizí“ čtení z cache na zápis, jako by každý běh začínal s prázdnou cache. Cizí čtení
volání = čtení z cache nad délku promptu předchozího volání téhož běhu (u prvního celé).
Hlavní srovnání se dělá na studené ceně, skutečně účtovaná cena je uvedena vedle.
"""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Ceník claude-sonnet-5-5 (USD za 1M tokenů): vstup, 1h zápis, čtení a výstup odvozeny přesně
# (lineární regrese, chyba < 1e-14) z modelUsage.costUSD všech 54 běhů. 5m zápisy se v datech
# nevyskytly. Všechny sazby souhlasí s oficiálním ceníkem Anthropic (říjen 2026), odkud je i 5m zápis.
PRICES = {'input': 2.0, 'cache_write_5m': 2.5, 'cache_write_1h': 4.0, 'cache_read': 0.10, 'output': 10.0}
CRITERIA = ['correctness', 'concurrency_security', 'error_handling', 'readability', 'scope']
FAILED = {'max_turns', 'timeout', 'max_budget', 'context_limit'}
CONFIG_ORDER = ['baseline', 'caveman', 'ponytail', 'rtk', 'context-mode', 'headroom',
                'claude-md-lean', 'claude-md-full', 'token-savior', 'token-efficient-md', 'rtk+caveman+ponytail']


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def rng(xs):
    xs = [x for x in xs if x is not None]
    return (min(xs), max(xs)) if xs else (None, None)


def pct(a, b):
    return None if a is None or not b else 100.0 * (a - b) / b


def cost_split(r, cold=False):
    w5 = r.get('cache_write_5m_tokens') or 0
    w1 = r.get('cache_write_1h_tokens') or 0
    if not (w5 or w1):
        w5 = r.get('cache_write_tokens') or 0
    ext = (r.get('external_cache_read_tokens') or 0) if cold else 0
    return {
        'input': (r.get('input_tokens') or 0) * PRICES['input'] / 1e6,
        'cache_write': (w5 * PRICES['cache_write_5m'] + (w1 + ext) * PRICES['cache_write_1h']) / 1e6,
        'cache_read': ((r.get('cache_read_tokens') or 0) - ext) * PRICES['cache_read'] / 1e6,
        'output': (r.get('output_tokens') or 0) * PRICES['output'] / 1e6,
    }


def enrich(r):
    """Doplní cizí čtení z cache, studenou cenu a velikost výchozího promptu z metrics.json."""
    # opětovné ověření (scripts/reverify.py) má přednost před ověřením v runneru
    for k in ('hidden_tests_pass', 'suite_pass', 'typecheck_pass'):
        if f'reverify_{k}' in r:
            r[f'runner_{k}'] = r.get(k)
            r[k] = r[f'reverify_{k}']
    path =ROOT / 'runs' / r['run_id'] / f"attempt-{r.get('attempt', 1)}" / 'metrics.json'
    if not path.exists():
        r['external_cache_read_tokens'] = None
        r['cost_cold_usd'] = r.get('cost_usd')
        return r
    calls = [c for c in json.loads(path.read_text())['api_calls'] if not c.get('subagent')]
    ext, prev = 0, 0
    for c in calls:
        ext += max(0, c['cache_read'] - prev)
        prev = c['cache_read'] + c['cache_write'] + c['input']
    r['external_cache_read_tokens'] = ext
    r['cost_cold_usd'] = (r.get('cost_usd') or 0) + ext * (PRICES['cache_write_1h'] - PRICES['cache_read']) / 1e6
    first = calls[0] if calls else None
    r['first_prompt_tokens'] = first['cache_read'] + first['cache_write'] + first['input'] if first else None
    return r


def review_mean(r):
    ok = [s for s in (r.get('review_scores') or []) if 'error' not in s]
    if not ok:
        return {}
    return {c: statistics.mean(s[c] for s in ok) for c in CRITERIA}


def ordered(configs):
    return sorted(configs, key=lambda c: (CONFIG_ORDER.index(c) if c in CONFIG_ORDER else 99, c))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='?', default=str(ROOT / 'results.jsonl'))
    ap.add_argument('--out', default=str(ROOT / 'analysis' / 'out'))
    a = ap.parse_args()
    out = Path(a.out)
    (out / 'charts').mkdir(parents=True, exist_ok=True)

    rows = [json.loads(x) for x in Path(a.results).read_text().splitlines() if x.strip()]
    invalid = defaultdict(int)
    for r in rows:
        if r['status'] == 'invalid':
            invalid[(r['task'], r['config'])] += 1
    # poslední platný pokus každého run_id
    valid = {}
    for r in rows:
        if r['status'] != 'invalid':
            valid[r['run_id']] = r
    runs = [enrich(r) for r in valid.values()]

    groups = defaultdict(list)
    for r in runs:
        groups[(r['task'], r['config'])].append(r)
    tasks = sorted({r['task'] for r in runs})
    configs = ordered({r['config'] for r in runs})

    # ---- tabulka úloha × konfigurace
    table = []
    for t in tasks:
        base = groups.get((t, 'baseline'), [])
        base_cost = med([r['cost_usd'] for r in base])
        base_cold = med([r['cost_cold_usd'] for r in base])
        base_prompt = med([r.get('first_prompt_tokens') for r in base])
        base_time = med([r['duration_s'] for r in base])
        base_split = {k: med([cost_split(r, cold=True)[k] for r in base]) for k in ('input', 'cache_write', 'cache_read', 'output')}
        for c in configs:
            g = groups.get((t, c), [])
            if not g:
                continue
            costs = [r['cost_usd'] for r in g]
            split = {k: med([cost_split(r, cold=True)[k] for r in g]) for k in base_split}
            cold = [r['cost_cold_usd'] for r in g]
            rev = [review_mean(r) for r in g]
            row = {
                'task': t, 'config': c, 'n': len(g), 'invalid': invalid[(t, c)],
                'failed': sum(r['status'] in FAILED for r in g),
                'cost_median': med(costs), 'cost_min': rng(costs)[0], 'cost_max': rng(costs)[1],
                'cost_vs_baseline_pct': pct(med(costs), base_cost),
                'cost_cold_median': med(cold), 'cost_cold_min': rng(cold)[0], 'cost_cold_max': rng(cold)[1],
                'cost_cold_vs_baseline_pct': pct(med(cold), base_cold),
                'external_cache_read_median': med([r.get('external_cache_read_tokens') for r in g]),
                'first_prompt_tokens_median': med([r.get('first_prompt_tokens') for r in g]),
                'first_prompt_vs_baseline_tokens': (med([r.get('first_prompt_tokens') for r in g]) or 0) - (base_prompt or 0),
                'time_median_s': med([r['duration_s'] for r in g]),
                'time_vs_baseline_pct': pct(med([r['duration_s'] for r in g]), base_time),
                'turns_median': med([r['turns'] for r in g]),
                'turns_min': rng([r['turns'] for r in g])[0], 'turns_max': rng([r['turns'] for r in g])[1],
                'input_tokens_median': med([r['input_tokens'] for r in g]),
                'cache_read_median': med([r['cache_read_tokens'] for r in g]),
                'cache_write_median': med([r['cache_write_tokens'] for r in g]),
                'output_tokens_median': med([r['output_tokens'] for r in g]),
                'tool_result_chars_median': med([r.get('tool_result_chars_total') for r in g]),
                'assistant_text_chars_median': med([r.get('assistant_text_chars') for r in g]),
                'diff_loc_code_median': med([r.get('diff_loc_code') for r in g]),
                'five_hour_delta_median': med([
                    (r['subscription_limits'].get('five_hour_after') or 0) - (r['subscription_limits'].get('five_hour_before') or 0)
                    for r in g if r.get('subscription_limits')]),
                'hidden_pass': sum(bool(r.get('hidden_tests_pass')) for r in g),
                'suite_pass': sum(bool(r.get('suite_pass')) for r in g),
                'typecheck_pass': sum(bool(r.get('typecheck_pass')) for r in g),
                'review_disagreements': sum(bool(r.get('review_disagreement')) for r in g),
                **{f'cost_{k}_median': split[k] for k in split},
                **{f'cost_{k}_vs_baseline_pct': pct(split[k], base_split[k]) for k in split},
                **{f'review_{c2}': med([x.get(c2) for x in rev]) for c2 in CRITERIA},
            }
            table.append(row)
    write_csv(out / 'by_task_config.csv', table)

    # ---- souhrn přes úlohy (průměr relativních změn mediánů)
    summary = []
    for c in configs:
        rs = [x for x in table if x['config'] == c]
        g = [r for r in runs if r['config'] == c]
        summary.append({
            'config': c, 'runs': len(g), 'invalid': sum(x['invalid'] for x in rs),
            'cost_cold_change_pct': mean_or_none([x['cost_cold_vs_baseline_pct'] for x in rs]),
            'cost_change_pct': mean_or_none([x['cost_vs_baseline_pct'] for x in rs]),
            'time_change_pct': mean_or_none([x['time_vs_baseline_pct'] for x in rs]),
            'success_rate': sum(bool(r.get('hidden_tests_pass')) for r in g) / len(g) if g else None,
            'failure_rate': sum(r['status'] in FAILED for r in g) / len(g) if g else None,
            **{f'review_{c2}': mean_or_none([review_mean(r).get(c2) for r in g]) for c2 in CRITERIA},
        })
    write_csv(out / 'summary.csv', summary)
    write_csv(out / 'runs.csv', [flat(r) for r in runs])
    (out / 'summary.md').write_text(markdown(summary, table))
    print((out / 'summary.md').read_text())
    charts(out / 'charts', runs, table, configs, tasks)


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def flat(r):
    keep = ['run_id', 'seed_position', 'task', 'config', 'repetition', 'attempt', 'status', 'cost_usd',
            'cost_cold_usd', 'external_cache_read_tokens', 'first_prompt_tokens',
            'input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens', 'thinking_tokens',
            'duration_s', 'turns', 'api_calls', 'tool_result_chars_total', 'assistant_text_chars',
            'hidden_tests_pass', 'suite_pass', 'typecheck_pass', 'diff_loc_code', 'diff_loc_docs',
            'review_disagreement', 'model', 'effort', 'cc_version', 'tool_version',
            'runner_hidden_tests_pass', 'runner_suite_pass', 'runner_typecheck_pass', 'reverify_attempts',
            'tool_result_chars_max', 'compactions']
    d = {k: r.get(k) for k in keep}
    d.update({f'review_{k}': v for k, v in review_mean(r).items()})
    d.update({f'cost_{k}': v for k, v in cost_split(r).items()})
    d.update({f'cost_cold_{k}': v for k, v in cost_split(r, cold=True).items()})
    return d


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def fmt(v, suffix='', digits=1):
    if v is None:
        return '–'
    return f'{v:+.{digits}f}{suffix}' if suffix == ' %' else f'{v:.{digits}f}{suffix}'


def markdown(summary, table):
    lines = ['## Souhrn přes úlohy', '',
             'Změna = průměr relativních změn mediánu proti baseline přes úlohy, na kterých konfigurace běžela. Studená cena: každý běh',
             'jako s prázdnou cache (viz docstring analyze.py); účtovaná: skutečný total_cost_usd.', '',
             '| Konfigurace | Běhů | Změna studené ceny | Změna účtované ceny | Změna času | Úspěšnost skrytých testů | Neúspěšné běhy | Review správnost | Review souběh | invalid |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for s in summary:
        lines.append(f"| {s['config']} | {s['runs']} | {fmt(s['cost_cold_change_pct'], ' %')} | {fmt(s['cost_change_pct'], ' %')} | {fmt(s['time_change_pct'], ' %')} | "
                     f"{fmt((s['success_rate'] or 0) * 100, '%', 0) if s['success_rate'] is not None else '–'} | "
                     f"{fmt((s['failure_rate'] or 0) * 100, '%', 0) if s['failure_rate'] is not None else '–'} | "
                     f"{fmt(s['review_correctness'], '', 2)} | {fmt(s['review_concurrency_security'], '', 2)} | {s['invalid']} |")
    lines += ['', '## Úloha × konfigurace', '',
              'Rozpad Δ po kategoriích je ze studené ceny.', '',
              '| Úloha | Konfigurace | n | Studená cena USD (min–max) | Δ studená | Účtovaná USD (min–max) | Δ účtovaná | Výchozí prompt tokenů (Δ) | Δ nové vstupy | Δ zápis cache | Δ čtení cache | Δ výstup | Medián času s | Tahy (min–max) | Skryté testy | Review správnost |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for x in table:
        lines.append(f"| {x['task']} | {x['config']} | {x['n']} | {fmt(x['cost_cold_median'], '', 2)} ({fmt(x['cost_cold_min'], '', 2)}–{fmt(x['cost_cold_max'], '', 2)}) | "
                     f"{fmt(x['cost_cold_vs_baseline_pct'], ' %')} | {fmt(x['cost_median'], '', 2)} ({fmt(x['cost_min'], '', 2)}–{fmt(x['cost_max'], '', 2)}) | "
                     f"{fmt(x['cost_vs_baseline_pct'], ' %')} | {fmt(x['first_prompt_tokens_median'], '', 0)} ({x['first_prompt_vs_baseline_tokens']:+.0f}) | {fmt(x['cost_input_vs_baseline_pct'], ' %')} | {fmt(x['cost_cache_write_vs_baseline_pct'], ' %')} | "
                     f"{fmt(x['cost_cache_read_vs_baseline_pct'], ' %')} | {fmt(x['cost_output_vs_baseline_pct'], ' %')} | {fmt(x['time_median_s'], '', 0)} | "
                     f"{fmt(x['turns_median'], '', 0)} ({fmt(x['turns_min'], '', 0)}–{fmt(x['turns_max'], '', 0)}) | {x['hidden_pass']}/{x['n']} | {fmt(x['review_correctness'], '', 2)} |")
    return '\n'.join(lines) + '\n'


def charts(d, runs, table, configs, tasks):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib chybí, grafy přeskočeny (uv run --with matplotlib …)')
        return
    colors = {'input': '#4C78A8', 'cache_write': '#F58518', 'cache_read': '#72B7B2', 'output': '#E45756'}

    # 2. rozpad ceny po kategoriích, medián přes všechny běhy konfigurace
    # (jen konfigurace hlavního běhu; pokus s CLAUDE.md běžel na jiných úlohách a nebyl by srovnatelný)
    main = [c for c in configs if not c.startswith('claude-md')]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bottom = [0.0] * len(main)
    rows_csv = []
    for k in colors:
        vals = [med([cost_split(r, cold=True)[k] for r in runs if r['config'] == c]) or 0 for c in main]
        ax.bar(main, vals, bottom=bottom, color=colors[k], label=k)
        bottom = [b + v for b, v in zip(bottom, vals)]
        rows_csv += [{'config': c, 'category': k, 'usd_median': v} for c, v in zip(main, vals)]
    ax.set_ylabel('USD (medián na běh)')
    ax.set_title('Rozpad studené ceny po kategoriích tokenů (všechny úlohy)')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    fig.tight_layout()
    fig.savefig(d / 'cost_breakdown.png', dpi=160)
    fig.savefig(d / 'cost_breakdown.svg')
    write_csv(d / 'cost_breakdown.csv', rows_csv)
    plt.close(fig)

    # 3. cena vs. kvalita, bod = běh
    fig, ax = plt.subplots(figsize=(8, 5))
    pts = []
    for i, c in enumerate(configs):
        xs = [r['cost_cold_usd'] for r in runs if r['config'] == c]
        ys = [review_mean(r).get('correctness') for r in runs if r['config'] == c]
        xy = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        ax.scatter([p[0] for p in xy], [p[1] for p in xy], label=c, alpha=0.75)
        pts += [{'config': c, 'cost_cold_usd': x, 'review_correctness': y} for x, y in xy]
    ax.set_xlabel('Studená cena běhu USD')
    ax.set_ylabel('Review: correctness (1–5)')
    ax.set_title('Cena vs. kvalita')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(d / 'cost_vs_quality.png', dpi=160)
    fig.savefig(d / 'cost_vs_quality.svg')
    write_csv(d / 'cost_vs_quality.csv', pts)
    plt.close(fig)

    # 4. rozptyl opakovaných běhů
    fig, axes = plt.subplots(1, len(tasks), figsize=(4 * len(tasks), 4.5), squeeze=False)
    spread = []
    for ax, t in zip(axes[0], tasks):
        for i, c in enumerate(configs):
            g = [r for r in runs if r['task'] == t and r['config'] == c and r['cost_usd'] is not None]
            ax.scatter([i - 0.12] * len(g), [r['cost_usd'] for r in g], facecolors='none', edgecolors=f'C{i}',
                       label='účtovaná' if i == 0 else None)
            ax.scatter([i + 0.12] * len(g), [r['cost_cold_usd'] for r in g], color=f'C{i}',
                       label='studená' if i == 0 else None)
            spread += [{'task': t, 'config': c, 'cost_usd': r['cost_usd'], 'cost_cold_usd': r['cost_cold_usd']} for r in g]
        ax.set_xticks(range(len(configs)))
        ax.set_xticklabels(configs, rotation=45, ha='right', fontsize=8)
        ax.set_title(t)
        ax.set_ylabel('USD')
        ax.legend(fontsize=7)
    fig.suptitle('Rozptyl ceny opakovaných běhů: účtovaná (prázdné) vs. studená (plné)')
    fig.tight_layout()
    fig.savefig(d / 'run_spread.png', dpi=160)
    fig.savefig(d / 'run_spread.svg')
    write_csv(d / 'run_spread.csv', spread)
    plt.close(fig)

    # 1. slib vs. nezávislé měření vs. náš výsledek: claims.json se doplňuje ručně z ověřených zdrojů
    claims_path = ROOT / 'analysis' / 'claims.json'
    if claims_path.exists():
        claims = json.loads(claims_path.read_text())
        ours = {s['config']: s for s in [{'config': c, 'v': mean_or_none([x['cost_cold_vs_baseline_pct'] for x in table if x['config'] == c])} for c in configs]}
        names = [c for c in configs if c in claims]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        w = 0.27
        rows_csv = []
        for j, (key, label) in enumerate([('claim_pct', 'slib autorů'), ('independent_pct', 'nezávislé měření'), ('ours', 'náš test (studená cena)')]):
            vals = []
            for c in names:
                v = -(ours[c]['v'] or 0) if key == 'ours' else claims[c].get(key)
                vals.append(v or 0)
                rows_csv.append({'config': c, 'series': label, 'saving_pct': v})
            ax.bar([i + (j - 1) * w for i in range(len(names))], vals, width=w, label=label)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names)
        ax.axhline(0, color='black', linewidth=0.8)
        ax.set_ylabel('úspora % (metrika slibu se liší, viz claims.json)')
        ax.set_title('Slib vs. nezávislé měření vs. náš test')
        ax.legend()
        fig.tight_layout()
        fig.savefig(d / 'claims_vs_measured.png', dpi=160)
        fig.savefig(d / 'claims_vs_measured.svg')
        write_csv(d / 'claims_vs_measured.csv', rows_csv)
        plt.close(fig)


if __name__ == '__main__':
    main()
