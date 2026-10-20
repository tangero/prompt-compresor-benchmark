#!/usr/bin/env bash
# Úloha 01: skryté testy limitu prioritních běhů, sada API, typecheck API.
TESTS_EXPECTED_TO_CHANGE="apps/api/src/admin-runs-priority.test.ts"
source "$(dirname "$0")/../../scripts/verify-lib.sh"

copy_hidden admin-runs-priority.hidden.test.ts apps/api/src/admin-runs-priority.hidden.test.ts
step hidden bash -c 'cd apps/api && node --import tsx --test src/admin-runs-priority.hidden.test.ts'
rm -f "$WORK/apps/api/src/admin-runs-priority.hidden.test.ts"
step suite $PNPM --filter @3gpp/api test
step typecheck $PNPM --filter @3gpp/api typecheck
write_result
