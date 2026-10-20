"""Grafy pro článek (díl 1). Spuštění: python3 analysis/article_charts.py"""
import json, os
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis/out/charts/article")
r = pd.read_csv(os.path.join(ROOT, "analysis/out/runs.csv"))
btc = pd.read_csv(os.path.join(ROOT, "analysis/out/by_task_config.csv"))
claims = json.load(open(os.path.join(ROOT, "analysis/claims.json")))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 15, "axes.titleweight": "bold", "axes.titlelocation": "left"})
COL = {"baseline": "#4a4a4a", "caveman": "#ff7f0e", "ponytail": "#2ca02c", "rtk": "#d62728",
       "context-mode": "#9467bd", "headroom": "#8c564b", "claude-md-lean": "#e377c2", "claude-md-full": "#7f7f7f"}
NAME = {"baseline": "bez doplňků", "caveman": "Caveman", "ponytail": "Ponytail", "rtk": "RTK",
        "context-mode": "Context Mode", "headroom": "Headroom",
        "claude-md-lean": "CLAUDE.md 7 KB", "claude-md-full": "CLAUDE.md 67 KB"}
TASKS = ["01-priority-queue", "02-releases", "03-version-decoder", "04-glossary-extract"]
TNAME = {"01-priority-queue": "01 oprava chyby", "02-releases": "02 refaktoring",
         "03-version-decoder": "03 nová funkce", "04-glossary-extract": "04 objemná data"}
TOOLS = ["caveman", "ponytail", "rtk", "context-mode", "headroom"]
SRC = "Zdroj: cc-token-bench, Marigold.cz, říjen 2026. Claude Code 2.1.303, Sonnet 5.5, 3 běhy na buňku."

def cz(x, d=0):
    s = f"{x:+.{d}f}" if d else f"{x:+.0f}"
    return s.replace("-", "−").replace(".", ",")

def save(fig, name, src=SRC):
    fig.text(0.01, 0.01, src, fontsize=8.5, color="#777")
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200)
    fig.savefig(os.path.join(OUT, name + ".svg"))
    plt.close(fig)

def chg(task, cfg):
    row = btc[(btc.task == task) & (btc.config == cfg)]
    return float(row.cost_cold_vs_baseline_pct.iloc[0])

# 1 Sliby vs. měření
metric = {"caveman": "slib: výstupní tokeny odpovědi", "ponytail": "slib: cena",
          "rtk": "slib: výstup příkazů v shellu", "context-mode": "slib: výstupy nástrojů v kontextu",
          "headroom": "slib: vstupní tokeny (jeden scénář)"}
fig, ax = plt.subplots(figsize=(9, 6.2))
fig.subplots_adjust(left=0.30, right=0.97, top=0.82, bottom=0.12)
for i, t in enumerate(TOOLS):
    y = len(TOOLS) - 1 - i
    c = claims[t]
    ax.barh(y + 0.22, -c["claim_pct"], height=0.3, color="#cfcfcf")
    ax.text(-c["claim_pct"] - 1.5, y + 0.22, f"−{c['claim_pct']} %", va="center", ha="right", fontsize=10, color="#666")
    if c.get("independent_pct") is not None:
        ax.barh(y - 0.12, -c["independent_pct"], height=0.3, color="#8a8a8a")
        ax.text(-c["independent_pct"] - 1.5, y - 0.12, f"−{str(c['independent_pct']).replace('.', ',')} %", va="center", ha="right", fontsize=10, color="#444")
    else:
        ax.text(-1.5, y - 0.12, "nezávislé měření nenalezeno", va="center", ha="right", fontsize=9.5, color="#999", style="italic")
    vals = [chg(tk, t) for tk in TASKS]
    ax.scatter(vals, [y - 0.38] * 4, s=34, color=COL[t], zorder=3, edgecolor="white", linewidth=0.6)
    m = float(np.mean(vals))
    ax.scatter([m], [y - 0.38], s=110, marker="D", color=COL[t], zorder=4, edgecolor="black", linewidth=0.8)
    ax.text(30, y - 0.38, f"{cz(m)} %", va="center", ha="left", fontsize=11.5, fontweight="bold", color=COL[t])
ax.set_yticks(range(len(TOOLS)))
ax.set_yticklabels([f"{NAME[t]}\n{metric[t]}" for t in reversed(TOOLS)], fontsize=10.5)
ax.axvline(0, color="black", lw=0.8)
ax.set_xlim(-108, 42)
ax.text(30, len(TOOLS) - 0.45, "průměr", fontsize=9.5, color="#555")
ax.set_xlabel("změna v %  (vlevo = úspora, vpravo = prodražení)")
fig.suptitle("Co autoři slibují a co jsme naměřili", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.905, "Světle šedá: slib autorů (každý měří něco jiného). Tmavě šedá: nezávislé měření ceny.\n"
         "Tečky: naše měření ceny na čtyřech úlohách, kosočtverec: průměr.", fontsize=10, color="#555", va="top")
save(fig, "01_sliby_vs_mereni")

# 2 Kde se platí
b = r[r.config == "baseline"].copy()
b["think"] = b.thinking_tokens * 10 / 1e6
b["prose"] = b.assistant_text_chars / 4 * 10 / 1e6
b["code"] = b.cost_cold_output - b.think - b.prose
parts = [("cost_cold_cache_write", "zápis kontextu do cache", "#e8833a"),
         ("cost_cold_cache_read", "čtení kontextu z cache", "#76b7b2"),
         ("code", "výstup: kód a volání nástrojů", "#c44e52"),
         ("think", "výstup: přemýšlení modelu", "#e9a3a5"),
         ("prose", "výstup: text odpovědí (odhad)", "#4a4a4a")]
fig, ax = plt.subplots(figsize=(9, 5.4))
fig.subplots_adjust(left=0.20, right=0.97, top=0.80, bottom=0.30)
for i, t in enumerate(reversed(TASKS)):
    g = b[b.task == t]; tot = g.cost_cold_usd.sum(); left = 0
    for col, lab, c in parts:
        v = g[col].sum() / tot * 100
        ax.barh(i, v, left=left, color=c, height=0.62, label=lab if i == 0 else None)
        if v >= 7:
            ax.text(left + v / 2, i, f"{v:.0f} %", ha="center", va="center", color="white", fontsize=10.5, fontweight="bold")
        left += v
ax.set_yticks(range(4)); ax.set_yticklabels([TNAME[t] for t in reversed(TASKS)])
ax.set_xlim(0, 100); ax.set_xlabel("podíl na ceně běhu, %")
ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.42, -0.16), frameon=False, fontsize=10)
fig.suptitle("Za co se v Claude Code platí", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.885, "Běhy bez doplňků. Většinu ceny tvoří kontext, který agent nese z tahu do tahu.\n"
         "Text odpovědí, na který míří Caveman, je kolem 1 % ceny (odhad: 4 znaky na token).", fontsize=10, color="#555", va="top")
save(fig, "02_kde_se_plati")

# 3 Vstupní daň
first = {t: float(btc[(btc.task == "02-releases") & (btc.config == t)].first_prompt_vs_baseline_tokens.iloc[0]) for t in TOOLS}
order = sorted(TOOLS, key=lambda t: first[t])
fig, ax = plt.subplots(figsize=(9, 4.4))
fig.subplots_adjust(left=0.20, right=0.95, top=0.78, bottom=0.18)
for i, t in enumerate(order):
    v = first[t]
    ax.barh(i, v, color=COL[t], height=0.6)
    lab = (f"{v/1000:+.1f}".replace(".", ",").replace("-", "−")) + " tis."
    ax.text(max(v, 0) + 300, i, lab, va="center", ha="left", fontsize=11)
ax.set_yticks(range(len(order))); ax.set_yticklabels([NAME[t] for t in order])
ax.axvline(0, color="black", lw=0.8); ax.set_xlim(-1500, 18000)
ax.set_xticks([0, 5000, 10000, 15000]); ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x/1000:.0f} tis.".replace("-", "−")))
ax.set_xlabel("tokeny navíc v úvodním kontextu každé relace")
fig.suptitle("Vstupní daň: o kolik doplněk prodlouží začátek každé relace", x=0.01, ha="left", fontsize=14, fontweight="bold")
fig.text(0.01, 0.875, "Pro srovnání: celý úvodní kontext bez doplňků měl cca 30 tisíc tokenů (se 7KB CLAUDE.md).", fontsize=10, color="#555", va="top")
save(fig, "03_vstupni_dan")

# 4 Tepelná mapa
M = np.array([[chg(tk, t) for tk in TASKS] for t in TOOLS])
fig, ax = plt.subplots(figsize=(9, 5))
fig.subplots_adjust(left=0.18, right=0.97, top=0.80, bottom=0.14)
im = ax.imshow(M, cmap="RdBu_r", vmin=-40, vmax=40, aspect="auto")
for i in range(len(TOOLS)):
    for j in range(4):
        v = M[i, j]
        ax.text(j, i, f"{cz(v)} %", ha="center", va="center", fontsize=12,
                fontweight="bold" if abs(v) >= 15 else "normal", color="white" if abs(v) > 25 else "black")
ax.set_xticks(range(4)); ax.set_xticklabels([TNAME[t] for t in TASKS], fontsize=10.5)
ax.set_yticks(range(len(TOOLS))); ax.set_yticklabels([NAME[t] for t in TOOLS])
ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
fig.suptitle("Změna ceny proti běhu bez doplňků", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.89, "Modrá = levnější, červená = dražší. Medián tří běhů, studená cena. Rozdíly kolem 10 % jsou v šumu,\n"
         "spolehlivý je jen směr, který se opakuje přes úlohy.", fontsize=10, color="#555", va="top")
save(fig, "04_zmena_ceny_mapa")

# 5 CLAUDE.md
fig, ax = plt.subplots(figsize=(9, 5.2))
fig.subplots_adjust(left=0.10, right=0.97, top=0.78, bottom=0.20)
pairs = [("01-priority-queue", "claude-md-lean", "01 oprava chyby\n67 KB → 7 KB"),
         ("02-releases", "claude-md-full", "02 refaktoring\n7 KB → 67 KB"),
         ("03-version-decoder", "claude-md-full", "03 nová funkce\n7 KB → 67 KB")]
for i, (t, cfg, lab) in enumerate(pairs):
    big_first = cfg == "claude-md-lean"
    for k, (c, name, col) in enumerate([("baseline", "67 KB" if big_first else "7 KB", "#7f7f7f"),
                                         (cfg, "7 KB" if big_first else "67 KB", "#e377c2" if big_first else "#7f7f7f")]):
        x = i * 3 + k
        v = r[(r.task == t) & (r.config == c)].cost_cold_usd
        size = "67 KB" if (big_first and k == 0) or (not big_first and k == 1) else "7 KB"
        color = "#555555" if size == "67 KB" else "#2ca02c"
        al = 1 if i == 0 else 0.35
        ax.scatter([x] * len(v), v, s=45, color=color, zorder=3, alpha=al)
        ax.hlines(v.median(), x - 0.3, x + 0.3, color=color, lw=2.5, alpha=al)
        ax.text(x, v.max() + 0.03, f"{v.median():.2f}".replace(".", ",") + " USD", ha="center", fontsize=10, alpha=al)
        ax.text(x, 0.08, size, ha="center", fontsize=10, color=color, fontweight="bold", alpha=al)
    ch = chg(t, cfg)
    ax.text(i * 3 + 0.5, 0.95, f"{cz(ch)} %", ha="center", fontsize=13, fontweight="bold",
            color="#2ca02c" if big_first else "#aaa")
    if not big_first:
        ax.text(i * 3 + 0.5, 0.90, "nesrovnatelné, viz text", ha="center", fontsize=9.5, color="#999", style="italic")
ax.set_xticks([0.5, 3.5, 6.5]); ax.set_xticklabels([p[2] for p in pairs])
ax.set_ylim(0, 1.02); ax.set_xlim(-0.8, 7.8); ax.set_ylabel("studená cena běhu, USD")
fig.suptitle("Kratší CLAUDE.md zlevnil krátkou opravu o třetinu", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.89, "Úloha 01: rozdíl 0,12 USD odpovídá ceně zápisu 29,5 tisíce tokenů do cache. Úlohy 02 a 03 nejsou srovnatelné:\n"
         "starší 67KB soubor nežádal dokumentaci, agent dělal méně práce. Úloha 04 vynechána (2 ze 3 běhů neprošly testy).", fontsize=10, color="#555", va="top")
save(fig, "05_claude_md")

# 6 40 MB vs kontext
fig, ax = plt.subplots(figsize=(9, 5.2))
fig.subplots_adjust(left=0.02, right=0.98, top=0.80, bottom=0.08)
ax.set_aspect("equal"); ax.axis("off")
big = 40_000_000; ctx_max = 60_000; ctx_med = 38_000
S = 10.0
ax.add_patch(Rectangle((0, 0), S, S, color="#d9d9d9"))
s_max = S * np.sqrt(ctx_max / big); s_med = S * np.sqrt(ctx_med / big)
ax.add_patch(Rectangle((0.3, 0.3), s_max, s_max, color="#d62728"))
ax.text(0.3 + s_max + 0.25, 0.3 + s_max / 2, "← co se dostalo do kontextu: nejvýš 60 tisíc znaků (0,15 %)",
        va="center", fontsize=11.5, color="#d62728", fontweight="bold")
ax.text(S / 2, S / 2 + 1.2, "data k dispozici agentovi:\ncca 40 MB", ha="center", va="center", fontsize=16, color="#555")
ax.text(S / 2, S / 2 - 0.9, "303 HTML specifikací, 1,5MB JSON, log", ha="center", va="center", fontsize=11, color="#777")
ax.text(S + 0.6, 7.5, "Agent ve všech konfiguracích\nčetl data po kouscích:\ngrep, výřezy řádků, krátké\nskripty vypisující počty.\n\n"
        "Největší jednotlivý výstup\n(45 tisíc znaků) byl zdrojový\nkód, žádná data.\n\nNástroje na zkracování výstupů\nneměly co zkracovat.",
        va="top", fontsize=11, color="#333")
ax.set_xlim(-0.1, S + 7.5); ax.set_ylim(-0.1, S + 0.1)
fig.suptitle("Úloha 04: 40 MB dat na disku, do kontextu prošlo 0,15 %", x=0.01, ha="left", fontsize=14, fontweight="bold")
fig.text(0.01, 0.895, "Plochy jsou ve skutečném poměru.", fontsize=10, color="#555", va="top")
save(fig, "06_objemna_data")

# 7 Kvalita na úloze 04
q = r[(r.task == "04-glossary-extract") & (r.config.isin(["baseline"] + TOOLS))].copy()
base_med = q[q.config == "baseline"].cost_cold_usd.median()
q["rel"] = (q.cost_cold_usd / base_med - 1) * 100
rng = np.random.default_rng(3)
fig, ax = plt.subplots(figsize=(9, 5.4))
fig.subplots_adjust(left=0.10, right=0.70, top=0.80, bottom=0.14)
for c in ["baseline"] + TOOLS:
    g = q[q.config == c]
    for _, row in g.iterrows():
        y = row.review_correctness + rng.uniform(-0.09, 0.09)
        if row.hidden_tests_pass:
            ax.scatter(row.rel, y, s=70, color=COL[c], edgecolor="white", linewidth=0.6, zorder=3)
        else:
            ax.scatter(row.rel, y, s=110, marker="X", color=COL[c], zorder=4)
ax.axvline(0, color="#999", lw=0.8, ls="--")
ax.set_xlabel("cena proti mediánu běhu bez doplňků, %  (vlevo = levnější)")
ax.set_ylabel("hodnocení správnosti v review (1–5)")
ax.set_ylim(1.5, 5.4)
h = [Line2D([], [], marker="o", ls="", color=COL[c], label=NAME[c], markersize=8) for c in ["baseline"] + TOOLS]
h.append(Line2D([], [], marker="X", ls="", color="#333", label="neprošel skrytými testy", markersize=9))
ax.legend(handles=h, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=10.5)
ax.annotate("Ponytail: levný běh,\nale review našlo chybu,\nkterou testy nepokrývají", xy=(q[(q.config == "ponytail")].sort_values("review_correctness").iloc[0].rel, 2.0),
            xytext=(-45, 2.35), fontsize=9.5, color=COL["ponytail"], arrowprops=dict(arrowstyle="->", color=COL["ponytail"]))
fig.suptitle("Úloha 04: levnější řešení může být i horší", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.89, "Jediná úloha, na které se kvalita lišila. Každý bod je jeden běh.", fontsize=10, color="#555", va="top")
save(fig, "07_kvalita_uloha04")

# 8 Rozptyl, úloha 01
cfgs = ["baseline", "ponytail", "context-mode", "claude-md-lean"]
g = r[(r.task == "01-priority-queue") & (r.config.isin(cfgs))]
fig, ax = plt.subplots(figsize=(9, 5))
fig.subplots_adjust(left=0.10, right=0.97, top=0.78, bottom=0.14)
for i, c in enumerate(cfgs):
    v = g[g.config == c]
    ax.scatter([i - 0.13] * len(v), v.cost_usd, s=60, facecolor="none", edgecolor=COL[c], linewidth=1.6, zorder=3)
    ax.scatter([i + 0.13] * len(v), v.cost_cold_usd, s=60, color=COL[c], zorder=3)
    lo, hi = v.cost_usd.min(), v.cost_usd.max()
    ax.vlines(i - 0.13, lo, hi, color=COL[c], lw=1, alpha=0.5)
ax.set_xticks(range(len(cfgs))); ax.set_xticklabels([NAME[c] for c in cfgs])
ax.set_ylabel("cena běhu, USD"); ax.set_ylim(0, 0.58)
h = [Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor="#333", label="účtovaná cena", markersize=8),
     Line2D([], [], marker="o", ls="", color="#333", label="studená cena (bez cizí cache)", markersize=8)]
ax.legend(handles=h, loc="upper left", frameon=False, fontsize=10.5)
ax.annotate("stejná úloha, stejný nástroj:\n0,15 až 0,52 USD", xy=(2 - 0.13, 0.15), xytext=(0.95, 0.03), fontsize=9.5,
            arrowprops=dict(arrowstyle="->", color="#555"))
fig.suptitle("Proč nestačí jeden běh", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.89, "Úloha 01, tři opakování. Účtovaná cena kolísá podle toho, jestli předtím běžel podobný běh\n"
         "a nechal v cache stejný začátek promptu. Studená cena tenhle vliv odstraňuje.", fontsize=10, color="#555", va="top")
save(fig, "08_rozptyl_behu")
print("hotovo", sorted(os.listdir(OUT)))
