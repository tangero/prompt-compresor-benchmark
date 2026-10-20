# Nástroj: dekodér verzí 3GPP

Na web (EN-only, Next.js static export) přidej veřejný nástroj, který z názvu souboru
nebo z označení verze specifikace 3GPP vyčte číslo specifikace, release a verzi
a odkáže na stránku specifikace v daném releasu.

## Zadání

1. **Čistá funkce** v `apps/web/src/lib/versionDecoder.ts`:

   ```ts
   export interface DecodedSpecFile {
     specNumber: string      // '38.331', '36.521-1'
     release: string         // 'R99', 'Rel-4' … 'Rel-21'
     version: { major: number; technical: number; editorial: number }
     versionString: string   // '19.4.0'
     url: string             // '/specification/Rel-19/38.331/'
   }
   export function decodeSpecFile(input: string): DecodedSpecFile
   ```

   Podporované vstupy (okolní mezery ignoruj, velikost písmen nerozhoduje):
   - název souboru `38331-j40.zip` nebo bez přípony `38331-j40`; číslo specifikace může mít
     část (`36521-1-i40.zip` → `36.521-1`); kód verze má tři znaky `0-9a-z` s hodnotou 0–35
     (`ib0` = 18.11.0),
   - označení `TS 38.331 V19.4.0` nebo `TR 38.901 V18.0.0`.

   Release určuje hlavní číslo verze: 3 = R99, 4 = Rel-4 … 21 = Rel-21. Neplatný vstup,
   návrh před schválením (hlavní číslo 0–2) i release mimo R99–Rel-21 vyhodí `Error`.
   Inspiraci najdeš v `apps/web/src/lib/specUrl.ts` a `apps/web/src/lib/seriesMapping.ts`
   a v tabulce verzování v `CLAUDE.md`.

2. **Klientská komponenta** `apps/web/src/components/VersionDecoder.tsx`, výchozí export
   `VersionDecoder({ initialInput }: { initialInput?: string })`: vstupní pole, a pokud je
   vstup platný, výsledek (číslo specifikace, release, verze) s odkazem na `url`;
   u neplatného vstupu srozumitelná chybová hláška. `initialInput` předvyplní pole
   a výsledek se musí vykreslit hned (i při renderu na serveru).

3. **Stránka** `/tools/version-decoder/` v `apps/web/src/app/tools/version-decoder/page.tsx`:
   synchronní serverová komponenta bez načítání dat, exportuje `metadata`, vykreslí
   `VersionDecoder` a anglický vysvětlující text o verzování 3GPP v aspoň třech sekcích
   s nadpisem `<h2>`. Veškerý text na webu je anglicky.

4. Napiš k funkci testy (vzor: `apps/web/tests/*.test.ts`, spouští se ze skriptu
   `test:unit` v `apps/web/package.json`).

5. Na závěr napiš krátké shrnutí návrhu (co a proč).

## Hotovo, když

- `pnpm --filter @3gpp/web test:unit` projde,
- `cd apps/web && npx tsc --noEmit` projde.

## Omezení prostředí

- Nespouštěj `pnpm build`, `next build` ani `next dev` (build volá produkční API).
  Síť není k dispozici.
- Repozitář nemá remote, nic nepushuj. Commit je volitelný.
- Pracuj samostatně, na nic se neptej.
