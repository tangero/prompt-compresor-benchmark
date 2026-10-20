/**
 * Skryté akceptační testy úlohy 02 (cc-token-bench): sdílený seznam releasů
 * v @3gpp/types. Kopíruje se do apps/api/src/ až ve fázi ověření.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { RELEASES, releaseFromVersionCode } from '@3gpp/types';

test('hidden: releaseFromVersionCode maps the first version character to a release', () => {
  assert.equal(releaseFromVersionCode('l00'), 'Rel-21');
  assert.equal(releaseFromVersionCode('k10'), 'Rel-20');
  assert.equal(releaseFromVersionCode('j40'), 'Rel-19');
  assert.equal(releaseFromVersionCode('ib0'), 'Rel-18');
  assert.equal(releaseFromVersionCode('a00'), 'Rel-10');
  assert.equal(releaseFromVersionCode('900'), 'Rel-9');
  assert.equal(releaseFromVersionCode('4a0'), 'Rel-4');
  assert.equal(releaseFromVersionCode('3a0'), 'R99');
});

test('hidden: releaseFromVersionCode is case-insensitive', () => {
  assert.equal(releaseFromVersionCode('L00'), 'Rel-21');
  assert.equal(releaseFromVersionCode('IB0'), 'Rel-18');
});

test('hidden: releaseFromVersionCode returns null for drafts, unknown and malformed codes', () => {
  for (const code of ['000', '100', '200', 'm00', 'z99', '', 'k1', 'k100', 'k-0', 'Rel-20']) {
    assert.equal(releaseFromVersionCode(code), null, `code ${JSON.stringify(code)}`);
  }
});

test('hidden: RELEASES is chronological, ends with Rel-21 and carries years', () => {
  const names = RELEASES.map((r) => r.name);
  assert.equal(names[names.length - 1], 'Rel-21');
  for (const n of ['R99', 'Rel-4', 'Rel-10', 'Rel-15', 'Rel-19', 'Rel-20', 'Rel-21']) {
    assert.ok(names.includes(n), `${n} in RELEASES`);
  }
  assert.ok(names.indexOf('R99') < names.indexOf('Rel-4'));
  for (let n = 5; n <= 21; n += 1) {
    assert.ok(names.indexOf(`Rel-${n - 1}`) < names.indexOf(`Rel-${n}`), `Rel-${n - 1} before Rel-${n}`);
  }
  assert.equal(new Set(names).size, names.length, 'no duplicates');
  for (const n of ['Ph1', 'Ph2', 'R96', 'R97', 'R98', 'Rel-2', 'Rel-3']) {
    assert.ok(!names.includes(n), `${n} is not a 3GPP release in RELEASES`);
  }
  const expected: Record<string, number> = {
    R99: 1999, 'Rel-4': 2001, 'Rel-5': 2002, 'Rel-6': 2005, 'Rel-7': 2007, 'Rel-8': 2008,
    'Rel-9': 2009, 'Rel-10': 2011, 'Rel-11': 2012, 'Rel-12': 2014, 'Rel-13': 2016,
    'Rel-14': 2017, 'Rel-15': 2018, 'Rel-16': 2020, 'Rel-17': 2022, 'Rel-18': 2024,
    'Rel-19': 2025, 'Rel-20': 2027, 'Rel-21': 2029,
  };
  for (const [name, year] of Object.entries(expected)) {
    assert.equal(RELEASES.find((r) => r.name === name)?.year, year, `year of ${name}`);
  }
  for (const r of RELEASES) assert.equal(typeof r.year, 'number', `${r.name} year is a number`);
});
