# Bug: limit prioritních běhů ve frontě jde obejít

Fronta admin běhů (`POST /api/admin/runs`, `apps/api/src/index.ts`) smí mít nejvýš
`MAX_QUEUED_PRIORITY_RUNS` (20, exportováno z `apps/api/src/admin-runs.ts`) čekajících
prioritních běhů (`priority > 0`, `status = 'queued'`). Nad limitem má API vrátit
HTTP 429 s tělem `{ "error": "priority_queue_full", ... }`. Limit ale jde obejít dvěma způsoby:

1. **Retry.** `POST /api/admin/runs/:id/retry` na neúspěšný prioritní běh založí nový
   prioritní běh, i když ve frontě už čeká 20 prioritních běhů. Má vrátit 429
   `priority_queue_full` a nic nezaložit.
2. **Souběh.** Když ve frontě čeká 19 prioritních běhů a přijdou dva souběžné požadavky
   na založení prioritního běhu, projdou oba (ve frontě je pak 21). Správně má jeden
   projít (200) a druhý dostat 429 `priority_queue_full`.

Oprav obě chyby. Chování běžných (neprioritních) běhů a existující API se nesmí změnit.
Doplň testy, které obě chyby zachytí (`apps/api/src/admin-runs-priority.test.ts`).

## Hotovo, když

- `pnpm --filter @3gpp/api test` projde,
- `pnpm --filter @3gpp/api typecheck` projde.

## Omezení prostředí

- Nespouštěj `pnpm build` ani build webu (volá produkční API). Síť není k dispozici.
- Repozitář nemá remote, nic nepushuj. Commit je volitelný.
- Pracuj samostatně, na nic se neptej. Na konci stručně napiš, co jsi změnil.
