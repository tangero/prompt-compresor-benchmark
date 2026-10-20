/**
 * Skryté akceptační testy úlohy 01 (cc-token-bench). Převzato z opravy
 * 0b68348 v 3gpp-explorer, samostatný soubor nezávislý na tom, jak agent
 * upravil admin-runs-priority.test.ts. Kopíruje se do apps/api/src/ až ve
 * fázi ověření.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import handler from './index';
import { MAX_QUEUED_PRIORITY_RUNS } from './admin-runs';
import { createSqliteTestD1 } from './lib/sqlite-test-d1';

const subtle = crypto.subtle as unknown as Record<string, unknown>;
if (typeof subtle.timingSafeEqual !== 'function') {
  subtle.timingSafeEqual = (l: ArrayBuffer, r: ArrayBuffer): boolean => {
    const a = new Uint8Array(l);
    const b = new Uint8Array(r);
    if (a.length !== b.length) return false;
    let d = 0;
    for (let i = 0; i < a.length; i += 1) d |= a[i] ^ b[i];
    return d === 0;
  };
}

const TOKEN = 'test-admin-token';

/** D1 that yields before every statement, so concurrent requests interleave like on real D1. */
function interleaving(db: D1Database): D1Database {
  const tick = () => new Promise((r) => setTimeout(r, 1));
  const wrap = (st: any): any => ({
    bind: (...a: unknown[]) => wrap(st.bind(...a)),
    first: async (...a: unknown[]) => { await tick(); return st.first(...a); },
    run: async () => { await tick(); return st.run(); },
    all: async () => { await tick(); return st.all(); },
  });
  return { ...db, prepare: (sql: string) => wrap(db.prepare(sql)), batch: db.batch?.bind(db) } as unknown as D1Database;
}

function context(opts: { interleave?: boolean } = {}) {
  const raw = createSqliteTestD1();
  const db = opts.interleave ? interleaving(raw) : raw;
  const env = { DB: db, ENVIRONMENT: 'test', ADMIN_TOKEN: TOKEN, USAGE_LOG_ENABLED: '0' };
  const ctx = { waitUntil() {}, passThroughOnException() {} } as unknown as ExecutionContext;
  const call = (path: string, body: unknown) =>
    handler.fetch(
      new Request(`https://api.test${path}`, { method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(body) }),
      env as never,
      ctx,
    );
  const create = async (body: Record<string, unknown>) => call('/api/admin/runs', { executor: 'spec-worker', ...body });
  return { db, create, call };
}

test('hidden: retry of a priority run respects the cap', async () => {
  const t = context();
  const prio = (await (await t.create({ type: 'release-changes', params: { s: 'x' }, priority: 1 })).json()) as any;
  await t.db.prepare(`UPDATE admin_runs SET status = 'failed', finished_at = unixepoch() WHERE id = ?1`).bind(prio.run.id).run();
  for (let i = 0; i < MAX_QUEUED_PRIORITY_RUNS; i += 1) await t.create({ type: 'process-spec', params: { i }, priority: 1 });
  const retry = await t.call(`/api/admin/runs/${prio.run.id}/retry`, {});
  assert.equal(retry.status, 429);
  assert.equal(((await retry.json()) as any).error, 'priority_queue_full');
  const n = await t.db.prepare(`SELECT COUNT(*) AS n FROM admin_runs WHERE priority > 0 AND status = 'queued'`).first<{ n: number }>();
  assert.equal(n?.n, MAX_QUEUED_PRIORITY_RUNS);
});

test('hidden: concurrent priority creates at the cap cannot both pass', async () => {
  const t = context({ interleave: true });
  for (let i = 0; i < MAX_QUEUED_PRIORITY_RUNS - 1; i += 1) await t.create({ type: 'process-spec', params: { i }, priority: 1 });
  const [a, b] = await Promise.all([
    t.create({ type: 'process-spec', params: { i: 'a' }, priority: 1 }),
    t.create({ type: 'process-spec', params: { i: 'b' }, priority: 1 }),
  ]);
  assert.deepEqual([a.status, b.status].sort(), [200, 429]);
  const n = await t.db.prepare(`SELECT COUNT(*) AS n FROM admin_runs WHERE priority > 0 AND status = 'queued'`).first<{ n: number }>();
  assert.equal(n?.n, MAX_QUEUED_PRIORITY_RUNS);
});
