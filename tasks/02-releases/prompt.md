# Rel-21 a jeden zdroj seznamu releasů

Seznam releasů 3GPP je v repozitáři natvrdo na mnoha místech a údaje si odporují
(web uvádí u Rel-20 rok 2026, API 2027). Kopie jsou mimo jiné v:

- web: `apps/web/src/app/specifications/SpecificationsClient.tsx`, `apps/web/src/app/admin/pipeline/page.tsx`,
  `apps/web/src/app/admin/runs/page.tsx`, `apps/web/src/lib/releaseMeta.ts`, `apps/web/src/lib/releaseYears.ts`,
- API: dvakrát `releaseOrder` a `RELEASE_ORDER_FOR_TE` / `RELEASE_YEARS_MAP` v `apps/api/src/index.ts`,
  `apps/api/src/admin-operations.ts`,
- pipeline: `packages/spec-pipeline/src/glossary/engines/timeline/release-eras.ts`.

## Zadání

1. V `packages/types/src/releases.ts` vytvoř a z `packages/types/src/index.ts` exportuj
   (import `from '@3gpp/types'`):
   - `RELEASES` — pole objektů `{ name: string; year: number }` (smíš přidat další pole)
     v chronologickém pořadí od nejstaršího. Obsahuje přesně tyto releasy a roky:

     R99 1999, Rel-4 2001, Rel-5 2002, Rel-6 2005, Rel-7 2007, Rel-8 2008, Rel-9 2009,
     Rel-10 2011, Rel-11 2012, Rel-12 2014, Rel-13 2016, Rel-14 2017, Rel-15 2018,
     Rel-16 2020, Rel-17 2022, Rel-18 2024, Rel-19 2025, Rel-20 2027, Rel-21 2029.

     Stávající export `RELEASES` (a typ `Release`) v `packages/types/src/index.ts` je
     zastaralý a nikde se nepoužívá, nahraď ho.

   - `releaseFromVersionCode(code: string): string | null` — z třímístného kódu verze
     v názvu souboru 3GPP (`38331-j40.zip` → kód `j40`) vrátí release podle prvního znaku
     (`3` R99, `4` Rel-4 … `9` Rel-9, `a` Rel-10 … `k` Rel-20, `l` Rel-21). Velikost písmen
     nerozhoduje. Pro návrhy (`0`–`2`), znaky bez releasu v `RELEASES` a cokoli, co není
     přesně tři znaky `[0-9a-z]`, vrátí `null`.
2. Přidej Rel-21 (znak `l`) a nahraď kopie seznamu ve webu, API a pipeline odvozením
   z `RELEASES`. Ve zdrojích `apps/web/src`, `apps/api/src` a `packages/spec-pipeline/src`
   nesmí zůstat literál pole s pěti a více po sobě jdoucími položkami `'Rel-N'`
   (krátká datová pole jako `releases: ['Rel-19', 'Rel-20']` jsou v pořádku).
3. Hodnoty, které nejsou releasem 3GPP v tomto smyslu (GSM `Ph1`, `Ph2`, `R96`–`R98`
   a historické hodnoty katalogu `Rel-2`, `Rel-3`), do `RELEASES` nepatří. Kde je kód
   potřebuje (řazení hodnot z katalogu, seznam archivu FTP), ponech je jako krátký
   doplňkový seznam a zbytek odvoď z `RELEASES`. Chování těchto míst se nemá změnit,
   kromě přidání Rel-21 a sjednocení roků.
4. `apps/downloader` je mimo rozsah, neupravuj ho.

## Hotovo, když

- `pnpm --filter @3gpp/api test`, `pnpm --filter @3gpp/spec-pipeline test`
  a `pnpm --filter @3gpp/web test:unit` projdou,
- `pnpm --filter @3gpp/api typecheck` a `cd apps/web && npx tsc --noEmit` projdou.

## Omezení prostředí

- Nespouštěj `pnpm build` ani build webu (volá produkční API). Síť není k dispozici.
- Repozitář nemá remote, nic nepushuj. Commit je volitelný.
- Pracuj samostatně, na nic se neptej. Na konci stručně napiš, co jsi změnil.
