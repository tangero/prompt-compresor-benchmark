# Vlastní úloha

Úloha je složka `tasks/NN-jmeno/`. Číslo `NN` (první dva znaky) se stává součástí jmen obrazů
(`cc-bench-task-NN`, `cc-bench-NN-<konfigurace>`), musí proto být mezi úlohami jedinečné.

```
tasks/05-moje-uloha/
  prompt.md          zadání pro agenta (jde na stdin `claude -p`)
  snapshot.ref       plný hash výchozího commitu ve vašem repozitáři (SOURCE_REPO)
  verify.sh          ověření řešení, zapíše verify.json
  hidden-tests/      testy, které agent nevidí; zkopírují se až při ověření
  reference.patch    vaše referenční řešení (pro scripts/check-tasks.sh)
  task.Dockerfile    volitelně: vlastní obraz úlohy místo docker/task/Dockerfile
  snapshot-fixup.sh  volitelně: úpravy snapshotu (např. přidání dat mimo git)
  big-data.json      volitelně: {jméno: regex} cest k objemným datům; runner pak měří, zda je agent četl
```

## Jak vybrat úlohu

- **Skutečný úkol z vašeho backlogu**, který zabere agentovi 5–30 minut. Na příliš krátkých
  úlohách převáží fixní náklad systémového promptu. Na dlouhých roste rozptyl a cena.
- **Různé profily spotřeby.** Doplňky cílí na různé položky: RTK na výstup shellu, Context
  Mode a Headroom na velké výsledky nástrojů, Caveman a Ponytail na text a kód modelu.
  Původní sada proto měla po jedné úloze na shell, čtení, psaní kódu a objemná data.
- **Strojově ověřitelný výsledek.** Zadání má určit rozhraní (jméno funkce, export, cestu
  ke stránce), aby ho skryté testy mohly volat. Implementaci nechte na agentovi.
- Pokud jde o objem, zadejte **dolní práh, ne přesný počet**. U úlohy 04 jsme původně
  testovali přesný počet definic a ten trestal i správná řešení.

## prompt.md

Pište tak, jak byste úkol zadali kolegovi: kontext, zadání a podmínky přijetí. Pokud má agent
zachovat existující testy, napište to do zadání. Ukázky najdete v `tasks/*/prompt.md`.

## verify.sh

Načte `scripts/verify-lib.sh` a spustí tři kroky, `hidden`, `suite` a `typecheck`. Každý krok
dostane hodnotu true nebo false:

```bash
#!/usr/bin/env bash
# volitelně: existující testy, které má agent podle zadání měnit (nepočítají se jako zásah do testů)
TESTS_EXPECTED_TO_CHANGE="src/foo.test.ts"
source "$(dirname "$0")/../../scripts/verify-lib.sh"

copy_hidden foo.hidden.test.ts src/foo.hidden.test.ts
step hidden bash -c 'node --import tsx --test src/foo.hidden.test.ts'
rm -f "$WORK/src/foo.hidden.test.ts"
step suite $PNPM test
step typecheck $PNPM typecheck
write_result
```

Volání: `verify.sh <adresář snapshotu> <výstupní adresář>`. Runner ho spouští uvnitř
kontejneru po skončení agenta, `scripts/reverify.py` později v čistém obraze bez sítě.

## Kontrola před během

```bash
SOURCE_REPO=~/cesta/k/repozitari scripts/check-tasks.sh /tmp/check 05-moje-uloha
```

Na výchozím stavu musí skryté testy **padat** a sada s typecheckem **projít**. Po aplikaci
`reference.patch` musí projít všechno. Pokud sada padá už na výchozím stavu (chybějící
systémový nástroj, síť), agent bude ladit něco, co s úlohou nesouvisí. Doinstalujte to
v `task.Dockerfile`, jako to dělá úloha 04 s `unzip`.

## Kolik běhů

Mezi nejlevnějším a nejdražším ze tří opakování téže konfigurace na téže úloze byl v původním
benchmarku rozdíl typicky 15–30 % mediánu, v krajních případech až 50 %. Tři opakování
na buňku stačí jen na velké rozdíly. Pro rozdíly kolem 10 % počítejte s pěti a více
opakováními, nebo úlohy zúžte.
