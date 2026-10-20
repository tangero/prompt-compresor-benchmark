# Benchmark nástrojů pro úsporu tokenů v Claude Code

Zadání pro sestavení samostatného testu a podklady k článku.
Verze: 2026-10-19. Autor zadání: Patrick Zandl.

---

## 0. Shrnutí pro agenta

Postav samostatný harness (nový repozitář `cc-token-bench`), který na snapshotech projektu 3gpp-explorer změří, kolik reálně ušetří populární doplňky Claude Code a jestli to nezhorší kvalitu práce. Výstupem jsou surová data, souhrnné tabulky a grafy pro článek.

Pracuj po etapách a na označených místech se **zastav a počkej na potvrzení** (oddíl 11). Do produkce 3gpp-explorer se nic nenasazuje, nic se nepushuje do jeho `main`, agenti v testu nemají přístup k produkčnímu API ani přihlašovacím údajům.

Rozhodnutí, která doplní Patrick:
- přihlášení: **[API klíč / předplatné]** (doporučeno API klíč)
- rozpočtový strop celého benchmarku: **[X USD]** (doporučeno 200 USD, upřesní se po pilotu)

---

## 1. Kontext: článek

Dvoudílný seriál pro Marigold.cz / Vibecoding.cz:

1. **Díl 1 (tento test):** nástroje a postupy, které slibují úsporu tokenů v Claude Code. Co slibují, co ukázala nezávislá měření, co ukázal náš vlastní test, komu se co hodí.
2. **Díl 2 (později):** orchestrace agentů a více sessions (Herdr, Claude Squad, Conductor, Agent Teams, subagenti). Mimo rozsah tohoto testu.

Hlavní teze dílu 1: nástroje slibují úspory 50-95 %, nezávislá měření ukazují řádově 5-40 %. Příčina je obvykle stejná: nástroj šetří jen jednu kategorii tokenů a uvádí procento z ní, uživatel ale platí za všechny.

### 1.1 Osnova dílu 1

1. Kam tokeny v Claude Code tečou (systémový prompt a cache, definice nástrojů a MCP, čtení souborů, výstupy shellu, výstupní text, reasoning). Pětihodinový a týdenní limit předplatného.
2. Vestavěné funkce jako první krok: volba modelu a effortu, subagenti s omezenými nástroji a levnějším modelem, `/clear`, `/compact`, krátký CLAUDE.md, vypnuté nepoužívané MCP servery.
3. Komprese výstupů nástrojů: RTK, Context Mode, Headroom, Token Savior. Jejich vzájemný překryv.
4. Úprava stylu výstupu: Caveman, Ponytail, claude-token-efficient.
5. Levnější model místo komprese: claude-code-router.
6. Jak si úsporu změřit sám (ccusage, Claude-Code-Usage-Monitor, `--output-format json`).
7. **Náš test** na reálném projektu: metodika, výsledky, omezení.
8. Doporučené sestavy pro tři typy čtenářů: sólo vývojář na předplatném, platba přes API, tým s paralelními agenty.
9. Most do dílu 2: paralelní agenti spotřebu zvyšují, každý načítá kontext znovu.

### 1.2 Přehled nástrojů: sliby a nezávislá měření

| Nástroj | Co dělá | Slib autorů | Nezávislé měření | Poznámka |
|---|---|---|---|---|
| Caveman (JuliusBrussee/caveman) | skill, telegrafický styl výstupu | 65-75 % výstupních tokenů | JetBrains: −8,5 % výstupních tokenů, cca −10 % ceny, kvalita beze změny | výstupní tokeny tvoří podle Implicator.ai jen 0,6-2,5 % účtovaných tokenů; sub-skill caveman-compress zkracuje CLAUDE.md (slib cca 46 % vstupu) |
| Ponytail (DietrichGebert/ponytail) | skill, agent píše méně kódu, preferuje stdlib a nativní funkce | −54 % kódu, −22 % tokenů, −20 % ceny, −27 % času | JetBrains (80 párových úloh): −15 % kódu, −10,3 % ceny, −11 % času | model ho v testu JetBrains sám ani jednou neaktivoval |
| claude-token-efficient (drona23) | jeden CLAUDE.md s pravidly stručnosti | původně 63 % méně slov | vlastní reprodukovatelný benchmark projektu: 4 % (Haiku), 12 % (Sonnet), 7 % (Opus) výstupu; computingforgeeks: −40 % ceny | ukázka, jak výsledek závisí na metodice |
| RTK (rtk-ai/rtk) | proxy pro výstupy shellových příkazů | 60-90 % výstupu bashe | bez nezávislé studie | README sám uvádí, že jde o snížení výstupu bashe, účet klesne méně; vestavěné Read/Grep/Glob hooks obcházejí |
| Context Mode (mksglu/claude-context-mode) | MCP server, velké výstupy zpracuje v sandboxu, do kontextu jen shrnutí | 98 % (315 KB → 5,4 KB) | nenalezeno | překrývá se s RTK a Headroom |
| Headroom (chopratejas/headroom) | lokální proxy komprimující celý kontext | 60-95 % u JSON, 15-20 % u kódu | nenalezeno | v režimu OAuth/předplatné jen bezztrátová komprese; deklarovaná latence 1-5 ms |
| Token Savior (Mibayy/token-savior) | MCP s nástroji pro navigaci v kódu, paměť, přepis bash příkazů | 94 % | computingforgeeks: nejlepší z 10 nástrojů; nezávislé přeměření 2026-08 | jediný s reprodukovatelným harnessem |
| claude-code-router (musistudio) | směruje požadavky na jiné (levnější) modely | velká úspora ceny | - | mění se kvalita modelu; není plně kompatibilní se všemi funkcemi Claude Code |

Zdroje:
- JetBrains, test Ponytail (a odkaz na test Caveman): https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/
- Implicator.ai, Caveman: https://www.implicator.ai/caveman-claude-code-skill-cuts-output-20-your-bill-barely-notices-2/
- computingforgeeks, 10 testovaných nástrojů: https://computingforgeeks.com/reduce-claude-code-token-usage-tools/
- Přehled slibů a studií (průběžně aktualizovaný): https://cc.bruniaux.com/token-savings/
- RTK: https://github.com/rtk-ai/rtk
- Context Mode: https://github.com/mksglu/claude-context-mode
- Headroom: https://pypi.org/project/headroom-ai/
- Token Savior: https://github.com/Mibayy/token-savior
- Pillitteri, 10 repozitářů: https://pasqualepillitteri.it/en/news/1181/summary_large_image

Pro článek: všechna čísla v tabulce před publikací ověř proti aktuální verzi zdrojů, projekty mění README i benchmarky.

---

## 2. Cíl a otázky testu

Pro každou konfiguraci zjistit oproti baseline:
1. Změnu ceny běhu (hlavní metrika).
2. Změnu jednotlivých kategorií tokenů (nové vstupní, čtení z cache, zápis do cache, výstupní).
3. Změnu času a počtu tahů.
4. Změnu kvality: úspěšnost akceptačních testů, skóre z nezávislého review (Codex), míru neúspěšných běhů.

Test je **orientační**, statisticky průkazný nebude. V článku se tak bude prezentovat: „malý test na reálném projektu, ukazuje směr".

---

## 3. Projekt pro test: 3gpp-explorer

- Monorepo pnpm, TypeScript, Node 22.
- Web: Next.js (static export) na Cloudflare Pages, React, Tailwind.
- API: Hono na Cloudflare Workers. `apps/api/src/index.ts` má cca 11 550 řádků. D1 se v testech nahrazuje SQLite (`createSqliteTestD1`).
- Pipeline: `packages/spec-pipeline`.
- Testy: `node:test` přes `tsx`. Spec-pipeline 96 testovacích souborů, API 56, web unit testy (render přes `renderToStaticMarkup`), Playwright e2e.
- **Zákaz:** `pnpm build` webu volá produkční API. V testu se nespouští, agentům se v zadání výslovně zakáže a v kontejneru nebude síťový přístup k produkci.
- Repozitář má v `.claude/` jen skills, žádné hooks ani `settings.json`.
- CLAUDE.md projektu nařizuje commitovat dokumentaci do `main` a pushovat. V testu bez remote a bez přihlašovacích údajů. Pravidla o `docs/changes.md` ponech pro všechny konfigurace stejná, `docs/` se počítá zvlášť od diffu kódu.

---

## 4. Úlohy

Každá úloha zatěžuje převážně jiný typ spotřeby. Čisté oddělení kategorií nedostaneme, cílem je rozdílný profil.

### Úloha 1: oprava souběhu ve frontě prioritních běhů (převážně shell)

- **Výchozí stav:** `0b68348^` (rodič skutečné opravy).
- **Zadání jako issue:**
  - retry neúspěšného prioritního běhu projde, i když ve frontě čeká limit 20 prioritních běhů (má vrátit 429 `priority_queue_full`),
  - dvě souběžná založení prioritního běhu při 19 čekajících projdou obě.
- **Skryté akceptační testy:** dva testy z opravy (`retry of a priority run respects the cap`, `concurrent priority creates at the cap…`). Třetí test z commitu (povýšení čekajícího běhu) vynech, jde o novou funkci.
- **Dál musí projít:** `pnpm --filter @3gpp/api test`, `typecheck`.
- **Očekávané chování agenta:** reprodukce souběhu (D1 mock, který mezi příkazy předá řízení), opakované spouštění 56souborové sady s rozvláčným výstupem. Zde by se měly projevit RTK a Context Mode.
- **Známé slabé místo:** zámek v JavaScriptu (mutex) testem projde, na skutečné D1 nefunguje. Zachytí jen review, proto má review pro tuto úlohu samostatné kritérium.

### Úloha 2: Rel-21 a jeden zdroj seznamu releasů (převážně čtení)

- **Výchozí stav:** pevný commit `main` [HASH doplní agent při přípravě a zapíše do manifestu].
- **Problém:** seznam releasů je natvrdo na mnoha místech:
  - web: `SpecificationsClient.tsx`, `admin/pipeline/page.tsx`, `admin/runs/page.tsx`, `releaseMeta.ts`, `releaseYears.ts`,
  - API: dvakrát `releaseOrder` v `index.ts`, mapa roků, `admin-operations.ts`,
  - pipeline: `release-eras.ts`.
  - Údaje si odporují: web uvádí u Rel-20 rok 2026, API 2027.
- **Zadání:** v `packages/types` vytvořit `RELEASES` (pořadí a rok) a `releaseFromVersionCode()`, přidat Rel-21 (znak `l`), nahradit kopie ve webu, API a pipeline. `apps/downloader` výslovně mimo rozsah. Rok Rel-20 je v zadání určen předem: **[2026 / 2027 - doplní Patrick]**.
- **Skryté akceptační testy:**
  - `l00` → Rel-21, `k10` → Rel-20, `a00` → Rel-10, `ib0` → Rel-18,
  - statický test: v `apps/web/src`, `apps/api/src` a `packages/spec-pipeline/src` nezůstane literál pole s 5 a více po sobě jdoucími `Rel-N` (datová pole typu `releases: ['Rel-19', 'Rel-20']` projdou),
  - existující sady a typecheck zelené.

### Úloha 3: dekodér verzí 3GPP (převážně výstup)

- **Výchozí stav:** stejný commit jako úloha 2.
- **Zadání:** stránka `/tools/version-decoder/` a čistá funkce `decodeSpecFile()` v `apps/web/src/lib/`. Vstup `38331-j40.zip`, `38331-j40` nebo `TS 38.331 V19.4.0`. Výstup: číslo specifikace, release, major/technical/editorial verze, odkaz na kanonickou URL `/specification/Rel-19/38.331/`. Klientská komponenta se vstupním polem, anglický vysvětlující text o verzování 3GPP (aspoň 3 sekce). Na závěr agent napíše shrnutí návrhu.
- **Skryté akceptační testy:**
  - tabulka cca 12 vstupů včetně okrajových (`ib0` = 18.11.0, neplatný vstup → chyba),
  - render komponenty obsahuje očekávaný release a odkaz,
  - výstup neobsahuje české znaky (web je EN-only).
- Fixtury převzít z `specUrl.ts`, `seriesMapping.ts`, `catalog-versions.ts`.
- **Pozor:** tabulka v CLAUDE.md mapuje znak `3` na Rel-4. Podle konvence 3GPP verze V3.x patří k R99, Rel-4 začíná znakem `4`. Před zápisem do testů ověř a případně oprav CLAUDE.md ve snapshotu (stejně pro všechny konfigurace).
- Většinu výstupních tokenů tvoří kód, úspora Cavemanu tu proto bude menší, než naznačuje kategorie.

### Pravidla pro všechny úlohy

- Všechny názvy funkcí, signatury a cesty, na kterých skryté testy závisí, musí být uvedené v `prompt.md`.
- Skryté testy ověřují chování přes veřejné rozhraní, nekódují stylová rozhodnutí.
- Skryté testy na výchozím stavu **padají** a na referenčním řešení **procházejí**. Ověřit před pilotem.
- Referenční řešení pro úlohy 2 a 3 napíše agent, Patrick je zreviduje (riziko, že testy zvýhodní styl Claude).
- Skryté testy leží mimo kontejner agenta a kopírují se dovnitř až ve fázi ověření.

---

## 5. Konfigurace

| ID | Obsah | Aktivace |
|---|---|---|
| `baseline` | čistý Claude Code | - |
| `caveman` | plugin Caveman | výslovná aktivace `/caveman` nebo ekvivalent v headless režimu |
| `ponytail` | plugin Ponytail | výslovná aktivace `/ponytail` nebo ekvivalent |
| `rtk` | RTK s hookem | `rtk init -g`, ověřit `rtk gain` |
| `context-mode` | MCP server Context Mode (+ jeho skill, pokud se instaluje jako plugin) | automaticky |
| `headroom` | Headroom proxy | `ANTHROPIC_BASE_URL` na proxy |

Volitelné rozšíření po hlavním běhu (jen pokud zbude rozpočet): `token-savior`, `token-efficient-md`, kombinace `rtk+caveman+ponytail`.

Instalační příkazy ověř v aktuálním README každého projektu a **zafixuj konkrétní verzi** (tag nebo commit). Orientačně:
- Caveman: `claude plugin marketplace add JuliusBrussee/caveman` a `claude plugin install caveman@caveman`
- Ponytail: `/plugin marketplace add DietrichGebert/ponytail` a `/plugin install ponytail@ponytail`
- RTK: `cargo install --git https://github.com/rtk-ai/rtk` (nebo install.sh) a `rtk init -g`
- Context Mode: `claude mcp add context-mode -- npx -y context-mode`
- Headroom: `pip install "headroom-ai[proxy]"` a `headroom proxy --port 8787`

### Izolace konfigurací

- Každá konfigurace má **vlastní image kontejneru**. Samotný `CLAUDE_CONFIG_DIR` nestačí (RTK = hook v shellu, Headroom = proxy a proměnná prostředí, Context Mode = MCP server).
- Caveman a Ponytail se samy neaktivují. V každém běhu z transkriptu ověř, že se instrukce skillu dostala do kontextu. Běh bez ověřené aktivace = `invalid`.
- U RTK ověř, že hook příkazy skutečně zachytil (`rtk gain` po běhu, uložit do logu).
- U Headroom ulož jeho statistiky (`headroom stats` nebo ekvivalent) a latenci proxy.

### Společné pro všechny konfigurace

- Model `claude-sonnet-5-5`, effort medium. Ověř, že se nastavení skutečně použije, a zapisuj do logu.
- Pevná verze Claude Code, `DISABLE_AUTOUPDATER=1`.
- Headless: `claude -p --output-format json`, pevné `--allowedTools` nebo `--permission-mode bypassPermissions` (jen v izolovaném kontejneru), `--max-turns` [návrh: 80] a časový limit [návrh: 45 min].
- `pnpm install` proběhne při sestavení image, nepočítá se do běhu.
- Kontejner bez síťového přístupu kromě Anthropic API (a u Headroom lokální proxy). Žádný remote v gitu, žádné tokeny GitHubu ani Cloudflare.

---

## 6. Průběh běhu

1. Z image konfigurace spusť kontejner.
2. Do něj zkopíruj **čistý snapshot** úlohy: soubory výchozího commitu, `git init`, jediný commit, bez historie a bez remote. (Git worktree sdílí objekty a refy s hlavním repozitářem, agent by si u úlohy 1 přečetl řešení přes `git show 0b68348`.)
3. Spusť agenta s `prompt.md`.
4. Po skončení: ulož JSON výstup, transkript, diff, statistiky nástroje.
5. Zkopíruj skryté testy, spusť `verify.sh` (skryté testy, sada, typecheck).
6. Spusť Codex review (oddíl 8).
7. Zapiš řádek do `results.jsonl`.

---

## 7. Plán běhů

- 3 úlohy × 6 konfigurací × 3 opakování = **54 běhů**.
- Pořadí všech běhů **náhodně zamíchat s pevným seedem**, seed uložit. Nespouštět po blocích konfigurací (prompt cache sdílí začátek promptu mezi běhy do 5 minut a zvýhodnila by pozdější běhy).
- Rozpočet: skript sleduje průběžnou cenu, při 80 % stropu se zastaví a ohlásí stav.
- **Neúspěšné běhy** (`max_turns`, `timeout`) se nevyřazují. Počítají se jako neúspěch, jejich spotřeba se zahrnuje, míra neúspěchů se vykazuje pro každou konfiguraci zvlášť.
- `invalid` běhy (neověřená aktivace, chyba harnessu) se opakují a v reportu se uvede jejich počet.

---

## 8. Codex review

Po každém běhu:
1. Diff proti výchozímu stavu **bez `docs/`**, bez značek prozrazujících konfiguraci (komentáře `// ponytail:` a podobné), bez commit zpráv. Codex dostane jen kód, zadání úlohy a hodnotící tabulku.
2. Codex v režimu jen pro čtení, pevný model a verze, výstup JSON.
3. Hodnotící tabulka, každé kritérium 1-5 se stručným zdůvodněním:
   - `correctness` - správnost řešení zadání
   - `concurrency_security` - bezpečnost a souběh (u úlohy 1 výslovně: funguje řešení na skutečné D1, nebo jen v jednom procesu?)
   - `error_handling` - ošetření chyb a okrajových případů
   - `readability` - čitelnost a udržovatelnost
   - `scope` - držení se zadání (nic navíc, nic chybějícího)
4. Review **dvakrát**. Pokud se hodnocení liší o víc než 1 bod v kterémkoli kritériu, spusť třetí a označ běh příznakem `review_disagreement`.
5. Codex nesmí znát název konfigurace ani identifikátor, který by ji prozradil (použij náhodné ID diffu).

Prompt pro review ulož do repozitáře jako `review/prompt.md`, aby byl součástí metodiky v článku.

---

## 9. Data

### 9.1 `results.jsonl`, jeden řádek na běh

```
run_id, seed_position, task, config, repetition,
model, effort, cc_version, tool_version, auth_mode,
status            # ok | max_turns | timeout | invalid
cost_usd,
input_tokens, cache_read_tokens, cache_write_tokens, output_tokens,
duration_s, turns,
hidden_tests_pass, suite_pass, typecheck_pass,
diff_loc_code, diff_loc_docs,
tool_stats        # rtk gain, headroom stats, ověření aktivace skillu
review_scores     # všechna hodnocení, ne jen průměr
review_disagreement
```

### 9.2 Další výstupy

- surové transkripty a JSON výstupy Claude Code (`runs/<run_id>/`),
- diffy a výstupy `verify.sh`,
- `manifest.json`: commity úloh, verze všech nástrojů, verze Claude Code a Codexu, seed, typ přihlášení, rozpočet.

### 9.3 Poznámka k ceně

Cena z `--output-format json` je přepočet podle ceníku API. Na předplatném jde o orientační číslo. Porovnávej **cenu**, součet tokenů zkresluje: dominuje levné čtení z cache a úspora nových vstupních tokenů se v ceně projeví jinak než v počtu.

---

## 10. Analýza a report

Pro každou úlohu a konfiguraci:
- medián a rozptyl (min-max) ceny, času a tahů,
- relativní změna mediánu ceny proti baseline téže úlohy,
- rozpad tokenů po kategoriích (kde přesně nástroj šetří),
- úspěšnost skrytých testů, sady a typechecku,
- míra neúspěšných běhů,
- průměrné skóre review po kritériích, počet `review_disagreement`.

Souhrn přes úlohy: tabulka konfigurace × (změna ceny, změna času, úspěšnost, skóre review).

Grafy pro článek (PNG/SVG a data v CSV):
1. Slib autorů vs. nezávislá měření vs. náš výsledek (sloupce po nástrojích).
2. Rozpad ceny po kategoriích tokenů, baseline vs. konfigurace.
3. Cena vs. kvalita (bodový graf, každý bod jeden běh).
4. Rozptyl opakovaných běhů (ukázka, proč nestačí jeden běh).

Report `REPORT.md` v češtině, věcně: metodika, výsledky, omezení (malý vzorek, jeden projekt, jeden model, jeden recenzent), co z toho plyne pro jednotlivé typy uživatelů.

---

## 11. Etapy a body zastavení

1. **Příprava:** repozitář `cc-token-bench`, snapshoty úloh, `prompt.md`, skryté testy, `verify.sh`, referenční řešení úloh 2 a 3. Ověření: testy na výchozím stavu padají, na referenčním řešení procházejí.
   → **STOP:** pošli skryté testy, signatury a referenční řešení k revizi.
2. **Harness:** image konfigurací, řídicí skript, Codex review, zápis dat.
3. **Pilot:** úloha 1, konfigurace `baseline` a `rtk`, dva běhy od každé. Ověř izolaci (čistý snapshot, žádný remote, žádné přihlašovací údaje), zachycení příkazů RTK (`rtk gain`), uložení všech polí včetně review, skutečnou cenu a délku běhu.
   → **STOP:** pošli výsledky pilotu, odhad ceny a délky plného běhu a seznam všeho, co fungovalo jinak, než se čekalo.
4. **Plný běh** (54 běhů) po potvrzení.
5. **Analýza a report.**
   → **STOP:** pošli `REPORT.md` a grafy.

---

## 12. Struktura repozitáře

```
cc-token-bench/
  README.md              # jak test spustit a reprodukovat
  manifest.json
  tasks/
    01-priority-queue/   prompt.md, hidden-tests/, verify.sh, snapshot.ref
    02-releases/         prompt.md, hidden-tests/, verify.sh, snapshot.ref, reference/
    03-version-decoder/  prompt.md, hidden-tests/, verify.sh, snapshot.ref, reference/
  configs/
    baseline/  caveman/  ponytail/  rtk/  context-mode/  headroom/
      Dockerfile, setup.sh, activate.md (pokud je potřeba aktivace)
  review/
    prompt.md, rubric.json, run-review.sh
  runner/
    plan.py (zamíchání, seed), run.py, budget.py
  analysis/
    analyze.py, charts/
  runs/                  # surová data, mimo git nebo v LFS
  results.jsonl
  REPORT.md
```

Repozitář bude veřejný jako součást článku (čtenář si test zopakuje), proto v něm nesmí být žádné přihlašovací údaje ani produkční URL 3gpp-explorer.
