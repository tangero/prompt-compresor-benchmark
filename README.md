# prompt-compresor-benchmark

Benchmark doplňků Claude Code, které slibují úsporu tokenů: Caveman, Ponytail, RTK, Context Mode
a Headroom. Každý doplněk řešil v izolovaném kontejneru stejné programátorské úlohy jako čisté
Claude Code. Měří se cena, rozpad tokenů, čas a kvalita řešení (skryté testy a review jiným modelem).

> *English summary: an A/B harness that runs Claude Code with and without token-saving add-ons
> (Caveman, Ponytail, RTK, Context Mode, Headroom) on identical tasks in isolated Docker
> containers and compares cost, token categories, time and solution quality. Docs are in Czech;
> the scripts are plain Python/Bash and the raw data is in `results.jsonl`.*

**Výsledky:** [REPORT.md](REPORT.md). Zjednodušeně: většinu ceny tvoří kontext, který agent nese
z tahu do tahu, ne výstup ani výsledky nástrojů. Spolehlivě ušetřil jen Ponytail, a to s výhradou
ke kvalitě. Ostatní doplňky cenu v průměru nezměnily (±5 %). Zadání benchmarku je
v [docs/cc-token-bench-zadani.md](docs/cc-token-bench-zadani.md).

## Co v repozitáři je a co ne

| Je | Není |
|---|---|
| harness (Docker obrazy, gateway, runner, review, ověření) | zdrojový kód projektu, na kterém úlohy běžely |
| 4 úlohy: zadání, skryté testy, `verify.sh`, referenční řešení | CLAUDE.md projektu (obsahuje interní údaje) |
| `results.jsonl` (všechny běhy) a tokeny po voláních API v `runs/*/metrics.json` | přepisy relací, diffy agentů a výstupy příkazů |
| analýza a grafy (`analysis/`) | |

Úlohy vznikly z reálného, **neveřejného** projektu 3gpp-explorer. Snapshot kódu proto
v repozitáři není a čtyři původní úlohy si sami nespustíte. Máte tři možnosti:

1. **Přepočítat analýzu** z publikovaných dat (minuta, zdarma).
2. **Spustit harness na vlastním repozitáři** s vlastní úlohou (viz níže).
3. Číst úlohy jako vzor: `tasks/*/prompt.md`, skryté testy a `verify.sh` ukazují, jak úlohu
   postavit, aby se dala ověřit strojově.

## 1. Přepočítání analýzy

```bash
uv run --with matplotlib analysis/analyze.py       # → analysis/out/*.csv, summary.md, charts/
uv run --with matplotlib --with pandas --with numpy analysis/article_charts.py   # grafy k článku
```

Výstup má odpovídat souborům v `analysis/out/`. Studená cena (cizí čtení z cache přeceněné
na zápis) se počítá z `runs/*/attempt-*/metrics.json`. Postup je popsaný v REPORT.md v kapitole Metodika.

## 2. Spuštění na vlastním repozitáři

### Požadavky

- Docker (stačí Docker Desktop; obrazy mají dohromady několik GB),
- Python 3.11+ a [uv](https://docs.astral.sh/uv/) pro analýzu,
- předplatné Claude (Pro nebo Max) a dlouhodobý OAuth token z `claude setup-token`,
- git, bash; pro `scripts/check-tasks.sh` také Node 22+ a corepack.

Base obraz obsahuje Node 22 a pnpm. Pro projekt v jiném ekosystému upravte `docker/base/Dockerfile`
a `docker/task/Dockerfile`, případně `task.Dockerfile` ve složce úlohy.

### Postup

```bash
# 0) token: spusťte `claude setup-token` a výsledek uložte do souboru, který čte jen gateway
mkdir -p ~/.config/cc-token-bench
printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' 'sem-vložte-token' > ~/.config/cc-token-bench/env
chmod 600 ~/.config/cc-token-bench/env

# 1) vlastní úloha (návod v docs/vlastni-uloha.md); původní úlohy přesuňte stranou,
#    plánovač bere všechny složky v tasks/
mkdir -p tasks-orig && git mv tasks/0* tasks-orig/
#    … vytvořte tasks/01-moje-uloha/{prompt.md,snapshot.ref,verify.sh,hidden-tests/,reference.patch}

# 2) kontrola úlohy: skryté testy musí na výchozím stavu padat a na referenci projít
SOURCE_REPO=~/cesta/k/repozitari scripts/check-tasks.sh /tmp/check 01-moje-uloha

# 3) obrazy (poprvé zhruba hodina); claude-md-* vynechte, pokud nedáváte vlastní CLAUDE.md
SOURCE_REPO=~/cesta/k/repozitari scripts/build-images.sh baseline caveman ponytail rtk context-mode headroom
#    jen vybrané úlohy: TASKS="01-moje-uloha" scripts/build-images.sh baseline rtk

# 4) ověření, že se každý doplněk opravdu aktivoval (~1 USD)
scripts/smoke-configs.py --task 01

# 5) plán a běhy: úlohy × konfigurace × opakování, náhodně promíchané
runner/plan.py --seed 42 --out plan.json
runner/run.py plan.json --budget 50        # navazuje, hotové běhy přeskočí
runner/rereview.py                         # doplní review, které selhalo

# 6) analýza
uv run --with matplotlib analysis/analyze.py
```

Pro běh bez dozoru je tu `scripts/night.sh plan.json`: nejdřív pustí pojistný běh,
pak celý plán, review a analýzu. Stav průběžně zapisuje do `build/NIGHT-STATUS.md`.

**Kolik to stojí:** jeden běh na středně velké úloze stál v přepočtu na ceník API 0,2–1,5 USD.
Celý benchmark vyšel zhruba na 38 USD a z týdenního limitu předplatného spotřeboval asi
2 procentní body. Runner se zastaví, když útrata dosáhne 80 % hodnoty `--budget`.

Plán běhy záměrně míchá. Kdyby běžely po blocích konfigurací, sdílená prompt cache by
zvýhodnila pozdější běhy téže konfigurace. Proto analýza počítá také studenou cenu
(viz REPORT.md).

### Snapshot úlohy

`scripts/make-snapshot.sh` vezme soubory commitu ze `snapshot.ref` v repozitáři `SOURCE_REPO`
a vytvoří z nich nový git s jediným commitem, tagem `base` a bez remote. Agent tak nevidí historii
(u úlohy 01 by si jinak přečetl řešení přes `git show`). Skryté testy se do snapshotu
zkopírují až při ověření.

## Konfigurace

| Konfigurace | Verze | Ověření aktivace (jinak je běh `invalid`) |
|---|---|---|
| baseline | – | žádný plugin ani MCP server |
| caveman | v4.0.1 (`d262ab3`), `CAVEMAN_DEFAULT_MODE=caveman` | banner v SessionStart hooku |
| ponytail | v5.3.2 (`16352ac`) | banner v SessionStart hooku |
| rtk | v1.0.1, `rtk init -g --auto-patch` | `rtk gain`: zachycené příkazy > 0 (pokud agent použil Bash) |
| context-mode | v1.0.169 (`589d821`), plugin | MCP server připojený v `system/init` |
| headroom | 0.41.0, proxy v kontejneru → gateway | `/stats`: api_requests > 0 |
| claude-md-lean / -full | pokus s délkou CLAUDE.md | `CLAUDE.md` do složky konfigurace dodáte sami (původní vytvářel `scripts/prepare-claude-md.sh`) |

Společné nastavení: `claude -p --model claude-sonnet-5-5 --effort medium --max-turns 80
--max-budget-usd 15 --permission-mode bypassPermissions`, časový limit 45 min, Claude Code 2.1.303.
Novou konfiguraci přidáte jako `configs/<jméno>/Dockerfile` (`FROM ${TASK_IMAGE}`)
a `settings.json`. Kontrolu aktivace doplníte do `runner/run.py`.

## Architektura

```
docker/base      Node 22 (Debian trixie), pnpm 8.15.0, Claude Code 2.1.303, uživatel node
docker/task      snapshot úlohy + pnpm install (bez skrytých testů)
configs/<cfg>    doplněk nad obrazem úlohy → cc-bench-<NN>-<cfg>
docker/gateway   nginx, jediná cesta ven: api.anthropic.com; vkládá OAuth token
runner/          plán, spouštění, sběr metrik, review
review/          slepé review diffu jiným modelem (rubrika v review/rubric.json)
scripts/         snapshoty, obrazy, kontrola úloh, opětovné ověření
analysis/        souhrny, grafy, claims.json (sliby autorů doplňků)
```

Pro každý běh vznikne `runs/<run_id>/attempt-N/` se soubory:

| Soubor | Obsah |
|---|---|
| `stream.jsonl` | surový výstup |
| `metrics.json` | metriky běhu |
| `transcripts/` | přepisy relace |
| `diff.patch` | diff agenta |
| `review.diff` | diff pro review, bez `docs/` a se zakrytými značkami nástrojů |
| `verify/` | výsledky ověření |
| `review-*.json` | hodnocení z review |
| `gateway.jsonl` | požadavky na API |
| `row.json` | řádek výsledků |

Do `results.jsonl` jde jeden řádek na pokus. Kromě tokenů a ceny obsahuje rozpad zápisů do cache
5m/1h, thinking tokeny, počty a objem výsledků nástrojů, počet volání API, bajty přes gateway,
čerpání limitů předplatného, výsledky ověření a review.

`scripts/reverify.py --task NN` znovu ověří uložené diffy v čistém obraze bez sítě a při chybě IPC
spouštěče testů Node to zkusí znovu. Jeho výsledky mají v analýze přednost.

## Bezpečnost

- Kontejner agenta běží v síti `--internal`. Ven se dostane jen přes gateway, a ta pouští
  jen `api.anthropic.com`.
- Token zná jen gateway (`docker/gateway/default.conf.template`). Agent dostane zástupnou hodnotu,
  takže ho nemůže vypsat ani poslat jinam.
- Snapshot nemá remote, agent nic nepushne.
- Harness počítá s OAuth tokenem předplatného. Pro API klíč upravte gateway (hlavička
  `x-api-key` místo `Authorization`) a proměnné prostředí kontejneru v `runner/run.py`.
- Před zveřejněním vlastních výsledků zkontrolujte, co obsahuje `runs/`. Přepisy obsahují
  váš kód a výstupy příkazů. `.gitignore` z `runs/` pouští do gitu jen `metrics.json`;
  původní soubory obsahují i spuštěné příkazy, tyto zveřejněné jsou ořezané na tokeny.

## Původní úlohy

| Úloha | Profil spotřeby | Skryté testy |
|---|---|---|
| [01-priority-queue](tasks/01-priority-queue/prompt.md) | shell (56 testovacích souborů API, ~68 KB výstupu na běh) | 2 testy limitu prioritní fronty (retry, souběh) |
| [02-releases](tasks/02-releases/prompt.md) | čtení (seznam releasů v ~10 souborech) | `releaseFromVersionCode`, `RELEASES`, statická kontrola literálů |
| [03-version-decoder](tasks/03-version-decoder/prompt.md) | výstup (nová stránka a funkce) | 12 platných a 8 neplatných vstupů, render komponenty a stránky |
| [04-glossary-extract](tasks/04-glossary-extract/prompt.md) | objemná data (303 HTML specifikací 3GPP, 38 MB, 1,5MB JSON a log chybného běhu) | syntetické případy, celý korpus: dolní práh definic, ztráty a šum ≤ 1 %, zkratky beze ztráty |

Běhy proběhly 19.–20. 10. 2026: 72 hlavních (4 úlohy × 6 konfigurací × 3) a 12 v pokusu
s CLAUDE.md. Pilot je v `results-pilot.jsonl` a odložené kolizní běhy úlohy 04
v `results-04-collided.jsonl`.
