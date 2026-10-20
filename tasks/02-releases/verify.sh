#!/usr/bin/env bash
# Úloha 02: skryté testy RELEASES / releaseFromVersionCode, statická kontrola
# literálů, sady API + pipeline + web unit, typecheck API + web.
source "$(dirname "$0")/../../scripts/verify-lib.sh"

copy_hidden releases.hidden.test.ts apps/api/src/releases.hidden.test.ts
copy_hidden releases-static.hidden.test.ts apps/api/src/releases-static.hidden.test.ts
step hidden bash -c "cd apps/api && SNAPSHOT_ROOT='$WORK' node --import tsx --test src/releases.hidden.test.ts src/releases-static.hidden.test.ts"
rm -f "$WORK"/apps/api/src/releases*.hidden.test.ts
step suite bash -c "$PNPM --filter @3gpp/api test && $PNPM --filter @3gpp/spec-pipeline test && $PNPM --filter @3gpp/web test:unit"
step typecheck bash -c "$PNPM --filter @3gpp/api typecheck && cd apps/web && npx tsc --noEmit"
write_result
