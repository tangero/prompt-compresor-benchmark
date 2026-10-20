/**
 * Skrytý statický test úlohy 02 (cc-token-bench): ve zdrojích webu, API
 * a pipeline nezůstane literál pole s pěti a více po sobě jdoucími položkami
 * 'Rel-N'. Datová pole s méně položkami (releases: ['Rel-19', 'Rel-20']) projdou.
 * Testovací soubory se nekontrolují. Spouští se z kořene snapshotu.
 */
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

const ROOTS = ['apps/web/src', 'apps/api/src', 'packages/spec-pipeline/src'];
const LITERAL_RUN = /(['"`])Rel-\d+\1(?:\s*,\s*(['"`])Rel-\d+\2){4,}/g;
const SKIP = /\.(test|spec)\.tsx?$/;

function* sources(dir: string): Generator<string> {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules') continue;
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) yield* sources(p);
    else if (/\.(ts|tsx|js|mjs)$/.test(entry) && !SKIP.test(entry)) yield p;
  }
}

test('hidden: no hard-coded lists of 5+ consecutive Rel-N literals', () => {
  const root = process.env.SNAPSHOT_ROOT ?? process.cwd();
  const hits: string[] = [];
  for (const r of ROOTS) {
    for (const file of sources(join(root, r))) {
      const text = readFileSync(file, 'utf8');
      for (const m of text.matchAll(LITERAL_RUN)) {
        const line = text.slice(0, m.index).split('\n').length;
        hits.push(`${file.slice(root.length + 1)}:${line}`);
      }
    }
  }
  assert.deepEqual(hits, []);
});
