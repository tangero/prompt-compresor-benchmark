// Skryté testy úlohy 04: extrakce definic glosáře.
// Kopírují se do packages/spec-pipeline/test/ až při ověření.
// Testují chování přes GlossaryExtractor (ne názvy pomocných funkcí reference):
// zalomené odstavce, novější šablona „3.1 Terms“ bez dvojího započtení
// a výsledek nad podkorpusem skutečných HTML v apps/downloader/data/specs.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { GlossaryExtractor, type ExtractedOutput } from '../src/glossary/extract-glossary';
import type { GlossaryPaths } from '../src/glossary/paths';

const HERE = dirname(fileURLToPath(import.meta.url));
const CORPUS = join(HERE, '..', '..', '..', 'apps', 'downloader', 'data', 'specs');

// Referenční řešení nad podkorpusem (303 specifikací): 1 075 definic z 208 specifikací,
// výchozí stav 1 001 ze 186. Test nechce přesný počet ani horní mez: agenti v korpusu
// našli i další skutečnou příčinu (nadpis „Definitions and abbreviations“) a správně
// došli k ~1 400 definicím. Místo horní meze kontroluje šum ve výstupu.
// Text definic se porovnává po normalizaci bílých znaků (HTML je stejně slévá).
const MIN_DEFINITIONS = 1060;
const MIN_SPECS_WITH_DEFS = 205;
const NOISE_TERM = /^(NOTE|EXAMPLE|Editor.?s?|Table|Figure|Annex|Clause)\b|^[\d.]+$|^[-–(]/i;
const norm = (s: string | undefined) => s?.replace(/\s+/g, ' ').trim();
const BASELINE = JSON.parse(readFileSync(join(HERE, 'glossary-baseline.fixture.json'), 'utf8')) as {
  definitionTerms: string[]; abbreviations: string[];
};

async function extract(corpus: string, opts: { spec?: string } = {}): Promise<ExtractedOutput> {
  const state = mkdtempSync(join(tmpdir(), 'glossary-hidden-state-'));
  const paths = {
    stateDir: state, specsCorpusDir: corpus, webOutDir: join(state, 'web'), topologyDir: join(state, 't'),
  } as unknown as GlossaryPaths;
  const log = console.log;
  console.log = () => {};
  try {
    await new GlossaryExtractor({ paths, output: 'x.json', minCount: 1, verbose: false, ...opts }).run();
  } finally {
    console.log = log;
  }
  return JSON.parse(readFileSync(join(state, 'x.json'), 'utf8')) as ExtractedOutput;
}

function corpusWith(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'glossary-hidden-'));
  for (const [rel, body] of Object.entries(files)) {
    const dir = join(root, rel);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'content.html'), `<html><body>${body}</body></html>`);
  }
  return root;
}

describe('hidden: wrapped definition paragraphs', () => {
  it('extracts definitions whose paragraph spans several lines', async () => {
    const out = await extract(corpusWith({
      'Rel-19/32/32999': `
<h2 id="definitions">3.1 Definitions</h2>
<p>For the purposes of the present document, the terms and definitions
given in TR 21.905 [1] and the following apply.</p>
<p>Centralized widget: widget solution where widget algorithms are executed at
the Network Management level.</p>
<p>Short widget: a widget defined on one line.</p>
<p>Spread widget: widget solution where widget algorithms are
executed at two or
more of the following levels: NE or EM or NM.</p>
<h2 id="abbreviations">3.2 Abbreviations</h2>
<p>WGT\tWidget Generation Technique</p>`,
    }));
    const defs = new Map(out.definitions.map((d) => [norm(d.term), norm(d.definition)]));
    assert.equal(defs.get('Centralized widget'), 'widget solution where widget algorithms are executed at the Network Management level.');
    assert.equal(defs.get('Short widget'), 'a widget defined on one line.');
    assert.equal(defs.get('Spread widget'), 'widget solution where widget algorithms are executed at two or more of the following levels: NE or EM or NM.');
    assert.deepEqual(out.abbreviations.map((a) => a.abbr), ['WGT']);
  });
});

describe('hidden: newer template with "3.1 Terms"', () => {
  it('extracts definitions under Terms, each paragraph counted once', async () => {
    const out = await extract(corpusWith({
      'Rel-20/22/22998': `<h1>3 Definitions of terms, symbols and abbreviations</h1>
<h2>3.1 Terms</h2>
<p><strong>Gadget service:</strong> a service provided by the network where gadget
functionalities are made available to a subscriber.</p>
<h2>3.2 Symbols</h2>
<p>Void.</p>
<h2>3.3 Abbreviations</h2>
<p>GDS\tGadget Service</p>`,
      'Rel-20/22/22997': `<h1>3 Definitions</h1>
<h2>3.1 Terms</h2>
<p>Probe service: a service that provides probing results to a consumer.</p>`,
    }));
    const defs = new Map(out.definitions.map((d) => [norm(d.term), d]));
    assert.ok(norm(defs.get('Gadget service')?.definition)?.startsWith('a service provided by the network where gadget functionalities'));
    assert.equal(defs.get('Probe service')?.occurrences, 1, 'odstavec pod vnořenými nadpisy se nesmí započítat dvakrát');
    assert.deepEqual(out.abbreviations.map((a) => a.abbr), ['GDS']);
  });

  it('does not treat the abbreviations or symbols clause as definitions', async () => {
    const out = await extract(corpusWith({
      'Rel-20/22/22996': `<h1>3 Definitions of terms, symbols and abbreviations</h1>
<h2>3.2 Symbols</h2>
<p>Tx: transmitter power in dBm for the purpose of this test.</p>
<h2>3.3 Abbreviations</h2>
<p>ZZZ\tZeta Zone Zero</p>`,
    }));
    assert.deepEqual(out.definitions.map((d) => d.term), []);
  });
});

describe('hidden: real specifications from the corpus', () => {
  it('corpus is present', () => {
    assert.ok(existsSync(join(CORPUS, 'Rel-19', '32', '32500', 'content.html')), CORPUS);
  });

  it('TS 32.500 has its wrapped SON definitions', async () => {
    const out = await extract(CORPUS, { spec: '32.500' });
    const defs = new Map(out.definitions.map((d) => [norm(d.term), norm(d.definition)]));
    assert.equal(defs.get('Distributed SON'), 'SON solution where SON algorithms are executed at the Network Element level.');
    assert.equal(defs.get('Hybrid SON'), 'SON solution where SON algorithms are executed at two or more of the following levels: NE or EM or NM.');
  });

  it('TR 22.870 has definitions from the "Terms" clause', async () => {
    const out = await extract(CORPUS, { spec: '22.870' });
    const ai = out.definitions.find((d) => norm(d.term) === '6G AI Service');
    assert.ok(ai, 'chybí 6G AI Service');
    assert.ok(norm(ai.definition)!.startsWith('a service provided by the 6th Generation (6G) network'), ai.definition);
    assert.ok(out.definitions.length >= 10, `jen ${out.definitions.length} definic`);
  });

  it('whole corpus: more definitions, nothing lost, no noise, abbreviations unchanged', async () => {
    const out = await extract(CORPUS);
    const terms = out.definitions.map((d) => d.term);
    // bez ohledu na velikost písmen: správná řešení slučují „Call“ a „call“ z různých specifikací
    const key = (t: string) => norm(t)!.toLowerCase();
    const normTerms = new Set(terms.map(key));
    const specs = new Set(out.definitions.flatMap((d) => d.specs));
    assert.ok(out.definitions.length >= MIN_DEFINITIONS, `definic ${out.definitions.length}, minimum ${MIN_DEFINITIONS}`);
    assert.ok(specs.size >= MIN_SPECS_WITH_DEFS, `specifikací s definicemi ${specs.size}, minimum ${MIN_SPECS_WITH_DEFS}`);
    assert.equal(new Set(terms).size, terms.length, 'zdvojené termy');
    // Výchozí stav obsahuje i šum (věty a poznámky editora místo termů), který správné řešení
    // smí vyčistit. Ztratit se proto smí nejvýš 1 % termů výchozího stavu.
    const lost = BASELINE.definitionTerms.filter((t) => !normTerms.has(key(t)));
    assert.ok(lost.length <= BASELINE.definitionTerms.length * 0.01,
      `ztracené definice výchozího stavu (${lost.length}): ${lost.slice(0, 20).join(' | ')}`);
    const bad = out.definitions.filter((d) => !d.definition || d.definition.trim().length < 10
      || d.term.length > 80 || /[\n\t]/.test(d.term) || NOISE_TERM.test(d.term.trim()));
    // Reference má 3 šumové termy (Figure B-1, NOTE 4A0, Example model), které propouštějí
    // původní filtry projektu; tolerance 1 % definic.
    assert.ok(bad.length <= out.definitions.length * 0.01,
      `prázdné, kusé nebo šumové definice (${bad.length}): ${bad.slice(0, 20).map((d) => d.term).join(' | ')}`);
    // Zkratky se nesmí ztratit. Přibýt smějí: oprava nadpisu „Definitions and abbreviations“
    // (třetí skutečná příčina, kterou reference neřeší) přidává pár zkratek z dosud přeskočených kapitol.
    const abbrs = new Set(out.abbreviations.map((a) => a.abbr));
    assert.deepEqual(BASELINE.abbreviations.filter((a) => !abbrs.has(a)), [], 'zkratky se nesmí ztratit');
  });
});
