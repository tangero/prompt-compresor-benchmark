#!/usr/bin/env bash
# Úloha 04: skryté testy extrakce definic (syntetické případy + podkorpus skutečných HTML),
# sada spec-pipeline, typecheck spec-worker (CI projektu tak kontroluje spec-pipeline).
source "$(dirname "$0")/../../scripts/verify-lib.sh"

copy_hidden glossary-extract.hidden.spec.ts packages/spec-pipeline/test/glossary-extract.hidden.spec.ts
copy_hidden glossary-baseline.fixture.json packages/spec-pipeline/test/glossary-baseline.fixture.json
step hidden bash -c "cd packages/spec-pipeline && node --test --import tsx test/glossary-extract.hidden.spec.ts"
rm -f "$WORK"/packages/spec-pipeline/test/glossary-extract.hidden.spec.ts "$WORK"/packages/spec-pipeline/test/glossary-baseline.fixture.json
step suite bash -c "$PNPM --filter @3gpp/spec-pipeline test"
step typecheck bash -c "$PNPM --filter @3gpp/spec-worker typecheck"
write_result
