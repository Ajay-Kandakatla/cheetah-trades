import { describe, expect, it } from 'vitest';
import { DEFAULT_WINDOW, FALLBACK_WINDOWS, bandLabel, distanceLabel, evidenceLabel,
  headline, money, normalizeSymbol, parseWindow, recencyLabel, recentCount,
  shortHistoryNote, supportQuery, testedCount,
  type SupportLevel, type SupportPayload,
  priceAsOf,
  DEFAULT_TF, FALLBACK_TIMEFRAMES, STRUCTURE_TIMEFRAMES, RETIRED_TIMEFRAMES,
  FRAME_WINDOW, frameFor, parseTf, retiredTf, windowForFrame, zoomApplies,
  SEPA_SUPPLY_WINDOW, windowsForFrame
} from './supportLevels';
import { tvChartUrl } from './tvChart';

function lvl(over: Partial<SupportLevel> = {}): SupportLevel {
  return {
    lo: 148.22, hi: 152.74, mid: 150.48, origin: 'demand', touches: 4,
    strength: 72, bars_since_test: 5, oldest_touch_bars: 40, recent: true,
    tested: true,
    distance_pct: 2.4,
    ...over,
  };
}

describe('parseWindow', () => {
  it('falls back to the default on junk rather than throwing', () => {
    // '5y' left this list on 2026-08-25 — it is a real window now.
    for (const junk of ['', '  ', '10y', 'monthly', null, undefined]) {
      expect(parseWindow(junk)).toBe(DEFAULT_WINDOW);
    }
  });

  it('accepts every window the backend offers', () => {
    for (const w of FALLBACK_WINDOWS) expect(parseWindow(w.key)).toBe(w.key);
  });

  it('is case- and whitespace-insensitive', () => {
    expect(parseWindow('  6M ')).toBe('6m');
  });

  it('validates against the list the SERVER offered, not the hardcoded one', () => {
    // A window retired backend-side must degrade to the default, not 404.
    const offered = [{ key: '3m', label: '3 months', bars: 63 }];
    expect(parseWindow('1y', offered)).toBe(DEFAULT_WINDOW);
    expect(parseWindow('3m', offered)).toBe('3m');
  });

  it('the default is one of the offered windows', () => {
    expect(FALLBACK_WINDOWS.some((w) => w.key === DEFAULT_WINDOW)).toBe(true);
  });
});

describe('normalizeSymbol', () => {
  it('upper-cases and strips what a US ticker cannot contain', () => {
    expect(normalizeSymbol(' $nvda, ')).toBe('NVDA');
    expect(normalizeSymbol('brk.b')).toBe('BRK.B');
    expect(normalizeSymbol('rds-a')).toBe('RDS-A');
  });

  it('answers empty for nothing, never undefined', () => {
    for (const junk of ['', '   ', null, undefined, '!!!']) {
      expect(normalizeSymbol(junk)).toBe('');
    }
  });

  it('caps length so a pasted paragraph cannot become a query', () => {
    expect(normalizeSymbol('A'.repeat(400)).length).toBe(12);
  });
});

describe('supportQuery', () => {
  it('always sends the symbol', () => {
    expect(supportQuery({ symbol: 'nvda', window: '3m' })).toContain('symbol=NVDA');
  });

  it('omits the window when it is the default, so shared URLs stay short', () => {
    expect(supportQuery({ symbol: 'NVDA', window: DEFAULT_WINDOW }))
      .not.toContain('window');
    expect(supportQuery({ symbol: 'NVDA', window: '1m' })).toContain('window=1m');
  });
});

describe('formatting', () => {
  it('money never prints NaN or undefined', () => {
    expect(money(148.2)).toBe('$148.20');
    for (const junk of [null, undefined, NaN, Infinity]) {
      expect(money(junk as any)).toBe('—');
    }
  });

  it('a band is printed as a RANGE, never a single number', () => {
    // A stop placed at the midpoint of a support sits inside it.
    expect(bandLabel(lvl())).toBe('$148.22 – $152.74');
    expect(bandLabel(null)).toBe('—');
  });

  it('distance reads "below" for support and "+" for overhead', () => {
    expect(distanceLabel(lvl({ distance_pct: 2.4 }))).toBe('2.4% below');
    expect(distanceLabel(lvl({ distance_pct: 3.1 }), 'overhead')).toBe('+3.1%');
  });

  it('says "at price" instead of a rounded-to-zero percentage', () => {
    // DHI's overhead was 0.01% above price on 2026-08-19. "+0.0%" reads as a
    // broken number; the level being AT price is the point of the row.
    expect(distanceLabel(lvl({ distance_pct: 0.01 }), 'overhead')).toBe('at price');
    expect(distanceLabel(lvl({ distance_pct: 0.03 }))).toBe('at price');
    expect(distanceLabel(lvl({ distance_pct: 0.2 }))).toBe('0.2% below');
  });

  it('a negative support distance says ABOVE rather than "-0.4% below"', () => {
    expect(distanceLabel(lvl({ distance_pct: -0.4 }))).toBe('0.4% above');
  });

  it('distance degrades rather than printing NaN%', () => {
    expect(distanceLabel(lvl({ distance_pct: null }))).toBe('—');
    expect(distanceLabel(lvl({ distance_pct: NaN }))).toBe('—');
    expect(distanceLabel(null)).toBe('—');
  });
});

describe('recencyLabel — "I want look at recent support levels as well"', () => {
  it('counts in SESSIONS, because bars are not calendar days', () => {
    expect(recencyLabel(lvl({ bars_since_test: 5 }))).toBe('tested 5 sessions ago');
  });

  it('reads naturally at 0 and 1', () => {
    expect(recencyLabel(lvl({ bars_since_test: 0 }))).toBe('tested today');
    expect(recencyLabel(lvl({ bars_since_test: 1 }))).toBe('tested yesterday');
  });

  it('says untested rather than inventing a number when the field is missing', () => {
    expect(recencyLabel(lvl({ bars_since_test: null })))
      .toBe('not tested in this window');
    expect(recencyLabel(lvl({ bars_since_test: NaN as any })))
      .toBe('not tested in this window');
  });
});

describe('evidenceLabel', () => {
  it('leads with the touch count and singularises it', () => {
    expect(evidenceLabel(lvl({ touches: 4 }))).toBe('4 touches');
    expect(evidenceLabel(lvl({ touches: 1 }))).toBe('1 touch');
  });

  it('flags a level that used to be resistance — a weaker claim', () => {
    expect(evidenceLabel(lvl({ origin: 'supply', touches: 3 })))
      .toBe('3 touches · was resistance');
  });

  it('does not surface strength, which is only comparable within one zoom', () => {
    expect(evidenceLabel(lvl({ strength: 99 }))).not.toContain('99');
  });
});

describe('recentCount', () => {
  it('counts only the flagged levels', () => {
    expect(recentCount([lvl({ recent: true }), lvl({ recent: false }),
                        lvl({ recent: true })])).toBe(2);
  });

  it('is 0 for nothing rather than throwing', () => {
    expect(recentCount(null)).toBe(0);
    expect(recentCount([])).toBe(0);
  });
});

describe('headline', () => {
  const base: SupportPayload = {
    symbol: 'DHI', window: '3m', window_label: '3 months',
    windows: FALLBACK_WINDOWS, recent_bars: 21, last_price: 155.0,
  };

  it('leads with the error when there is one', () => {
    expect(headline({ ...base, error: 'No price data for ZZZZ.' }))
      .toBe('No price data for ZZZZ.');
  });

  it('says so when price is standing INSIDE a band', () => {
    const out = headline({ ...base, standing_in: lvl(), supports: [] });
    expect(out).toContain('INSIDE');
    expect(out).toContain('$148.22 – $152.74');
  });

  it('reports the nearest support with its distance, evidence and recency', () => {
    const out = headline({ ...base, supports: [lvl()] });
    expect(out).toContain('$148.22 – $152.74');
    expect(out).toContain('2.4% below');
    expect(out).toContain('4 touches');
    expect(out).toContain('tested 5 sessions ago');
  });

  it('says plainly when there is nothing below — never a fabricated level', () => {
    expect(headline({ ...base, supports: [] })).toContain('No band below');
  });

  it('answers empty for no payload', () => {
    expect(headline(null)).toBe('');
  });
});

describe('shortHistoryNote', () => {
  it('warns when the frame could not cover the window asked for', () => {
    const note = shortHistoryNote({
      symbol: 'IPO', window: '6m', window_label: '6 months',
      windows: FALLBACK_WINDOWS, recent_bars: 21,
      short_history: { have: 30, asked: 126 },
    });
    expect(note).toContain('30');
    expect(note).toContain('126');
  });

  it('is silent when the window was fully covered', () => {
    expect(shortHistoryNote({
      symbol: 'NVDA', window: '6m', window_label: '6 months',
      windows: FALLBACK_WINDOWS, recent_bars: 21, short_history: null,
    })).toBe('');
    expect(shortHistoryNote(null)).toBe('');
  });
});


describe('tested vs single-touch — found in the live smoke test 2026-08-19', () => {
  it('spells out a single-touch level rather than leaving it to be inferred', () => {
    // NVDA's nearest support at EVERY zoom was one touch, 0.03% below price.
    // "1 touch" alone reads as a small number, not as "this is not a floor".
    expect(evidenceLabel(lvl({ touches: 1, tested: false })))
      .toBe('1 touch · single low');
    expect(evidenceLabel(lvl({ touches: 4, tested: true }))).toBe('4 touches');
  });

  it('carries the caveat into the headline, where the decision is read', () => {
    const base: SupportPayload = {
      symbol: 'NVDA', window: '1m', window_label: '1 month',
      windows: FALLBACK_WINDOWS, recent_bars: 21, last_price: 217.56,
    };
    expect(headline({ ...base, supports: [lvl({ tested: false, touches: 1 })] }))
      .toContain('not a tested floor');
    expect(headline({ ...base, supports: [lvl({ tested: true })] }))
      .not.toContain('not a tested floor');
  });

  it('counts tested levels separately from recent ones — neither implies the other', () => {
    const levels = [
      lvl({ recent: true, tested: false }),    // yesterday's low, once
      lvl({ recent: false, tested: true }),    // held four times, last year
    ];
    expect(recentCount(levels)).toBe(1);
    expect(testedCount(levels)).toBe(1);
    expect(testedCount(null)).toBe(0);
  });
});

// ── the overlay window (Ajay 2026-08-25) ─────────────────────────────────────
describe('overlay window', () => {
  it('parseWindow accepts "all" once the server offers it', () => {
    expect(parseWindow('all')).toBe('all');           // FALLBACK now carries it
    expect(parseWindow(' ALL ')).toBe('all');
  });

  it('evidenceLabel leads with agreement on overlay rows', () => {
    const lv = {
      lo: 223.31, hi: 230.5, mid: 226.9, origin: 'supply' as const,
      touches: 3, strength: 0, bars_since_test: 4, oldest_touch_bars: null,
      recent: true, tested: true, distance_pct: 8.5,
      windows: ['1m', '3m', '6m', '1y'], agree: 4,
    };
    expect(evidenceLabel(lv)).toBe('4 windows agree (1m, 3m, 6m, 1y) · 3 touches');
  });

  it('a one-window level is called out as the caveat it is', () => {
    const lv = {
      lo: 179.31, hi: 179.72, mid: 179.5, origin: 'demand' as const,
      touches: 1, strength: 0, bars_since_test: null, oldest_touch_bars: null,
      recent: false, tested: false, distance_pct: 12.7,
      windows: ['1y'], agree: 1,
    };
    expect(evidenceLabel(lv)).toBe('one window only (1y) · 1 touch · single low');
  });

  it('rows without overlay fields keep the exact old label', () => {
    const lv = {
      lo: 99, hi: 101, mid: 100, origin: 'demand' as const,
      touches: 3, strength: 50, bars_since_test: 2, oldest_touch_bars: 40,
      recent: true, tested: true, distance_pct: 1.0,
    };
    expect(evidenceLabel(lv)).toBe('3 touches');
  });
});


describe('priceAsOf', () => {
  const NOW = Date.parse('2026-08-26T18:00:00Z');

  it('renders both halves when both are known', () => {
    expect(priceAsOf(NOW / 1000 - 2 * 3600, '2026-08-26', NOW))
      .toBe('Prices fetched 2h ago · bars through Aug 26');
  });

  it('renders each half alone', () => {
    expect(priceAsOf(NOW / 1000 - 300, null, NOW)).toBe('Prices fetched 5m ago');
    expect(priceAsOf(null, '2026-08-25', NOW)).toBe('bars through Aug 25');
  });

  it('renders NOTHING when nothing is provable — never a fabricated stamp', () => {
    // The INTU lesson (2026-08-26): a chart that cannot say when its data
    // left the provider must say nothing, not imply "now".
    for (const [asOf, through] of [[null, null], [undefined, undefined],
                                   [0, ''], [-5, 'not-a-date'], [NaN, null]] as const) {
      expect(priceAsOf(asOf as never, through as never, NOW)).toBeNull();
    }
  });

  it('clamps clock skew instead of inventing a negative age', () => {
    expect(priceAsOf(NOW / 1000 + 600, null, NOW)).toBe('Prices fetched just now');
  });
});

/* ── FIVE frames, named by the JOB (Ajay 2026-09-22) ──────────────────────
 * > "Just simpliyfy this drop down. I wanna use this for entries during the
 * >  day and it been useless for that It does help with 6 months but when it
 * >  comes to daily charts and checking support levels for daily. at any
 * >  giving point This has been useless"
 *
 * Seventeen merged (window, tf) entries became five FRAMES plus a zoom that
 * exists only where it changes something. These pin the agreed set, the span
 * beside every name, and the pins that keep an invalid pair unreachable. */
describe('the chart control — five frames, named by the job', () => {
  it('offers EXACTLY the five agreed frames, shortest first', () => {
    expect(FALLBACK_TIMEFRAMES.map((t) => t.key))
      .toEqual(['5m_today', '24h', '15m', '60m', 'daily']);
    expect(FALLBACK_TIMEFRAMES.map((t) => t.label)).toEqual([
      'Today, for an entry', 'Last 24 hours', 'The last two weeks',
      'The last two months', 'The big picture',
    ]);
    // Rule #5: a change that ADDS options has failed. Five is the ceiling.
    expect(FALLBACK_TIMEFRAMES.length).toBeLessThanOrEqual(5);
  });

  it('every option carries a span built from its own bar size and window', () => {
    for (const t of FALLBACK_TIMEFRAMES) {
      expect(t.bar_label, `${t.key} has no bar_label`).toBeTruthy();
      expect(t.window_label, `${t.key} has no window_label`).toBeTruthy();
      // The span is the two joined BY THE SERVER (timeframes._span). Mirroring
      // it wrong here would put a false span on screen for the first paint.
      expect(t.span).toBe(`${t.bar_label} bars · ${t.window_label}`);
    }
  });

  it('answers BOTH of his asks, and says which is which', () => {
    // "I mainly need the support levels for the last 24 hours"
    const day = FALLBACK_TIMEFRAMES.find((t) => t.key === '24h')!;
    expect(day.label).toBe('Last 24 hours');
    expect(day.window_label).toMatch(/24 hours/);
    // "if you cannot do it then support level from market open but I do not
    // have to see previous days in that"
    const today = FALLBACK_TIMEFRAMES.find((t) => t.key === '5m_today')!;
    expect(today.window_label).toMatch(/today only/i);
    expect(today.window_label).toMatch(/04:00 ET/);
    // "It does help with 6 months" — the big picture keeps its zoom.
    const big = FALLBACK_TIMEFRAMES.find((t) => t.key === 'daily')!;
    expect(big.window_label).toMatch(/Zoom dropdown/);
  });

  it('NEGATIVE: no label is a bar size, and no span asserts "~2.5 sessions"', () => {
    for (const t of FALLBACK_TIMEFRAMES) {
      // The old names WERE the bar size ("15 min", "1 hour") — that is the
      // complaint. A label must name the job, never the resolution alone.
      expect(t.label, `${t.key} is still named by its bar size`)
        .not.toMatch(/^\s*(daily|\d+\s*(min|minute|hour|h|m))\b/i);
      // MEASURED 2026-09-22: a fixed BAR COUNT makes the span a function of
      // liquidity — the retired 5m_live drew 3 sessions of NVDA and 5 of PTGX
      // under one label claiming "~2.5 sessions". No surviving span may make
      // a session claim a thin name can falsify.
      expect(t.span).not.toMatch(/2\.5 sessions/);
    }
  });

  it('NEGATIVE: nothing in the offered list says "bounce"', () => {
    // Every surface he READS says reversal. `overnightLine` keeps `bouncing`
    // internally on purpose; a dropdown is not an internal.
    for (const t of FALLBACK_TIMEFRAMES) {
      expect(`${t.label} ${t.span}`).not.toMatch(/bounc/i);
    }
  });

  it('pins a daily window to every intraday frame, so no invalid pair exists', () => {
    // The window never leaves the wire — it still decides the BOARD block and
    // the named fallback, both DAILY reads. It is just not his to pick where
    // nothing he can see would change. These are the pins the merged control
    // carried before 2026-09-22; 24h inherits 5m_live's 6m.
    expect(FRAME_WINDOW).toEqual({ '5m_today': '6m', '24h': '6m', '15m': '1m', '60m': '3m' });
    expect(windowForFrame('5m_today', '1y')).toBe('6m');
    expect(windowForFrame('24h', '3y')).toBe('6m');
    expect(windowForFrame('15m', '5y')).toBe('1m');
    expect(windowForFrame('60m', 'all')).toBe('3m');
    // Daily keeps whatever zoom he is on.
    expect(windowForFrame('daily', '6m')).toBe('6m');
    expect(windowForFrame('daily', 'all')).toBe('all');
    expect(windowForFrame('daily', 'garbage')).toBe(DEFAULT_WINDOW);
    // and an unknown frame is daily, so it keeps the zoom too
    expect(windowForFrame('weekly', '3m')).toBe('3m');
  });

  it('the zoom offers only what the chosen frame can answer', () => {
    // Ajay 2026-08-29: "1 month" + "15 min" was a combination with no
    // meaning, so the two controls were merged. The merge is not undone —
    // but daily-ONLY zoom went too far and silently dropped the hourly
    // 1-week chart he asked for on 2026-09-18. A frame now offers exactly
    // the zooms its own bars can fill.
    expect(zoomApplies('daily')).toBe(true);
    expect(zoomApplies(null)).toBe(true);
    expect(zoomApplies('60m')).toBe(true);
    expect(zoomApplies('15m')).toBe(true);
    // the 5-minute frames ARE their window — nothing to zoom
    for (const k of ['5m_today', '24h']) {
      expect(zoomApplies(k), `${k} defines its own window`).toBe(false);
      expect(windowsForFrame(k)).toEqual([]);
    }
  });

  it('REGRESSION: the hourly 1-week and 2-week charts stay reachable', () => {
    // Ajay 2026-09-18: "Can you increase the bars on the weekly chart
    // please?" -> 1 week of HOURLY bars. It shipped backend-first once and
    // the picker could not express the pair, so it never reached him. The
    // five-row picker broke it the same way until the zoom went per-frame.
    for (const w of ['1w', '2w']) {
      expect(windowsForFrame('60m')).toContain(w);
      expect(windowForFrame('60m', w), `60m:${w} must survive the switch`).toBe(w);
    }
  });

  it('NEGATIVE: a frame is never sent a zoom its bars cannot fill', () => {
    // 330 hourly bars is ~47 sessions — a 5-year window would be a label
    // over bars that do not exist.
    for (const w of ['1y', '2y', '5y', 'all']) {
      expect(windowsForFrame('60m')).not.toContain(w);
      expect(windowForFrame('60m', w)).toBe('3m');   // the frame's own pin
    }
    expect(windowForFrame('15m', '1y')).toBe('1m');
  });

  it('NEGATIVE: an unknown frame gets a zoom rather than silently losing one', () => {
    expect(windowsForFrame('a-frame-added-later')).toEqual(windowsForFrame('daily'));
  });

  it('frameFor names the frame a key belongs to, and never returns undefined', () => {
    expect(frameFor('24h').label).toBe('Last 24 hours');
    expect(frameFor('nonsense').key).toBe(DEFAULT_TF);
    expect(frameFor('5m_live').key).toBe('24h');      // through the retirement
  });

  it('the structure picker is offered NO extended-hours frame', () => {
    // `frame_for` refuses them to every caller but the Support tab, so a
    // zone-map option for one would be a dropdown entry that errors.
    expect(STRUCTURE_TIMEFRAMES.map((t) => t.key)).toEqual(['15m', '60m', 'daily']);
    expect(STRUCTURE_TIMEFRAMES.some((t) => t.ext)).toBe(false);
    // NEGATIVE: and the two that ARE extended-hours are still offered on the
    // Support tab, which is the one surface allowed to draw them.
    expect(FALLBACK_TIMEFRAMES.filter((t) => t.ext).map((t) => t.key))
      .toEqual(['5m_today', '24h']);
  });
});

/* ── Live frame + overnight read (Ajay 2026-09-02) ────────────────────────── */
import { overnightLine } from './supportLevels';

describe('overnightLine — the one-line overnight read', () => {
  it('is empty without a read and says so when nothing printed', () => {
    expect(overnightLine(null)).toBe('');
    expect(overnightLine({ bars: 0, note: 'Nothing has printed since the last regular close.' }))
      .toMatch(/Nothing has printed/);
  });

  it('names the bounce with its time when a support touch held', () => {
    const line = overnightLine({
      bars: 40, low: 198.9, low_at: '2026-09-02 06:45:00-04:00', high: 204.1,
      high_at: '2026-09-02 08:10:00-04:00', last: 203.2, change_pct: -1.66,
      touches: [{ side: 'support', lo: 198.8, hi: 201.2, at: '2026-09-02 06:45:00-04:00',
                  low: 198.9, held: true, broke: false }],
    });
    expect(line).toMatch(/bounced off support \$198\.80–\$201\.20 at 06:45 ✓/);
    expect(line).toMatch(/-1\.66% vs the close/);
  });

  it('NEGATIVE: a break is called a break, never a bounce', () => {
    const line = overnightLine({
      bars: 10, low: 197.0, low_at: 'x 05:00', high: 201.0, high_at: 'x 04:10', last: 197.5,
      touches: [{ side: 'support', lo: 198.8, hi: 201.2, at: 'x 04:30', held: false, broke: true }],
    });
    expect(line).toMatch(/broke support/);
    expect(line).not.toMatch(/bounced/);
  });

  it('a clean overnight says no level touched', () => {
    expect(overnightLine({ bars: 5, low: 205, low_at: 'x 04:05', high: 206, high_at: 'x 05:00', last: 205.5, touches: [] }))
      .toMatch(/No level touched/);
  });
});


/* ── RETIRED frames still land somewhere real (Ajay 2026-09-22) ───────────
 * "Do not silently delete a frame." An old bookmark, or a tab he left open,
 * still carries `15m_open` / `5m_live`. Each resolves to the nearest
 * SURVIVING frame and the page says that it did. */
describe('retired frames — an old link still works, and says where it went', () => {
  it('names both retirements and where each one goes', () => {
    expect(Object.keys(RETIRED_TIMEFRAMES).sort()).toEqual(['15m_open', '5m_live']);
    // 15m_open -> 15m: its 26-bar session budget was measurably too thin to
    // cluster (2026-09-22: PTGX and NVDA both returned NO support band). The
    // alias points at 15m rather than 5m_today because 15m is the nearest key
    // that resolves on EVERY surface — the structure endpoints refuse an
    // extended-hours frame, so an old /zones?tf=15m_open link would error.
    expect(RETIRED_TIMEFRAMES['15m_open'].to).toBe('15m');
    // 5m_live -> 24h: same bar size, same pre/post policy, a span that is true
    // for a thin name as well as a liquid one.
    expect(RETIRED_TIMEFRAMES['5m_live'].to).toBe('24h');
    // mirrors backend supply_demand/timeframes.RETIRED
    for (const [, v] of Object.entries(RETIRED_TIMEFRAMES)) {
      expect(FALLBACK_TIMEFRAMES.some((t) => t.key === v.to)).toBe(true);
    }
  });

  it('parseTf resolves a retired key to its successor, NOT to daily', () => {
    expect(parseTf('15m_open')).toBe('15m');
    expect(parseTf('5m_live')).toBe('24h');
    // the spellings a URL might carry, mirroring backend _ALIAS
    for (const k of ['open', 'session', '15open']) expect(parseTf(k)).toBe('15m');
    for (const k of ['5m', '5min', 'live', '5m_ext']) expect(parseTf(k)).toBe('24h');
    for (const k of ['24', 'h24', '24hr', 'last24']) expect(parseTf(k)).toBe('24h');
    for (const k of ['today', '5open', '5m_open']) expect(parseTf(k)).toBe('5m_today');
    expect(parseTf('1h')).toBe('60m');
    expect(parseTf(' 15M ')).toBe('15m');
  });

  it('retiredTf flags the case the page has to announce — and only that case', () => {
    expect(retiredTf('5m_live')).toEqual(
      { from: '5m_live', was: '5 min · live · pre/post market', to: '24h' });
    expect(retiredTf('15m_open'))
      .toEqual({ from: '15m_open', was: '15 min · from the open', to: '15m' });
    // NEGATIVE: a live frame, an alias of a live frame, junk and an empty tf
    // are NOT retirements — announcing one on an ordinary load would be noise.
    for (const k of ['24h', '15m', 'daily', '', null, undefined, 'weekly', '1h']) {
      expect(retiredTf(k as never), `${k} must not read as retired`).toBeNull();
    }
  });

  it('NEGATIVE: a retired key never falls through to Daily without a word', () => {
    for (const k of Object.keys(RETIRED_TIMEFRAMES)) {
      expect(parseTf(k)).not.toBe(DEFAULT_TF);
      expect(retiredTf(k)).not.toBeNull();
    }
  });

  it('NEGATIVE: junk still falls back to daily, silently and on purpose', () => {
    // Every surface answered on daily before timeframes existed, so that is
    // the one fallback that cannot surprise anyone — and it needs no notice,
    // because no real frame was asked for.
    for (const junk of ['', '5m_tomorrow', 'weekly', null, undefined, '15m_opne']) {
      expect(parseTf(junk)).toBe('daily');
      expect(retiredTf(junk as never)).toBeNull();
    }
  });

  it('parseTf honours the SERVED list, so a backend retirement needs no deploy', () => {
    const served = FALLBACK_TIMEFRAMES.filter((t) => t.key !== '24h');
    expect(parseTf('24h', served)).toBe(DEFAULT_TF);
    expect(parseTf('5m_live', served)).toBe(DEFAULT_TF);   // its target is gone
    expect(retiredTf('5m_live', served)).toBeNull();
  });
});

/* ── TradingView link-out stays in step (Ajay 2026-08-31) ─────────────────── */
describe('tvChartUrl — an interval for every frame that can be selected', () => {
  it('maps every offered frame to a real TradingView interval', () => {
    const want: Record<string, string> = {
      '5m_today': '5', '24h': '5', '15m': '15', '60m': '60', daily: 'D',
    };
    for (const t of FALLBACK_TIMEFRAMES) {
      expect(tvChartUrl('NVDA', t.key), `${t.key} lost its TV interval`)
        .toContain(`interval=${want[t.key]}`);
    }
  });

  it('a retired key still opens the right bar size, not daily', () => {
    expect(tvChartUrl('NVDA', '5m_live')).toContain('interval=5');
    expect(tvChartUrl('NVDA', '15m_open')).toContain('interval=15');
  });

  it('NEGATIVE: an unknown frame opens the daily chart', () => {
    expect(tvChartUrl('NVDA', 'weekly')).toContain('interval=D');
    expect(tvChartUrl('BRK-B')).toContain('symbol=BRK.B');
  });
});

describe('default zoom — 1 year on every surface (Ajay 2026-09-06)', () => {
  it('opens on 1 year and on the big-picture frame', () => {
    // Was 3m on Chart Maps and 6m on the ticker page (Ajay 2026-09-02);
    // 2026-09-06: "make support default to 1 year on all the tabs? I think
    // its safer and more accurate." 2026-09-22 moved the frame out of the
    // zoom's control, so the default is now two facts, not one composite key.
    expect(DEFAULT_WINDOW).toBe('1y');
    expect(SEPA_SUPPLY_WINDOW).toBe('1y');
    expect(DEFAULT_TF).toBe('daily');
    expect(parseWindow('')).toBe('1y');
    expect(parseWindow('garbage')).toBe('1y');
    expect(windowForFrame(DEFAULT_TF, '')).toBe('1y');
  });

  it('NEGATIVE: neither new frame became a default', () => {
    expect(DEFAULT_TF).not.toBe('24h');
    expect(DEFAULT_TF).not.toBe('5m_today');
    // an untouched tab's URL still carries no tf and no window at all
    expect(supportQuery({ symbol: 'CRDO', window: DEFAULT_WINDOW }))
      .toBe('symbol=CRDO');
  });

  it('keeps shared URLs short on the default and spells out the old default (NEGATIVE)', () => {
    expect(supportQuery({ symbol: 'NVDA', window: '1y' })).not.toContain('window');
    expect(supportQuery({ symbol: 'NVDA', window: '3m' })).toContain('window=3m');
    expect(supportQuery({ symbol: 'NVDA', window: '6m' })).toContain('window=6m');
  });

  it('the wire carries the bare frame key, never a composite', () => {
    const q = supportQuery({ symbol: 'MU', window: windowForFrame('24h', '1y'), tf: '24h' });
    expect(q).toContain('tf=24h');
    expect(q).toContain('window=6m');
    expect(q).not.toContain('%3A');
  });
});

/* ── The ZOOM LADDER SURVIVED (Ajay 2026-09-06 + 2026-09-18) ──────────────
 * "add 2 years ... also add 3 years and then keep 5 years", and "Also a
 * weekly chart for the past week and 2 week inthe charting time frames in all
 * places". Collapsing the frame picker must not cost him a single zoom: they
 * moved to the "How far back" control, which renders on the daily frame. */
describe('the zoom ladder — unchanged by the 2026-09-22 collapse', () => {
  it('still runs 1w → 2w → 1m → 3m → 6m → 1y → 2y → 3y → 5y → overlay', () => {
    expect(FALLBACK_WINDOWS.map((w) => w.key))
      .toEqual(['1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all']);
    const bars = FALLBACK_WINDOWS.filter((w) => w.key !== 'all').map((w) => w.bars);
    expect(bars).toEqual([...bars].sort((a, b) => a - b));
    expect(FALLBACK_WINDOWS.find((w) => w.key === '1w')).toEqual({ key: '1w', label: '1 week', bars: 5 });
    expect(FALLBACK_WINDOWS.find((w) => w.key === '2w')).toEqual({ key: '2w', label: '2 weeks', bars: 10 });
    expect(FALLBACK_WINDOWS.find((w) => w.key === '2y')).toEqual({ key: '2y', label: '2 years', bars: 504 });
    expect(FALLBACK_WINDOWS.find((w) => w.key === '3y')).toEqual({ key: '3y', label: '3 years', bars: 756 });
    expect(FALLBACK_WINDOWS.find((w) => w.key === '5y')).toEqual({ key: '5y', label: '5 years', bars: 1260 });
    // NEGATIVE: bars are SESSIONS. Nobody counted calendar days.
    expect(FALLBACK_WINDOWS.some((w) => w.bars === 7 || w.bars === 14)).toBe(false);
  });

  it('every zoom he asked for is still selectable and still parses', () => {
    for (const w of FALLBACK_WINDOWS) expect(parseWindow(w.key)).toBe(w.key);
    expect(parseWindow(' 1W ')).toBe('1w');
    expect(parseWindow(' 3Y ')).toBe('3y');
    // and a zoom sent with the daily frame survives the round trip
    for (const w of FALLBACK_WINDOWS) {
      expect(windowForFrame('daily', w.key)).toBe(w.key);
    }
  });

  it('NEGATIVE: an intraday frame can never carry a long zoom', () => {
    // 2y/3y/5y and the overlay are DAILY reads. Before 2026-09-22 the merged
    // control guaranteed this by listing no such pair; now the pin does.
    for (const tf of ['5m_today', '24h', '15m', '60m']) {
      for (const w of ['2y', '3y', '5y', 'all']) {
        expect(['2y', '3y', '5y', 'all']).not.toContain(windowForFrame(tf, w));
      }
    }
  });

  /* FE-5 NEGATIVE — the api-only-deploy degrade, pinned on purpose.
   * ChartMaps.tsx validates `?window=` against the FRONTEND's own list, so a
   * deploy that ships api before frontend rewrites ?window=1w to 1y. That is
   * the documented half-ship failure mode (ship `api frontend` together) —
   * do NOT "fix" it by loosening parseWindow. */
  it('a payload served before the change still renders, and an old offered list degrades 1w', () => {
    const oldOffered = FALLBACK_WINDOWS.filter((w) => w.key !== '1w' && w.key !== '2w');
    expect(parseWindow('1w', oldOffered)).toBe(DEFAULT_WINDOW);
    const stale: SupportPayload = {
      symbol: 'NVDA', window: '1m', window_label: '1 month',
      windows: oldOffered, supports: [], overhead: [],
    } as unknown as SupportPayload;
    expect(() => shortHistoryNote(stale)).not.toThrow();
    expect(shortHistoryNote(stale)).toBe('');
    expect(stale.levels_window ?? null).toBeNull();
    expect(stale.levels_fallback ?? null).toBeNull();
  });

  /* FE-7 */
  it('the thin-history note names the window the NUMBERS came from', () => {
    expect(shortHistoryNote({ short_history: { have: 3, asked: 5 } } as SupportPayload))
      .toBe('Only 3 sessions of history — less than the 5 this window asks for. '
            + 'Levels are read from what exists.');
    expect(shortHistoryNote({
      short_history: { have: 13, asked: 21 }, levels_window_label: '1 month',
    } as SupportPayload))
      .toBe('Only 13 sessions of history — less than the 21 the 1 month read asks for. '
            + 'Levels are read from what exists.');
    // NEGATIVE: the read wording never appears without a served label.
    expect(shortHistoryNote({ short_history: { have: 13, asked: 21 } } as SupportPayload))
      .not.toContain('read asks for');
  });
});


/* ── SOURCE GUARDS — the surface prints what the server sent (2026-09-22) ─── */
describe('SOURCE GUARDS — the page composes no span of its own', () => {
  /* The repo's own source-read pattern: `import.meta.url` is not a file URL
     under the vitest transform, so resolve from the frontend root instead. */
  async function readSource(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/${rel}`, 'utf8');
  }
  /* Comments carry the reasoning and quote the served sentences verbatim;
     they are not what renders. Strip them before guarding the CODE. */
  const code = (s: string) => s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

  it('NEGATIVE: the component builds no span and no level-source phrase', () => {
    // The span and the provenance are ONE served sentence each
    // (timeframes._span, support.chart_span). A surface that rebuilds either
    // can drift from the numbers beside it, which is the bug class this whole
    // change exists to remove.
    return readSource('src/components/SupportLevels.tsx').then((raw) => {
      const src = code(raw);
      // `bar_label` narrowed 2026-09-23: the component now PASSES the served
      // `levels_bar_label` to the level tables so the Last-tested column can
      // say "N x 5-minute bars ago" instead of "N sessions ago". Reading a
      // served key is the opposite of composing a span; what stays banned is
      // INTERPOLATING one into a sentence here, which is the same shape the
      // library guard below forbids.
      for (const banned of [/bars\s*·/, /04:00/, /~\s*\d+\s*session/i,
                            /\$\{[^}]*bar_label[^}]*\}\s*bars/,
                            /levels from/i, /pre\/post/i]) {
        expect(src, `SupportLevels.tsx composes span text: ${banned}`)
          .not.toMatch(banned);
      }
      // and it must positively READ the served ones
      expect(src).toMatch(/data\.chart_span/);
      expect(src).toMatch(/t\.span/);
      expect(src).toMatch(/data\.levels_fallback/);
      // …including the unit the level read counted its bars in, and the
      // scope the empty tables name. Both are served; neither is derived
      // from the frame key here (on the named fallback the frame is
      // 5-minute and the levels are daily).
      expect(src).toMatch(/data\.levels_bar_label/);
      expect(src).not.toMatch(/'5-minute'|"5-minute"/);
    });
  });

  it('NEGATIVE: the library mirrors the server span, it does not assemble one at render', () => {
    return readSource('src/lib/supportLevels.ts').then((raw) => {
      const src = code(raw);
      // Every mirrored span is a literal, checked field-by-field above. What
      // must NOT exist is a helper that builds one from parts at call time.
      expect(src).not.toMatch(/function\s+\w*[Ss]pan\w*\s*\(/);
      expect(src).not.toMatch(/\$\{[^}]*bar_label[^}]*\}\s*bars/);
    });
  });

  it('NEGATIVE: no bare Date constructor in either file', () => {
    // `new Date('2026-09-22')` parses as UTC midnight and renders as the
    // PREVIOUS day in ET. The one Date here pins an explicit midday Z.
    return Promise.all([readSource('src/lib/supportLevels.ts'),
                        readSource('src/components/SupportLevels.tsx')])
      .then(([lib, comp]) => {
        for (const [name, raw] of [['supportLevels.ts', lib],
                                   ['SupportLevels.tsx', comp]] as const) {
          const src = code(raw);
          expect(src, `${name} has a bare new Date()`).not.toMatch(/new Date\(\s*\)/);
          expect(src, `${name} builds a Date from a bare date string`)
            .not.toMatch(/new Date\(\s*['"`]\d{4}-\d{2}-\d{2}['"`]\s*\)/);
        }
        expect(lib).toMatch(/new Date\(`\$\{dataThrough\}T12:00:00Z`\)/);
      });
  });

  it('NEGATIVE: nothing the tab RENDERS says "bounce"', () => {
    // Every surface he READS says reversal (2026-09-09). The zone-room hook
    // keeps `bounce` in its identifier on purpose — internals are exempt, the
    // words on screen are not.
    return readSource('src/components/SupportLevels.tsx').then((raw) => {
      const src = code(raw)
        .replace(/useBounceRoom/g, '').replace(/BounceRoom/g, '')
        .replace(/bounce_room/g, '');
      expect(src).not.toMatch(/bounc/i);
    });
  });

  it('the frame picker is width-capped, so the long spans stay usable', () => {
    // A native <select> sizes to its WIDEST option, and the 24-hour span is a
    // long sentence. Without a cap it pushes the search box off the screen at
    // the width in his screenshot. The OPEN list still renders in full, which
    // is where the span is read.
    return Promise.all([readSource('src/styles.css'),
                        readSource('src/components/SupportLevels.tsx')])
      .then(([css, comp]) => {
        expect(comp).toMatch(/className="cm-ctl sl-ctl-frame"/);
        const rule = css.match(/\.sl-ctl-frame select \{[^}]*\}/);
        expect(rule, '.sl-ctl-frame select has no rule in styles.css').toBeTruthy();
        expect(rule![0]).toMatch(/max-width/);
        expect(rule![0]).toMatch(/text-overflow:\s*ellipsis/);
        // NEGATIVE: and it goes full-width on a phone rather than staying capped
        expect(css).toMatch(/@media \(max-width: 720px\)[\s\S]{0,200}\.sl-ctl-frame/);
      });
  });

  it('NEGATIVE: the admin email never reaches the bundle', () => {
    return Promise.all([readSource('src/lib/supportLevels.ts'),
                        readSource('src/components/SupportLevels.tsx'),
                        readSource('src/components/ZoneMap.tsx')])
      .then((srcs) => {
        for (const s of srcs) expect(s).not.toMatch(/@gmail\.com/i);
      });
  });
});
