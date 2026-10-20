/**
 * Skryté akceptační testy úlohy 03 (cc-token-bench): decodeSpecFile,
 * render komponenty a stránky, žádné české znaky ve výstupu.
 * Kopíruje se do apps/web/tests/ až ve fázi ověření.
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { decodeSpecFile } from '../src/lib/versionDecoder'
import VersionDecoder from '../src/components/VersionDecoder'
import Page from '../src/app/tools/version-decoder/page'

type Row = [input: string, spec: string, release: string, version: string]
const VALID: Row[] = [
  ['38331-j40.zip', '38.331', 'Rel-19', '19.4.0'],
  ['38331-j40', '38.331', 'Rel-19', '19.4.0'],
  ['TS 38.331 V19.4.0', '38.331', 'Rel-19', '19.4.0'],
  ['23501-ib0.zip', '23.501', 'Rel-18', '18.11.0'],
  ['36521-1-i40.zip', '36.521-1', 'Rel-18', '18.4.0'],
  ['21101-3a0.zip', '21.101', 'R99', '3.10.0'],
  ['23002-400.zip', '23.002', 'Rel-4', '4.0.0'],
  ['38300-k10.zip', '38.300', 'Rel-20', '20.1.0'],
  ['38331-L00.ZIP', '38.331', 'Rel-21', '21.0.0'],
  ['TR 38.901 V18.0.0', '38.901', 'Rel-18', '18.0.0'],
  ['TS 38.331 V19.10.2', '38.331', 'Rel-19', '19.10.2'],
  ['  36331-a00.zip  ', '36.331', 'Rel-10', '10.0.0'],
]
const INVALID = ['', 'hello', '38331-j4.zip', '38331.zip', '38331-240.zip', 'TS 38.331 V2.1.0', '38331-m00.zip', 'TS 38.331']

for (const [input, spec, release, version] of VALID) {
  test(`hidden: decodeSpecFile(${JSON.stringify(input)})`, () => {
    const d = decodeSpecFile(input)
    assert.equal(d.specNumber, spec)
    assert.equal(d.release, release)
    assert.equal(d.versionString, version)
    const [major, technical, editorial] = version.split('.').map(Number)
    assert.deepEqual(d.version, { major, technical, editorial })
    assert.equal(d.url, `/specification/${release}/${spec}/`)
  })
}

test('hidden: decodeSpecFile throws on invalid input', () => {
  for (const input of INVALID) {
    assert.throws(() => decodeSpecFile(input), Error, `input ${JSON.stringify(input)}`)
  }
})

const CZECH = /[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/

test('hidden: VersionDecoder renders the decoded release and the link', () => {
  const html = renderToStaticMarkup(createElement(VersionDecoder, { initialInput: '38331-j40.zip' }))
  assert.match(html, /<input/)
  assert.match(html, /Rel-19/)
  assert.match(html, /19\.4\.0/)
  // next/link mimo Next.js (bez trailingSlash z next.config) koncové lomítko ořízne
  assert.match(html, /href="\/specification\/Rel-19\/38\.331\/?"/)
  assert.doesNotMatch(html, CZECH)
})

test('hidden: VersionDecoder with invalid input shows no result link', () => {
  const html = renderToStaticMarkup(createElement(VersionDecoder, { initialInput: 'hello' }))
  assert.doesNotMatch(html, /href="\/specification\//)
  assert.doesNotMatch(html, CZECH)
})

test('hidden: the page explains versioning in at least three sections, English only', () => {
  const html = renderToStaticMarkup(createElement(Page as any))
  assert.ok((html.match(/<h2[\s>]/g) ?? []).length >= 3, 'at least three <h2> sections')
  assert.match(html, /<input/)
  assert.doesNotMatch(html, CZECH)
})
