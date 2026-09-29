/* 🔥 Hottest — a REAL payload through the REAL component (2026-09-28).
 *
 * The fixture is the branch API's own answer to
 *   GET /rotation/hottest?names=3&sort=eq_score&dir=desc&then_by=q_eps_yoy:desc
 * captured 2026-09-29 00:1x ET (market closed) from the branch backend run
 * read-only on :8014, trimmed to its first 2 rosters and first 3 sectors (first
 * 2 industries each), served order untouched, every top-level key kept verbatim
 * (quality_info, sorted_then_by, sort_max_keys, amd_summary, d1, pre).
 *
 * The synthetic fixtures in the other HottestSectors.* files pin the rules;
 * this one pins that the SHAPES the backend really serves draw: the 1▼ / 2▼
 * marks from the served plan, every column header incl. Next ER, the ⓘ sheet
 * with the served explainer (the "16 days" is the live research-cache TTL),
 * the served tier label on hover, rows in served order, and nothing printed
 * as NaN / undefined / a raw sort key. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import REAL from './__fixtures__/hottest_real_2026_09_28.json';
import { HottestSectors, THEME_LABELS, colLabel, visibleCols } from './HottestSectors';
import type { HsPayload } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const D = REAL as unknown as HsPayload & {
  sortable: string[];
  quality_info: {
    points: { label: string; max: number }[];
    penalties: { label: string; points: number }[];
    tiers: { key: string; label: string }[];
    blank: string[];
    measured_note: string;
    fundamentals_as_of: { oldest: string; newest: string };
  };
};
const QI = D.quality_info;

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null, get length() { return m.size; },
  } as Storage;
}

/** The real answer for the request it answers. The two intermediate clicks
 *  (the first read on 5 days, the plain click on Quality) get the same rows
 *  with the plan fields echoing THEIR request — nothing is asserted on them;
 *  every assertion runs after the request the fixture answers. */
function stub() {
  const hottest: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const s = String(url);
    if (s.includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    let body: unknown = REAL;
    if (s.includes('/rotation/hottest')) {
      hottest.push(s);
      const u = new URL(s, 'http://x');
      const thenBy = (u.searchParams.get('then_by') || '').split(',').filter(Boolean)
        .map((t) => { const [key, dir] = t.split(':'); return { key, dir }; });
      const matches = u.searchParams.get('sort') === D.sorted_by
        && u.searchParams.get('dir') === D.sorted_dir
        && JSON.stringify(thenBy) === JSON.stringify(D.sorted_then_by);
      if (!matches) {
        body = { ...REAL, sorted_by: u.searchParams.get('sort'), sorted_dir: u.searchParams.get('dir'),
                 sorted_then_by: thenBy };
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  }));
  return hottest;
}
const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

const headBtn = (label: string) =>
  screen.getAllByRole('button').find((b) => b.classList.contains('hs-sort')
    && (b.textContent || '').startsWith(label))!;

/** Plain click Quality, then shift-click Q EPS — the request the fixture answers. */
async function toServedPlan(hottest: string[]) {
  await screen.findByText(/Technology/);
  fireEvent.click(headBtn(colLabel('eq_score', D)));
  await waitFor(() => expect(hottest.at(-1)).toContain('sort=eq_score&dir=desc'));
  await waitFor(() => expect(headBtn(colLabel('eq_score', D)).textContent).toMatch(/▼$/));
  fireEvent.click(headBtn(colLabel('q_eps_yoy', D)), { shiftKey: true });
  await waitFor(() => expect(hottest.at(-1)).toContain('sort=eq_score&dir=desc&then_by=q_eps_yoy%3Adesc'));
  await waitFor(() => expect(headBtn(colLabel('q_eps_yoy', D)).textContent).toContain('2▼'));
}

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage());
  _resetSignalWatchlist(); _resetBounceRoomCache();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('the real 2026-09-28 payload through <HottestSectors/>', () => {
  it('the fixture is the multi-sorted read it claims to be', () => {
    expect(D.sorted_by).toBe('eq_score');
    expect(D.sorted_dir).toBe('desc');
    expect(D.sorted_then_by).toEqual([{ key: 'q_eps_yoy', dir: 'desc' }]);
    expect(D.sort_max_keys).toBe(3);
    // the tie the secondary exists for: ai_semis' three names all at 90
    const semis = (D.themes ?? []).find((t) => t.group === 'ai_semis')!;
    expect(semis.names.map((n) => n.eq_score)).toEqual([90, 90, 90]);
    const q = semis.names.map((n) => n.q_eps_yoy as number);
    expect(q[0]).toBeGreaterThan(q[1]);
    expect(q[1]).toBeGreaterThan(q[2]);
  });

  it('headers: Quality 1▼, Q EPS 2▼, every visible column present incl. Next ER', async () => {
    const hottest = stub();
    const { container } = view();
    await toServedPlan(hottest);
    const ths = Array.from(container.querySelectorAll('table.hs-table thead th'));
    const cols = visibleCols(D);
    expect(ths.length).toBe(1 + cols.length);
    cols.forEach((c, i) => expect(ths[i + 1].textContent || '').toContain(colLabel(c.key, D)));
    expect(cols.map((c) => c.key)).toContain('next_earnings');
    expect(ths.at(-1)!.textContent).toContain(colLabel('next_earnings', D));

    const qTh = headBtn(colLabel('eq_score', D)).closest('th')!;
    const eTh = headBtn(colLabel('q_eps_yoy', D)).closest('th')!;
    expect(headBtn(colLabel('eq_score', D)).textContent).toBe(`${colLabel('eq_score', D)} 1▼`);
    expect(headBtn(colLabel('q_eps_yoy', D)).textContent).toBe(`${colLabel('q_eps_yoy', D)} 2▼`);
    expect(qTh.getAttribute('aria-sort')).toBe('descending');
    expect(eTh.getAttribute('data-sort-priority')).toBe('2');
    // NEGATIVE: the secondary is not announced as THE sort; no other column carries a mark
    expect(eTh.getAttribute('aria-sort')).toBe('none');
    for (const b of Array.from(container.querySelectorAll('button.hs-sort'))) {
      const t = b.textContent || '';
      if (t.startsWith(colLabel('eq_score', D)) || t.startsWith(colLabel('q_eps_yoy', D))) continue;
      expect(t).not.toMatch(/[▼▲]/);
    }
    // "ranked on" names the served tie-break by its label
    const then = container.querySelector('button.hs-then')!;
    expect(then.textContent).toContain(colLabel('q_eps_yoy', D));
  });

  it('ⓘ Quality opens the served explainer (16-day TTL from the live read)', async () => {
    const hottest = stub();
    view();
    await toServedPlan(hottest);
    const n = hottest.length;
    fireEvent.click(screen.getByRole('button', { name: 'What is Quality score?' }));
    const dlg = screen.getByRole('dialog', { name: 'Quality score' });
    const t = dlg.textContent || '';
    expect(t).toContain(QI.measured_note);
    for (const p of QI.points) { expect(t).toContain(p.label); expect(t).toContain(`${p.max} pts`); }
    for (const p of QI.penalties) { expect(t).toContain(p.label); expect(t).toContain(`−${p.points} pts`); }
    for (const tr of QI.tiers) expect(t).toContain(tr.label);
    for (const b of QI.blank) expect(t).toContain(b);
    expect(t).toContain('16 days');
    expect(within(dlg).getByTestId('hs-qi-asof').textContent)
      .toContain(`cached ${QI.fundamentals_as_of.oldest} → ${QI.fundamentals_as_of.newest} ET`);
    // NEGATIVE: no cite, no author, no returns claim, no cadence, no NaN
    expect(t).not.toMatch(/p\.\s?\d|Minervini|\bedge\b|\bpredicts\b|\bweek|NaN|undefined|bounce/i);
    // NEGATIVE: opening it fired no read
    expect(hottest.length).toBe(n);
  });

  it('rows print in served order; the Quality hover is the served tier label', async () => {
    const hottest = stub();
    const { container } = view();
    await toServedPlan(hottest);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(container.querySelectorAll('tr.hs-name').length).toBeGreaterThan(0));

    const groupRows = Array.from(container.querySelectorAll('tr.hs-sector, tr.hs-industry'))
      .map((tr) => (tr.querySelector('button.hs-disc')?.textContent || '').replace(/^[▾▸]\s*/, ''));
    const expGroups: string[] = [];
    const expNames: string[] = [];
    for (const t of D.themes ?? []) { expGroups.push(THEME_LABELS[t.group] || t.group); expNames.push(...t.names.map((r) => r.symbol)); }
    for (const s of D.sectors) {
      expGroups.push(s.group);
      for (const i of s.industries) { expGroups.push(i.group); expNames.push(...i.names.map((r) => r.symbol)); }
    }
    expect(groupRows).toEqual(expGroups);
    const nameRows = Array.from(container.querySelectorAll('tr.hs-name'))
      .map((tr) => /open (\S+) in a new tab/.exec(tr.getAttribute('title') || '')?.[1]);
    expect(nameRows).toEqual(expNames);

    // hover: every name's Quality cell carries the SERVED label of its tier
    const qIdx = 1 + visibleCols(D).findIndex((c) => c.key === 'eq_score');
    const all = [...(D.themes ?? []).flatMap((t) => t.names), ...D.sectors.flatMap((s) => s.industries.flatMap((i) => i.names))];
    const trs = Array.from(container.querySelectorAll('tr.hs-name'));
    trs.forEach((tr, k) => {
      const tier = all[k].eq_tier as string | null | undefined;
      const want = tier ? QI.tiers.find((x) => x.key === tier)?.label ?? tier : null;
      const cell = tr.children[qIdx] as HTMLElement;
      expect(cell.getAttribute('title')).toBe(want);
    });
    // NEGATIVE: a raw tier key never reaches the hover when a label was served
    const mu = trs[expNames.indexOf('MU')].children[qIdx] as HTMLElement;
    expect(mu.getAttribute('title')).toBe(QI.tiers.find((x) => x.key === 'code33')!.label);
    expect(mu.getAttribute('title')).not.toBe('code33');
  });

  it('NEGATIVE: nothing on screen reads NaN / undefined / bounce or a raw sort key', async () => {
    const hottest = stub();
    const { container } = view();
    await toServedPlan(hottest);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(container.querySelectorAll('tr.hs-name').length).toBeGreaterThan(0));
    const text = container.textContent || '';
    expect(text).not.toMatch(/\bNaN\b|undefined|bounce/i);
    for (const k of D.sortable.filter((x) => x.includes('_'))) expect(text).not.toContain(k);
  });
});

describe('gated snapshot of the REAL payload for the real-browser probe', () => {
  it('writes the rendered board when HS_LAYOUT_SNAPSHOT is set (expand-all on)', async () => {
    const out = (globalThis as { process?: { env?: Record<string, string | undefined> } })
      .process?.env?.HS_LAYOUT_SNAPSHOT;
    if (!out) return;
    const hottest = stub();
    const { container } = view();
    await toServedPlan(hottest);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(container.querySelectorAll('tr.hs-name').length).toBeGreaterThan(0));
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    (mod?.default || mod).writeFileSync(out, container.innerHTML, 'utf8');
  });
});
