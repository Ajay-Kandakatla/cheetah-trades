import { describe, expect, it } from 'vitest';
import {
  ON_DEFAULT_SUB, ON_LEV_HIDE, ON_LEV_PARAM, ON_OWN_PARAMS, ON_SORT_PARAM, ON_SUBS, ON_SUB_LABELS, ON_SUB_PARAM,
  fmtAge, fmtPct, fmtPrice, fmtUsdShort, onQuery, parseOnSub, srcWords, watchSet,
} from './overnightSession';

/* 🌙 Overnight session (BUILD_SPEC16 §3.7, 2026-10-19) — the tab's own params,
 * the GET query, the formatters, the ⭐ set, and the source guard: the FE types
 * no floor, clock or $ threshold (every one is served by overnight/board.py). */

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('params + subs', () => {
  it('owns its OWN param names (never the gajjala sub / sort)', () => {
    expect(ON_SUB_PARAM).toBe('on_sub');
    expect(ON_SORT_PARAM).toBe('on_sort');
    expect(ON_LEV_PARAM).toBe('on_lev');
    expect([...ON_OWN_PARAMS]).toEqual(['on_sub', 'on_sort', 'on_lev']);
    expect(ON_OWN_PARAMS).not.toContain('sub');
    expect(ON_OWN_PARAMS).not.toContain('sort');
    expect(ON_LEV_HIDE).toBe('1');
  });

  it('two subs, 🌙 session first and the default (HIS CALL #8)', () => {
    expect([...ON_SUBS]).toEqual(['session', 'gappers']);
    expect(ON_DEFAULT_SUB).toBe('session');
    expect(ON_SUB_LABELS.session).toBe('\u{1F319} Overnight session');
    expect(ON_SUB_LABELS.gappers).toBe('Gappers');
  });

  it('parseOnSub reads both subs, case-insensitively', () => {
    expect(parseOnSub('session')).toBe('session');
    expect(parseOnSub('gappers')).toBe('gappers');
    expect(parseOnSub(' GAPPERS ')).toBe('gappers');
  });

  it('NEGATIVE: an unknown, empty or missing on_sub lands on the session sub', () => {
    for (const raw of ['bogus', '', null, undefined, 'gapper', 'sessions']) expect(parseOnSub(raw as any)).toBe('session');
  });
});

describe('onQuery', () => {
  it('sends the picked sort and hide_lev=true', () => {
    const q = new URLSearchParams(onQuery({ sort: 'losers', hideLev: true }));
    expect(q.get('sort')).toBe('losers');
    expect(q.get('hide_lev')).toBe('true');
  });

  it('NEGATIVE: no sort picked and leveraged shown leave the query empty (the server echoes its default)', () => {
    expect(onQuery({})).toBe('');
    expect(onQuery({ sort: null, hideLev: false })).toBe('');
    expect(onQuery({ sort: '  ' })).toBe('');
  });
});

describe('formatters', () => {
  it('fmtPct signs and rounds', () => {
    expect(fmtPct(3.456)).toBe('+3.46%');
    expect(fmtPct(-0.4)).toBe('-0.40%');
    expect(fmtPct(0)).toBe('0.00%');
    expect(fmtPct(1.25, 1)).toBe('+1.3%');
  });

  it('fmtUsdShort K / M / B', () => {
    expect(fmtUsdShort(512)).toBe('$512');
    expect(fmtUsdShort(41_800)).toBe('$42K');
    expect(fmtUsdShort(3_250_000)).toBe('$3.3M');
    expect(fmtUsdShort(1_200_000_000)).toBe('$1.2B');
    expect(fmtUsdShort(-41_800)).toBe('-$42K');
  });

  it('fmtPrice two decimals with separators', () => {
    expect(fmtPrice(709.8)).toBe('$709.80');
    expect(fmtPrice(1549.944)).toBe('$1,549.94');
  });

  it('fmtAge whole minutes, seconds under a minute', () => {
    expect(fmtAge(936)).toBe('16 min');
    expect(fmtAge(0)).toBe('0 s');
    expect(fmtAge(42)).toBe('42 s');
  });

  it('NEGATIVE: null / NaN / Infinity never print a number', () => {
    for (const v of [null, undefined, NaN, Infinity, -Infinity]) {
      expect(fmtPct(v as any)).toBe('—');
      expect(fmtUsdShort(v as any)).toBe('—');
      expect(fmtPrice(v as any)).toBe('—');
      expect(fmtAge(v as any)).toBe('—');
    }
    expect(fmtAge(-5)).toBe('—');
  });
});

describe('srcWords (AMENDMENTS16 A1 / A4)', () => {
  it('q = the bid/ask midpoint; t = an indicative, delayed overnight trade', () => {
    expect(srcWords('q')).toBe('bid/ask midpoint');
    expect(srcWords('t')).toMatch(/indicative/);
    expect(srcWords('t')).toMatch(/delayed/);
  });

  it('NEGATIVE: a trade-based price is never called "live"', () => {
    expect(srcWords('t')).not.toMatch(/live/i);
    expect(srcWords('q')).not.toMatch(/indicative|delayed/);
  });
});

describe('watchSet (D9 — ⭐ from the in-app watchlist)', () => {
  it('upper-cases the tickers', () => {
    const s = watchSet([{ ticker: 'qqq' }, { ticker: 'TWLO' }]);
    expect(s.has('QQQ')).toBe(true);
    expect(s.has('TWLO')).toBe(true);
  });

  it('NEGATIVE: empty / missing tickers and a null list add nothing', () => {
    expect(watchSet([{ ticker: '' }, { ticker: null }, {}]).size).toBe(0);
    expect(watchSet(null).size).toBe(0);
    expect(watchSet([{ ticker: 'QQQ' }]).has('SPY')).toBe(false);
  });
});

describe('source guard — the board and the lib type no rule and no number (BUILD_SPEC16 §3.7 / §4)', () => {
  const TYPED = ['$25', '$250', '$1M', '$2 ', '20:00', '04:00', '06:45', '15 min'];
  const FILES = ['src/lib/overnightSession.ts', 'src/components/OvernightSessionBoard.tsx',
                 'src/components/OvernightTab.tsx', 'src/hooks/useOvernightSession.ts'];

  it('no floor, clock or $ literal in any of the four files', async () => {
    for (const f of FILES) {
      const src = await readSource(f);
      for (const t of TYPED) expect(src.includes(t), `${f} types "${t}"`).toBe(false);
    }
  });

  it('the board prints the served lines', async () => {
    const src = await readSource('src/components/OvernightSessionBoard.tsx');
    for (const re of [/session\??\.line/, /lines\??\.counts/, /lines\??\.price_rule/, /lines\??\.unmeasured/,
                      /lines\??\.leveraged/, /lines\??\.empty/, /lines\??\.read_old/, /last_pass\??\.line/, /disclaimer/]) {
      expect(re.test(src), re.source).toBe(true);
    }
  });

  it('NEGATIVE: the sort labels are served — none typed in the board', async () => {
    const src = await readSource('src/components/OvernightSessionBoard.tsx');
    for (const t of ['Top gainers', 'Top losers', 'Most $ traded']) expect(src.includes(t), t).toBe(false);
  });

  it('NEGATIVE: never the b-word or "fake"; never "live" outside comments in the board / lib', async () => {
    const bword = new RegExp(`${['bou', 'n'].join('')}|fak[e]`, 'i');
    for (const f of [...FILES, 'src/styles/overnight.css']) expect(bword.test(await readSource(f)), f).toBe(false);
    for (const f of ['src/lib/overnightSession.ts', 'src/components/OvernightSessionBoard.tsx']) {
      const code = (await readSource(f)).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      expect(/\blive\b/i.test(code), f).toBe(false);
    }
  });

  it('self-test: the guard catches a typed floor', () => {
    const typed = 'const x = "$25K";';
    expect(TYPED.some((t) => typed.includes(t))).toBe(true);
  });
});
