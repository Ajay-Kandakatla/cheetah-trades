/* 🗂 GgwPager section labels (2026-11-22, spec watch_org rev 4 §3.5 / §4 WP-FE-WATCH).
 * Ajay 2026-11-22: "Manual ones I add them need to be on top then auto intraday..". With served `groups` the pager draws
 * the served section words INLINE at the first item of each section and every item reads `[🎯?, SYM]` (the dashed
 * outline already says 🤖 — no pager 🤖 tag, no clock [C7]). NEGATIVES: no `groups` → today's pager byte for byte (the
 * 🚩 / 🧪 card grid never passes it); a repeated key never draws a second label; no HH:MM in the pager. Words = stand-ins. */
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgwPager } from './GajjalaWatchLayout';
import { ggwGroupStarts, parseRowOrg, parseSections, type GgwRowAplus, type GgwRowAuto } from '../lib/gajjalaWatch';

const AUTO: GgwRowAuto = {
  tag: '🤖', sources: [], source_words: [], text: 'served-auto', volume_text: null, volume_source: null, added_et: '10:42',
  added_text: 'served added 10:42', leaving_text: null, remove_title: 'served-auto-x',
};
const APLUS: GgwRowAplus = { tag: '🎯', text: 'served-aplus 09:47', title: 'served-aplus-hover', items: [] };
const ROWS = [
  { symbol: 'AKAN', aplus: APLUS, auto: null, org: parseRowOrg({ group: 'yours' }) },
  { symbol: 'RAIN', aplus: null, auto: null, org: parseRowOrg({ group: 'yours' }) },
  { symbol: 'SEGG', aplus: APLUS, auto: AUTO, org: parseRowOrg({ group: 'aplus' }) },
  { symbol: 'SKYA', aplus: null, auto: AUTO, org: parseRowOrg({ group: 'auto' }) },
  { symbol: 'MEDS', aplus: null, auto: AUTO, org: parseRowOrg({ group: 'ran' }) },
];
const SECTIONS = parseSections([
  { key: 'yours', text: 'served-s1 · 2', hint: 'served-h1' },
  { key: 'aplus', text: 'served-s2 · 1', hint: 'served-h2' },
  { key: 'auto', text: 'served-s3 · 1', hint: null },
  { key: 'ran', text: 'served-s4 · 1', hint: 'served-h4' },
])!;

function pager(groups?: ReturnType<typeof ggwGroupStarts>, rows = ROWS) {
  return render(
    <GgwPager rows={rows} onPage={(i) => i < 2} paged cur={0} pages={3} usePick={false} busy={false} removeLabel="served-rm"
              onToggle={() => {}} onPrev={() => {}} onNext={() => {}} onRemove={() => {}} groups={groups} />,
  ).container;
}
afterEach(() => cleanup());

describe('🗂 GgwPager groups', () => {
  it('the served labels sit inline BEFORE the first item of each section, in served order (a 4th key too)', () => {
    const c = pager(ggwGroupStarts(ROWS, SECTIONS));
    const seq = Array.from(c.querySelector('nav')!.children).map((e) => e.getAttribute('data-testid') ?? e.className);
    const at = (id: string) => seq.indexOf(id);
    expect(at('ggw-pager-group-yours')).toBe(at('ggw-pager-prev') + 1);
    expect(at('ggw-pager-group-aplus')).toBeGreaterThan(at('ggw-pager-group-yours'));
    expect(at('ggw-pager-group-auto')).toBeGreaterThan(at('ggw-pager-group-aplus'));
    expect(at('ggw-pager-group-ran')).toBeGreaterThan(at('ggw-pager-group-auto'));
    expect(c.querySelector('[data-testid="ggw-pager-group-yours"]')!.textContent).toBe('served-s1 · 2');
    expect(c.querySelector('[data-testid="ggw-pager-group-yours"]')!.getAttribute('title')).toBe('served-h1');
    expect(c.querySelector('[data-testid="ggw-pager-group-yours"]')!.classList.contains('ggw-pager-group--first')).toBe(true);
    expect(c.querySelector('[data-testid="ggw-pager-group-aplus"]')!.classList.contains('ggw-pager-group--first')).toBe(false);
    /* the label precedes its first item */
    const groupEl = c.querySelector('[data-testid="ggw-pager-group-ran"]')!;
    expect(groupEl.nextElementSibling!.querySelector('[data-testid="ggw-pager-MEDS"]')).not.toBeNull();
  });
  it('items read [🎯?, SYM] — no 🤖 tag in grouped mode; the dashed 🤖 class and the served × title stay', () => {
    const c = pager(ggwGroupStarts(ROWS, SECTIONS));
    expect(c.querySelector('[data-testid="ggw-pager-AKAN"]')!.textContent).toBe('🎯 AKAN');
    expect(c.querySelector('[data-testid="ggw-pager-SEGG"]')!.textContent).toBe('🎯 SEGG');
    expect(c.querySelector('[data-testid="ggw-pager-SKYA"]')!.textContent).toBe('SKYA');
    expect(c.querySelector('[data-testid="ggw-pager-SKYA"]')!.closest('.ggw-pager-item')!.classList.contains('ggw-pager-item--auto')).toBe(true);
    expect(c.querySelector('[data-testid="ggw-pager-x-SKYA"]')!.getAttribute('title')).toBe('served-auto-x');
  });
  it('NEGATIVE: no HH:MM anywhere in a grouped pager (C7) — the served add time never leaks in', () => {
    const c = pager(ggwGroupStarts(ROWS, SECTIONS));
    const items = Array.from(c.querySelectorAll('.ggw-pager-item, .ggw-pager-group')).map((e) => e.textContent).join(' ');
    expect(items).not.toMatch(/\d{1,2}:\d{2}/);
  });
  it('NEGATIVE: a repeated key later in the list never draws a second label [C6]', () => {
    const rows = [...ROWS, { symbol: 'LATE', aplus: null, auto: null, org: parseRowOrg({ group: 'yours' }) }];
    const c = pager(ggwGroupStarts(rows, SECTIONS), rows);
    expect(c.querySelectorAll('[data-testid="ggw-pager-group-yours"]').length).toBe(1);
  });
  it('NEGATIVE: no `groups` → today\'s pager byte for byte (the 🤖 tag kept, no label)', () => {
    const a = pager().innerHTML;
    cleanup();
    const b = render(
      <GgwPager rows={ROWS} onPage={(i) => i < 2} paged cur={0} pages={3} usePick={false} busy={false} removeLabel="served-rm"
                onToggle={() => {}} onPrev={() => {}} onNext={() => {}} onRemove={() => {}} />,
    ).container.innerHTML;
    expect(b).toBe(a);
    expect(a).not.toContain('ggw-pager-group');
    cleanup();
    const c = pager();
    expect(c.querySelector('[data-testid="ggw-pager-SKYA"]')!.textContent).toBe('🤖 SKYA');
    expect(c.querySelector('[data-testid="ggw-pager-SEGG"]')!.textContent).toBe('🎯 🤖 SEGG');
  });
  it('NEGATIVE: groups with no served section → items without labels; empty groups → no label', () => {
    const c = pager([]);
    expect(c.querySelector('.ggw-pager-group')).toBeNull();
    expect(c.querySelector('[data-testid="ggw-pager-SKYA"]')!.textContent).toBe('SKYA');
  });
});
