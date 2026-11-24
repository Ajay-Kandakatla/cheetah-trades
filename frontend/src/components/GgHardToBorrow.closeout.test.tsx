/* 🔒 Close-out day on the Hard to borrow tag — the frontend half (2026-11-24, spec regsho_tag §3.3 / §3.6 / §4 fe).
 *
 * Ajay 2026-11-23: "I need to know when it would like to Potentially squeeze.." · "Add a tag with date in it.."
 *
 * No production change: the backend serves the longer chip / short / label / title (the day count and the day-13 date)
 * and the real chip, label, hook and lib print them verbatim, fetch stubbed. The six worked items of §3.3 (GMEX counting
 * day 9, SMTK passed day 18, AKAN counting day 1, unknown, passed_open, reached) are copied byte for byte from the
 * planner's computed output (scratchpad regsho_tag/planner/proto_out.txt). The served `run` block and the top-level
 * `closeout` block are dropped by parseRegSho (unknown keys). Source guards: the three FE files type no rule word, no
 * weekday, no day count, do no date math for the tag and read neither `run` nor `closeout`. Display only. UNMEASURED. */
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgHardToBorrowChip, GgHardToBorrowLabel } from './GgHardToBorrow';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { parseRegSho } from '../lib/regSho';

/* ── the served strings (§3.3 worked set, Nasdaq list of 2026-11-20) ── */
const prefix = (sym: string) =>
  `🔒 Hard to borrow — ${sym} is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: fails to deliver of at `
  + 'least 10,000 shares and at least 0.5% of shares outstanding for 5 straight settlement days (SEC Regulation SHO Rule '
  + "203(c)(6)). The threshold list measures persistent fails to deliver, not a broker's borrow rate — a broker's own "
  + 'hard-to-borrow list can differ. A data label, not a signal. UNMEASURED.';
const TAILS = ' Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so '
  + 'fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver only, not '
  + 'every short position. A rule date — it says nothing about price. Not advice.';
const RULE_SENT = ' After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on '
  + 'every one of those days';
const STALE_TITLE = ' This list could not be refreshed (last good list 11/20) — the name may have left it.';

const runBlock = (over: Record<string, unknown>) => ({
  state: 'counting', days: 0, start: null, through: '2026-11-20', window_from: '2026-10-08', day11: null, day13: null,
  day13_late: null, start_by: null, missing: null, rule_days: 13, first_buy_day: 11, ...over,
});

type W = { sym: string; chip: string; short: string; label: string; title: string; stale?: boolean; run: Record<string, unknown> };
const item = (w: W) => ({
  state: 'on', symbol: w.sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: w.stale === true,
  chip: w.chip, short: w.short, label: w.label, title: w.title, run: w.run,
});

const GMEX: W = {
  sym: 'GMEX',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 9 of 13 · close-out day Fri 11/27 if it stays on',
  short: '🔒 close-out Fri 11/27 · day 9 of 13',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 9 of 13 · close-out day Fri 11/27 if it stays on',
  title: prefix('GMEX') + ' On the list 9 straight settlement days since 11/9. Day 13 = Fri 11/27 if it stays on (Mon 11/30 if '
    + "counted from each list's next open)." + RULE_SENT + '; the buying may come from day 11 (Tue 11/24) and must start by '
    + 'the next open (SEC staff FAQ 6.5, 6.7).' + TAILS,
  run: runBlock({ state: 'counting', days: 9, start: '2026-11-09', day11: '2026-11-24', day13: '2026-11-27',
    day13_late: '2026-11-30', start_by: '2026-11-30' }),
};
const SMTK: W = {
  sym: 'SMTK',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 18 · close-out day passed Fri 11/13 · still on',
  short: '🔒 close-out passed Fri 11/13 · day 18',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 18 · close-out day passed Fri 11/13 · still on the list',
  title: prefix('SMTK') + ' On the list 18 straight settlement days since 10/27. Day 13 was Fri 11/13 (Mon 11/16 if counted '
    + "from each list's next open); it is still on the list 5 settlement days later." + RULE_SENT + '. Staying listed means '
    + 'the total of fails is still over the level, not that any one fail is that old — a name leaves a list only after 5 '
    + 'straight settlement days back under it.' + TAILS,
  run: runBlock({ state: 'passed', days: 18, start: '2026-10-27', day11: '2026-11-10', day13: '2026-11-13',
    day13_late: '2026-11-16', start_by: '2026-11-16' }),
};
const AKAN: W = {
  sym: 'AKAN',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on',
  short: '🔒 close-out Wed 12/9 · day 1 of 13',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on',
  title: prefix('AKAN') + ' On the list 1 straight settlement day since 11/20. Day 13 = Wed 12/9 if it stays on (Thu 12/10 if '
    + "counted from each list's next open)." + RULE_SENT + '; the buying may come from day 11 (Mon 12/7) and must start by '
    + 'the next open (SEC staff FAQ 6.5, 6.7).' + TAILS,
  run: runBlock({ state: 'counting', days: 1, start: '2026-11-20', day11: '2026-12-07', day13: '2026-12-09',
    day13_late: '2026-12-10', start_by: '2026-12-10' }),
};
const UNKN: W = {
  sym: 'UNKN',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day count unknown',
  short: '🔒 Hard to borrow · 11/20',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day count unknown',
  title: prefix('UNKN') + ' Days on the list: not known — the Nasdaq list for 11/18 has not been read. Not advice.',
  run: runBlock({ state: 'unknown', days: 2, missing: '2026-11-18' }),
};
const OPEN_TAIL = ' On every list read for the last 30 settlement days (back to 10/8), so day 13 has passed; its date is not '
  + 'known.' + RULE_SENT + '.' + TAILS;
const OPEN: W = {
  sym: 'OPEN',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 30+ · close-out day passed · still on',
  short: '🔒 close-out passed · day 30+',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 30+ · close-out day passed · still on the list',
  title: prefix('OPEN') + OPEN_TAIL,
  run: runBlock({ state: 'passed_open', days: 30 }),
};
const RCHD_TAIL = " On the list 13 straight settlement days since 11/3. Day 13 = Fri 11/20, this list's date (Mon 11/23 if "
  + "counted from each list's next open)." + RULE_SENT + '; the buying may come from day 11 (Wed 11/18) and must start by '
  + 'the next open (SEC staff FAQ 6.5, 6.7).' + TAILS;
const RCHD_RUN = runBlock({ state: 'reached', days: 13, start: '2026-11-03', day11: '2026-11-18', day13: '2026-11-20',
  day13_late: '2026-11-23', start_by: '2026-11-23' });
const RCHD: W = {
  sym: 'RCHD',
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 13 of 13 · close-out day Fri 11/20',
  short: '🔒 close-out Fri 11/20 · day 13 of 13',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 13 of 13 · close-out day Fri 11/20',
  title: prefix('RCHD') + RCHD_TAIL,
  run: RCHD_RUN,
};
/* stale + dated (proto_out.txt: the passed_open window and the reached item, stale) */
const OPENS: W = {
  sym: 'OPENS', stale: true,
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 30+ · close-out day passed · still on · stale',
  short: '🔒 close-out passed · day 30+ · stale',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 30+ · close-out day passed · still on the list · stale',
  title: prefix('OPENS') + OPEN_TAIL + STALE_TITLE,
  run: runBlock({ state: 'passed_open', days: 30 }),
};
const RCHDS: W = {
  sym: 'RCHDS', stale: true,
  chip: '🔒 Hard to borrow · threshold security · 11/20 · day 13 of 13 · close-out day Fri 11/20 · stale',
  short: '🔒 close-out Fri 11/20 · day 13 of 13 · stale',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 13 of 13 · close-out day Fri 11/20 · stale',
  title: prefix('RCHDS') + RCHD_TAIL + STALE_TITLE,
  run: RCHD_RUN,
};

const SIX: W[] = [GMEX, SMTK, AKAN, UNKN, OPEN, RCHD];
const ALL: W[] = [...SIX, OPENS, RCHDS];
const CLOSEOUT = {
  rule: 'SEC Regulation SHO Rule 203(b)(3)', rule_days: 13, first_buy_day: 11, ok: true,
  history: { window_days: 30, read: { nasdaq: 28 }, not_read: { nasdaq: ['2026-10-09', '2026-10-08'] }, pending: false },
};
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, n: ALL.length,
  items: Object.fromEntries(ALL.map((w) => [w.sym, item(w)])),
  fault_text: null, refreshing: false, retry_after_sec: null, closeout: CLOSEOUT, ...over,
});

let body: unknown = valid();
function stub() {
  const f = vi.fn(async () => ({ ok: true, json: async () => JSON.parse(JSON.stringify(body)) }) as unknown as Response);
  vi.stubGlobal('fetch', f);
  return f;
}
const settle = (f: ReturnType<typeof vi.fn>) =>
  waitFor(() => expect(f).toHaveBeenCalled()).then(() => new Promise((r) => setTimeout(r, 10)));

function mountAll(list: W[]) {
  return render(<>{list.map((w) => (
    <div key={w.sym}>
      <GgHardToBorrowChip symbol={w.sym} testid={`c-${w.sym}`} />
      <GgHardToBorrowChip symbol={w.sym} testid={`s-${w.sym}`} form="short" />
      <GgHardToBorrowLabel symbol={w.sym} testid={`l-${w.sym}`} />
    </div>
  ))}</>);
}

describe('🔒 close-out day — the six worked items print verbatim through the real chip, label, hook and lib', () => {
  beforeEach(() => { _resetRegShoCache(); body = valid(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); });

  it('GMEX, SMTK, AKAN, unknown, passed_open, reached: chip, short and label verbatim; hover = the served title; classes unchanged; ONE GET', async () => {
    const f = stub();
    mountAll(SIX);
    await screen.findByTestId('c-GMEX');
    for (const w of SIX) {
      const c = screen.getByTestId(`c-${w.sym}`);
      const s = screen.getByTestId(`s-${w.sym}`);
      const l = screen.getByTestId(`l-${w.sym}`);
      expect(c.textContent, w.sym).toBe(w.chip);
      expect(s.textContent, w.sym).toBe(w.short);
      expect(l.textContent, w.sym).toBe(w.label);
      for (const el of [c, s, l]) expect(el.getAttribute('title'), w.sym).toBe(w.title);
      expect(c.className).toBe('cm-badge gg-htb');
      expect(s.className).toBe('cm-badge gg-htb');
      expect(l.className).toBe('cm-note gg-line gg-htb-label');
      expect(c.tagName).toBe('SPAN');
      expect(l.tagName).toBe('DIV');
    }
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('the worked lengths hold (chip 100 / short 35 / label 124 for GMEX; SMTK chip 98) — the strings were copied whole', () => {
    expect([...GMEX.chip].length).toBe(100);
    expect([...GMEX.short].length).toBe(35);
    expect([...GMEX.label].length).toBe(124);
    expect([...SMTK.chip].length).toBe(98);
    expect([...SMTK.short].length).toBe(37);
    expect([...AKAN.chip].length).toBe(99);
  });

  it('[C9] the GMEX chip and label TEXT (not only the title) carry "if it stays on" — the phone has no hover', async () => {
    stub();
    mountAll([GMEX, SMTK]);
    const c = await screen.findByTestId('c-GMEX');
    expect(c.textContent).toContain('if it stays on');
    expect(screen.getByTestId('l-GMEX').textContent).toContain('if it stays on');
    expect(screen.getByTestId('c-SMTK').textContent).not.toContain('if it stays on');
    expect(screen.getByTestId('l-SMTK').textContent).not.toContain('if it stays on');
  });

  it('items that carry the served `run` block and a payload that carries `closeout` still parse; parseRegSho drops both keys', () => {
    const p = parseRegSho(JSON.parse(JSON.stringify(valid())));
    expect(p).not.toBeNull();
    expect(Object.keys(p!.items).sort()).toEqual(ALL.map((w) => w.sym).sort());
    for (const it of Object.values(p!.items)) expect(Object.prototype.hasOwnProperty.call(it, 'run')).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(p!, 'closeout')).toBe(false);
    expect(p!.items.GMEX.short).toBe(GMEX.short);
  });

  it('stale + dated: gg-htb-stale and the text ends " · stale" on chip, short and label; hover ends with the stale sentence', async () => {
    stub();
    mountAll([OPENS, RCHDS]);
    await screen.findByTestId('c-OPENS');
    for (const w of [OPENS, RCHDS]) {
      const c = screen.getByTestId(`c-${w.sym}`);
      const s = screen.getByTestId(`s-${w.sym}`);
      const l = screen.getByTestId(`l-${w.sym}`);
      expect(c.className).toBe('cm-badge gg-htb gg-htb-stale');
      expect(s.className).toBe('cm-badge gg-htb gg-htb-stale');
      expect(l.className).toBe('cm-note gg-line gg-htb-label gg-htb-stale');
      expect(c.textContent).toBe(w.chip);
      expect(s.textContent).toBe(w.short);
      expect(l.textContent).toBe(w.label);
      for (const el of [c, s, l]) {
        expect(el.textContent, w.sym).toMatch(/ · stale$/);
        expect(el.getAttribute('title')!.endsWith(STALE_TITLE), w.sym).toBe(true);
      }
    }
  });

  it('NEGATIVE: the six un-stale items never carry gg-htb-stale', async () => {
    stub();
    mountAll(SIX);
    await screen.findByTestId('c-GMEX');
    for (const w of SIX) for (const k of ['c', 's', 'l']) {
      const el = screen.getByTestId(`${k}-${w.sym}`);
      expect(el.className, w.sym).not.toContain('gg-htb-stale');
      expect(el.textContent, w.sym).not.toMatch(/ · stale$/);
    }
  });
});

describe('🔒 close-out day — the follow-up waits the served retry_after_sec', () => {
  const flush = async () => { for (let k = 0; k < 4; k += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };
  beforeEach(() => { vi.useFakeTimers(); _resetRegShoCache(); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetRegShoCache(); });

  it('refreshing: true + retry_after_sec: 60 (history still being read) → the re-GET fires at 60 s, not at 20 s', async () => {
    let i = 0;
    const bodies = [valid({ refreshing: true, retry_after_sec: 60 }), valid()];
    const f = vi.fn(async () => {
      const b = bodies[Math.min(i, bodies.length - 1)];
      i += 1;
      return { ok: true, json: async () => JSON.parse(JSON.stringify(b)) } as unknown as Response;
    });
    vi.stubGlobal('fetch', f);
    mountAll([GMEX]);
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('c-GMEX').textContent).toBe(GMEX.chip);
    await act(async () => { await vi.advanceTimersByTimeAsync(20000); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(39999); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
    expect(screen.getByTestId('c-GMEX').textContent).toBe(GMEX.chip);
  });
});

describe('🔒 close-out day — NEGATIVES', () => {
  beforeEach(() => { _resetRegShoCache(); body = valid(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); });

  for (const k of ['short', 'chip', 'label', 'title'] as const) {
    it(`an item with a served run block but a blank ${k} → no tag at all`, async () => {
      body = valid({ items: { GMEX: { ...item(GMEX), [k]: k === 'chip' ? '  ' : '' } } });
      const f = stub();
      const { container } = mountAll([GMEX]);
      await settle(f);
      expect(container.innerHTML).toBe('<div></div>');
    });
  }

  it('closeout alone (items empty, or no items key) → nothing renders', async () => {
    for (const b of [valid({ items: {} }), { kind: 'reg_sho_threshold', closeout: CLOSEOUT, fault_text: null, refreshing: false }]) {
      _resetRegShoCache();
      body = b;
      const f = stub();
      const { container, unmount } = mountAll([GMEX, AKAN]);
      await settle(f);
      expect(container.innerHTML, JSON.stringify(Object.keys(b))).toBe('<div></div><div></div>');
      unmount();
      vi.unstubAllGlobals();
    }
  });
});

/* ── source guards (comments stripped) ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const code = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const FE_FILES = ['src/components/GgHardToBorrow.tsx', 'src/lib/regSho.ts', 'src/hooks/useRegSho.ts'];
const NO_DATE_FILES = FE_FILES.slice(0, 2);
const RULE_WORDS = /close-out|settlement|buy-in|day \d/i;
const WEEKDAY = /\b(Mon|Tue|Wed|Thu|Fri)\b/;
const DATE_USE = /\bDate\b/;
const RUN_READ = /\.(run|closeout)\b|\[\s*['"`](run|closeout)['"`]\s*\]/;

describe('🔒 close-out day — source guards', () => {
  it('the three FE files type no close-out / settlement / buy-in / day N / weekday, and read neither .run nor .closeout', async () => {
    for (const f of FE_FILES) {
      const src = code(await readSource(f));
      expect(src, f).not.toMatch(RULE_WORDS);
      expect(src, f).not.toMatch(WEEKDAY);
      expect(src, f).not.toMatch(RUN_READ);
    }
  });

  it('the component and the lib do no Date math for the tag', async () => {
    for (const f of NO_DATE_FILES) expect(code(await readSource(f)), f).not.toMatch(DATE_USE);
  });

  it('NEGATIVE: every guard fires on a planted sample; a commented word does not', () => {
    expect(code("const t = 'close-out day ' + d;")).toMatch(RULE_WORDS);
    expect(code("const t = 'settlement';")).toMatch(RULE_WORDS);
    expect(code("const t = 'buy-in';")).toMatch(RULE_WORDS);
    expect(code('const t = `day ${9} of 13`; const u = "day 9";')).toMatch(RULE_WORDS);
    expect(code("const w = 'Fri';")).toMatch(WEEKDAY);
    expect(code('const d = new Date(it.as_of);')).toMatch(DATE_USE);
    expect(code('const n = it.run.days;')).toMatch(RUN_READ);
    expect(code('const c = p.closeout?.rule_days;')).toMatch(RUN_READ);
    expect(code("const c = j['closeout'];")).toMatch(RUN_READ);
    expect(code('/* close-out day Fri 11/27, settlement, new Date(), it.run */ const x = 1;')).not.toMatch(RULE_WORDS);
    expect(code('// close-out Fri it.run\nconst x = 1;')).not.toMatch(WEEKDAY);
    expect(code('const r = runtime.closeouts;')).not.toMatch(RUN_READ);
  });

  it('📱 .gg-htb still wraps on the phone: white-space normal, overflow-wrap anywhere, min-width 0', async () => {
    const htb = rule(await readSource('src/styles/ggHardToBorrow.css'), '.gg-htb');
    expect(htb).not.toBeNull();
    expect(htb!).toMatch(/white-space:\s*normal/);
    expect(htb!).toMatch(/overflow-wrap:\s*anywhere/);
    expect(htb!).toMatch(/min-width:\s*0\b/);
  });

  it('NEGATIVE: a sheet whose .gg-htb lost the wrap fails the same matchers', () => {
    const r = rule('.gg-htb { white-space: nowrap; }', '.gg-htb')!;
    expect(r).not.toMatch(/white-space:\s*normal/);
    expect(r).not.toMatch(/overflow-wrap:\s*anywhere/);
    expect(r).not.toMatch(/min-width:\s*0\b/);
  });

  it('no b-word in this file (Reversal, never the b-word)', async () => {
    const self = await readSource('src/components/GgHardToBorrow.closeout.test.tsx');
    expect(self).not.toMatch(new RegExp('boun' + 'c', 'i'));
  });
});
