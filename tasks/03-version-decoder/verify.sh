#!/usr/bin/env bash
# Úloha 03: skryté testy dekodéru a stránky, web unit testy, typecheck webu.
source "$(dirname "$0")/../../scripts/verify-lib.sh"

copy_hidden version-decoder.hidden.test.tsx apps/web/tests/version-decoder.hidden.test.tsx
step hidden bash -c 'cd apps/web && npx tsx --tsconfig tests/tsconfig.react.json --test tests/version-decoder.hidden.test.tsx'
rm -f "$WORK/apps/web/tests/version-decoder.hidden.test.tsx"
step suite $PNPM --filter @3gpp/web test:unit
step typecheck bash -c 'cd apps/web && npx tsc --noEmit'
write_result
