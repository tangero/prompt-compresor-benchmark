# Bug: extrakce glosáře ztrácí definice

Poslední běh extrakce glosáře nad Rel-19/20 (série 22 a 32) vrátil podezřele málo
definic. Ruční kontrola našla například tyto díry:

- **TR 22.870** nemá ve výstupu ani jednu definici, i když kapitola 3 jich obsahuje řadu
  (mimo jiné „6G AI Service“).
- **TS 32.500** postrádá definice „Distributed SON“ a „Hybrid SON“, i když v kapitole
  Definitions jsou.

Podle počtů to vypadá, že problém se netýká jen těchto dvou dokumentů.

Podklady jsou v repozitáři:

- korpus HTML, nad kterým extrakce běžela: `apps/downloader/data/specs/` (303 specifikací),
- výstup a log toho běhu: `apps/downloader/data/glossary/` (`extracted-glossary.json`,
  `extract-delta.json`, `abbreviations-list.txt`, `extract-run.log`),
- extrakce: `packages/spec-pipeline/src/glossary/extract-glossary.ts`, lokální spuštění
  `cd apps/downloader && npx tsx src/extract-glossary.ts` (volby viz hlavička souboru).

Najdi příčinu (může jich být víc) a oprav extrakci definic. Extrakce zkratek
se nesmí změnit a žádná definice se nesmí započítat dvakrát. Doplň regresní test
do `packages/spec-pipeline/test/`.

## Hotovo, když

- `pnpm --filter @3gpp/spec-pipeline test` projde,
- `pnpm --filter @3gpp/spec-worker typecheck` projde.

## Omezení prostředí

- Nespouštěj `pnpm build` ani build webu (volá produkční API). Síť není k dispozici.
- Repozitář nemá remote, nic nepushuj. Commit je volitelný.
- Pracuj samostatně, na nic se neptej. Na konci stručně napiš, co jsi změnil.
