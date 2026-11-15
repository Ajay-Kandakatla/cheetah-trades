/**
 * 🌫️ DayReadLine (2026-11-15, spec §3.7 / WP-C). Ajay 2026-11-15 "yes" to an information-only day label on the Gajjala
 * tab. The component prints the served block verbatim: head + caption VISIBLE; the 8 chips + note + read rule FOLDED
 * under the served `fold_text` (C-R5); an older API without `fold_text` → unfolded; the absent state → head + caption +
 * read rule; null → nothing. The FE types no served word (C11 source guard, narrowed). 📱 phone rules on dayRead.css are
 * source guards (jsdom has no layout) with a PRE_FIX negative.
 * The fixture is a HAND copy of the §3.4 served shape — test data only.
 */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { DayReadLine } from './DayReadLine';
import type { DayRead } from '../lib/dayRead';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

const FORMS = ['GD3w_pre', 'GD4_pre', 'GD4_by1030', 'GD6b_pre', 'GD6b_by1030', 'GD7_by1030', 'LD3i_pre', 'LD9_pre'];
const ASOF = 'read 2026-11-16 10:26 ET · gg5_last_graded_at 2026-11-13 20:15 ET';
const SRC = 'MINE — test source';

/** The §3.4 served block at a 10:26 ET pass on a session day: 3 on, 3 off, 1 missing (GD7), 1 pending (GD6b_by1030). */
const READ: DayRead = {
  state: 'read', session: '2026-11-16', is_today: true, computed_at_et: '10:26 ET',
  grades_through_et: '2026-11-13 20:15 ET',
  head: '🌫️ Day read: 3 of 6 pre-registered reads on · information only · 1 not read · 1 read later today',
  counts: { on: 3, off: 3, read: 6, missing: 1, pending: 1 },
  fold_text: 'the 8 reads',
  chips: [
    { form: 'GD3w_pre', state: 'on', text: 'most setups failed this week (GD3w)', state_text: 'on',
      value_text: '6 failed · 4 held (60% failed)', why: null, asof_text: ASOF, source: SRC, reads_at: null },
    { form: 'GD4_pre', state: 'off', text: 'risk halved after losses (GD4, before the 09:30 open)', state_text: 'off',
      value_text: 'risk ×1', why: null, asof_text: ASOF, source: SRC, reads_at: '09:30' },
    { form: 'GD4_by1030', state: 'on', text: 'risk halved after losses (GD4, by 10:30)', state_text: 'on',
      value_text: 'risk ×0.5', why: null, asof_text: ASOF, source: SRC, reads_at: '10:30' },
    { form: 'GD6b_pre', state: 'off', text: 'fewer runners than usual (GD6b, the 09:29 pass)', state_text: 'off',
      value_text: '12 names at the pass · median 9', why: null, asof_text: ASOF, source: SRC, reads_at: '09:29' },
    { form: 'GD6b_by1030', state: 'pending', text: 'fewer runners than usual (GD6b, the 10:30 pass)',
      state_text: 'reads at 10:30 ET', value_text: null, why: null, asof_text: ASOF, source: SRC, reads_at: '10:30' },
    { form: 'GD7_by1030', state: 'missing', text: 'QQQ and IWM both red into 10:30 (GD7)', state_text: 'not read',
      value_text: null, why: 'QQQ/IWM bars absent by 10:30', asof_text: ASOF, source: SRC, reads_at: '10:30' },
    { form: 'LD3i_pre', state: 'on', text: 'IWM 9 EMA under 21 (LD3i)', state_text: 'on',
      value_text: '9 − 21 EMA -0.42', why: null, asof_text: ASOF, source: SRC, reads_at: null },
    { form: 'LD9_pre', state: 'off', text: 'big techs under 9 & 21 (LD9)', state_text: 'off',
      value_text: '2 big techs weak', why: null, asof_text: ASOF, source: SRC, reads_at: null },
  ],
  note: 'Read during the session from the grades on file (through 2026-11-13 20:15 ET). The nightly record is taken '
    + "after the close, so GD3w and GD4 can read differently there once the day's grades land.",
  caption: 'Information only — not a gate, not measured. In the 22 sessions studied no read flagged the worse days; '
    + 'GD6b read the opposite way (not significant after correction); LD3i and LD9 had too few days.',
  read_date_text: "Read once, when every page holds 30 recorded entry weeks forward from 2026-11-12 (the prereg's "
    + 'MEASURE_FLOOR_WEEKS rule); nothing is read before then.',
  tags: {},
};

const ABSENT: DayRead = {
  state: 'absent', session: '2026-11-16', is_today: true, computed_at_et: null, grades_through_et: null,
  head: '🌫️ Day read: no read on file for this session yet — it is read on every 5-minute 🚩 pass',
  counts: { on: 0, off: 0, read: 0, missing: 0, pending: 0 }, fold_text: null, chips: [], note: null,
  caption: READ.caption, read_date_text: READ.read_date_text, tags: {},
};

afterEach(() => cleanup());

describe('DayReadLine — the served block, verbatim', () => {
  it('head and caption are VISIBLE (outside the fold), verbatim', () => {
    render(<DayReadLine block={clone(READ)} />);
    const head = screen.getByTestId('day-read-head');
    const cap = screen.getByTestId('day-read-caption');
    expect(head.textContent).toBe(READ.head);
    expect(cap.textContent).toBe(READ.caption);
    expect(head.closest('details')).toBeNull();
    expect(cap.closest('details')).toBeNull();
    expect(screen.getByTestId('day-read').className).toBe('dr');
  });

  it('C-R5: the chips + note + read rule sit in a CLOSED <details> whose summary is the served fold_text', () => {
    render(<DayReadLine block={clone(READ)} />);
    const fold = screen.getByTestId('day-read-fold') as HTMLDetailsElement;
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(fold.open).toBe(false);
    const sum = screen.getByTestId('day-read-fold-summary');
    expect(sum.tagName).toBe('SUMMARY');
    expect(sum.textContent).toBe('the 8 reads');
    expect(fold.contains(screen.getByTestId('day-read-chips'))).toBe(true);
    expect(fold.contains(screen.getByTestId('day-read-note'))).toBe(true);
    expect(fold.contains(screen.getByTestId('day-read-date'))).toBe(true);
    expect(screen.getByTestId('day-read-note').textContent).toBe(READ.note);
    expect(screen.getByTestId('day-read-date').textContent).toBe(READ.read_date_text);
  });

  it('the 8 chips in the served order, class dr-<state>, data-state, title = asof · source', () => {
    render(<DayReadLine block={clone(READ)} />);
    const items = within(screen.getByTestId('day-read-chips')).getAllByRole('listitem');
    expect(items.map((li) => li.getAttribute('data-testid'))).toEqual(FORMS.map((f) => `day-read-chip-${f}`));
    for (const [i, c] of (READ.chips || []).entries()) {
      const li = items[i];
      expect(li.className).toBe(`dr-chip dr-${c.state}`);
      expect(li.getAttribute('data-state')).toBe(c.state);
      expect(li.getAttribute('title')).toBe(`${ASOF} · ${SRC}`);
      expect(li.textContent!.startsWith(c.text)).toBe(true);
    }
    expect(screen.getByTestId('day-read-chip-GD3w_pre').textContent)
      .toBe('most setups failed this week (GD3w): on · 6 failed · 4 held (60% failed)');
  });

  it('a missing chip prints the served "not read" + why, a pending chip the served "reads at 10:30 ET"; neither a value', () => {
    render(<DayReadLine block={clone(READ)} />);
    expect(screen.getByTestId('day-read-chip-GD7_by1030').textContent)
      .toBe('QQQ and IWM both red into 10:30 (GD7): not read — QQQ/IWM bars absent by 10:30');
    expect(screen.getByTestId('day-read-chip-GD6b_by1030').textContent)
      .toBe('fewer runners than usual (GD6b, the 10:30 pass): reads at 10:30 ET');
    expect(screen.getByTestId('day-read-chip-GD7_by1030').textContent).not.toContain(' · ');
    expect(screen.getByTestId('day-read-chip-GD6b_by1030').textContent).not.toContain(' · ');
  });

  it('NEGATIVE: the FE prints only served words — a chip with a different served state_text prints THAT', () => {
    const b = clone(READ);
    b.chips![5] = { ...b.chips![5], state_text: 'served-other' };
    render(<DayReadLine block={b} />);
    expect(screen.getByTestId('day-read-chip-GD7_by1030').textContent).toContain(': served-other');
    expect(screen.getByTestId('day-read-chip-GD7_by1030').textContent).not.toContain('not read');
  });

  it('NEGATIVE: a chip with no asof/source carries no title attribute', () => {
    const b = clone(READ);
    b.chips![0] = { ...b.chips![0], asof_text: null, source: null };
    render(<DayReadLine block={b} />);
    expect(screen.getByTestId('day-read-chip-GD3w_pre').hasAttribute('title')).toBe(false);
  });

  it('NEGATIVE: an older API without fold_text renders the chips UNFOLDED (no day-read-fold)', () => {
    const b = clone(READ);
    delete (b as any).fold_text;
    render(<DayReadLine block={b} />);
    expect(screen.queryByTestId('day-read-fold')).toBeNull();
    expect(screen.queryByTestId('day-read-fold-summary')).toBeNull();
    expect(screen.getByTestId('day-read-chips').closest('details')).toBeNull();
    expect(screen.getAllByRole('listitem')).toHaveLength(8);
    expect(screen.getByTestId('day-read-note')).toBeTruthy();
    expect(screen.getByTestId('day-read-date')).toBeTruthy();
  });

  it('absent state → head + caption + read rule; no chips, no fold, no note', () => {
    render(<DayReadLine block={clone(ABSENT)} />);
    expect(screen.getByTestId('day-read-head').textContent).toBe(ABSENT.head);
    expect(screen.getByTestId('day-read-caption').textContent).toBe(ABSENT.caption);
    expect(screen.getByTestId('day-read-date').textContent).toBe(ABSENT.read_date_text);
    expect(screen.queryByTestId('day-read-chips')).toBeNull();
    expect(screen.queryByTestId('day-read-fold')).toBeNull();
    expect(screen.queryByTestId('day-read-note')).toBeNull();
  });

  it('NEGATIVE: null / undefined / a block without a string head render NOTHING', () => {
    for (const b of [null, undefined, { state: 'read' } as DayRead, { ...clone(READ), head: 7 as any }]) {
      const { container, unmount } = render(<DayReadLine block={b} />);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });

  it('NEGATIVE: no "undefined" / "null" / "[object Object]" leaks on sparse chips', () => {
    const b: DayRead = { state: 'read', head: 'h', fold_text: 'f',
      chips: [{ form: 'GD4_pre', state: 'off', text: 't' }] };
    const { container } = render(<DayReadLine block={b} />);
    expect(container.textContent).toBe('hft');
    for (const bad of ['undefined', 'null', '[object Object]']) expect(container.textContent).not.toContain(bad);
  });
});

describe('DayReadLine — C11 source guard: the FE types no served word', () => {
  const BANNED: (string | RegExp)[] = ['not read', 'choppy', 'Information only', 'reads at', 'last session', 'ⓘ',
    'aria-label=', /['"`]on['"`]/, /bounce/i];
  const hits = (src: string) => BANNED.filter((b) => (typeof b === 'string' ? src.includes(b) : b.test(src)));

  it('DayReadLine.tsx contains none of the listed literals', async () => {
    const src = await readSource('src/components/DayReadLine.tsx');
    expect(hits(src)).toEqual([]);
  });

  it('NEGATIVE: the guard catches each literal in a source that types them', () => {
    const typed = `<span aria-label="x">ⓘ not read · reads at 10:30 · last session · Information only · choppy</span>
      {s === 'on' ? 'x' : ''} bounce`;
    expect(hits(typed)).toHaveLength(BANNED.length);
    expect(hits('const x = `on`;')).toHaveLength(1);
  });
});

describe('dayRead.css — 📱 430 px phone rules (source guards; jsdom has no layout)', () => {
  const rule = (src: string, sel: string): string | null => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)\\s*${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  const has = (decl: string | null, prop: string, val: string) =>
    !!decl && new RegExp(`(^|;|\\s)${prop}\\s*:\\s*${val.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*(;|$)`).test(decl);
  const phoneOk = (src: string) => {
    const dr = rule(src, '.dr'), chips = rule(src, '.dr-chips'), chip = rule(src, '.dr-chip'), head = rule(src, '.dr-head');
    return has(dr, 'min-width', '0') && has(dr, 'max-width', '100%')
      && has(chips, 'flex-wrap', 'wrap') && has(chips, 'min-width', '0')
      && has(chip, 'white-space', 'normal') && has(chip, 'overflow-wrap', 'anywhere') && has(chip, 'max-width', '100%')
      && has(head, 'overflow-wrap', 'anywhere') && has(head, 'min-width', '0');
  };
  /** A pre-fix stylesheet: no min-width on the block, nowrap chips, no wrap-anywhere — what overflows a 430 px board. */
  const PRE_FIX = `.dr { display: flex; flex-direction: column; }
.dr-head { font-weight: 600; }
.dr-chips { display: flex; gap: 4px; }
.dr-chip { white-space: nowrap; display: inline-block; }`;

  it('the stylesheet carries the phone rules', async () => {
    const src = await readSource('src/styles/dayRead.css');
    expect(phoneOk(src)).toBe(true);
  });

  it('NEGATIVE: the matcher rejects the PRE_FIX stylesheet', () => {
    expect(phoneOk(PRE_FIX)).toBe(false);
    expect(has(rule(PRE_FIX, '.dr-chip'), 'white-space', 'normal')).toBe(false);
    expect(has(rule(PRE_FIX, '.dr-chips'), 'flex-wrap', 'wrap')).toBe(false);
  });

  it('NEGATIVE: no red / green verdict colour on any state class', async () => {
    const src = await readSource('src/styles/dayRead.css');
    expect(src).not.toMatch(/--(red|green|bear|bull)\b|#(ef4444|22c55e|dc2626|16a34a)/i);
  });

  it('the component imports its own stylesheet', async () => {
    const src = await readSource('src/components/DayReadLine.tsx');
    expect(src).toContain("import '../styles/dayRead.css';");
  });
});
