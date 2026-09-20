import { describe, it, expect } from 'vitest';
import {
  BONDE_LIVE_COST_SENTENCE, PAIR_WARN_TITLE, UNVERIFIED_TITLE,
  basisLine, etClock, heldOutSentence, isLive, periodMark, signedPct,
  tapeLabel, tierText, todayCell, type BondeD1,
} from './bondeLive';

const live = (over: Partial<BondeD1> = {}): BondeD1 => ({
  basis: 'live', live: true, market_closed: null, in_session: true,
  session_window: '9:30-16:00 ET', as_of: '2026-09-18T14:14:09+00:00',
  close_as_of: '2026-09-17', symbols: 260, live_names: 258, reason: null,
  tape_session: 'rth', note: 'live note', ...over,
});

const closed = (over: Partial<BondeD1> = {}): BondeD1 => ({
  basis: 'close', live: false, market_closed: 'weekend', in_session: false,
  session_window: '9:30-16:00 ET', as_of: null, close_as_of: '2026-09-19',
  symbols: 260, live_names: 0,
  reason: 'the market is closed (weekend)', tape_session: 'closed',
  note: 'close note', ...over,
});

describe('the Today cell says which session it is on', () => {
  it('renders a signed percent with a tone on the live basis', () => {
    expect(todayCell({ today_pct: 3.24 }, live())).toMatchObject({ text: '+3.2%', tone: 'bd-good' });
    expect(todayCell({ today_pct: -1.15 }, live())).toMatchObject({ text: '−1.1%', tone: 'bd-bad' });
    // A real minus sign, like every other percentage on this board.
    expect(todayCell({ today_pct: -1.15 }, live()).text).not.toContain('-');
  });

  it('a flat print is a number, not a blank', () => {
    // Unsigned at zero, the same convention the rest of this board's
    // percentages use — a "+" on a flat tape reads as a gain.
    expect(todayCell({ today_pct: 0 }, live()).text).toBe('0.0%');
    expect(todayCell({ today_pct: 0 }, live()).tone).toBe('bd-dim');
  });

  it('NEGATIVE — on the close basis it is an em-dash EVEN WITH a number on the row', () => {
    // The whole point: the column shares one basis. A leftover today_pct on a
    // close-basis payload must never render under a "Today" header.
    const cell = todayCell({ today_pct: 3.24 }, closed());
    expect(cell.text).toBe('—');
    expect(cell.tone).toBe('bd-dim');
    expect(cell.title).toContain('2026-09-19');
    expect(cell.title).toContain('the market is closed (weekend)');
  });

  it('NEGATIVE — a live board with no print for THIS name says so, not 0%', () => {
    const cell = todayCell({ today_pct: null }, live());
    expect(cell.text).toBe('—');
    expect(cell.title).toContain('No live price came back for this name');
  });

  it('NEGATIVE — a missing d1 is treated as close, never as live', () => {
    expect(todayCell({ today_pct: 3.2 }, null).text).toBe('—');
    expect(todayCell({ today_pct: 3.2 }, undefined).text).toBe('—');
    expect(isLive(null)).toBe(false);
  });

  it('NEGATIVE — a non-finite value is not a number', () => {
    expect(todayCell({ today_pct: NaN as number }, live()).text).toBe('—');
    expect(signedPct(Infinity)).toBe('—');
    expect(signedPct(null)).toBe('—');
  });
});

describe('the basis line', () => {
  it('names the live clock in ET', () => {
    const s = basisLine(live());
    expect(s).toContain('Today = live print');
    expect(s).toContain('as of 10:14 ET');      // 14:14 UTC in September = EDT
  });

  it('badges the tape only when it is NOT the regular session', () => {
    expect(basisLine(live())).not.toContain('pre-mkt');
    expect(basisLine(live({ tape_session: 'premarket' }))).toContain('pre-mkt');
    expect(basisLine(live({ tape_session: 'afterhours' }))).toContain('after-hrs');
    expect(tapeLabel('rth')).toBeNull();
    expect(tapeLabel(null)).toBeNull();
  });

  it('on the close basis it names the date and the calendar’s own reason', () => {
    const s = basisLine(closed());
    expect(s).toBe('Today = last close 2026-09-19 — the market is closed (weekend)');
  });

  it('NEGATIVE — a missing d1 never claims a live print', () => {
    expect(basisLine(null)).toContain('last close');
    expect(basisLine(null)).not.toContain('live print');
  });

  it('NEGATIVE — a broken as_of does not print "Invalid Date"', () => {
    expect(etClock('not-a-date')).toBeNull();
    expect(etClock(null)).toBeNull();
    expect(basisLine(live({ as_of: 'not-a-date' }))).toBe('Today = live print');
  });
});

describe('the cost sentence is THIS board’s', () => {
  it('names 2 snapshot calls and 260 names', () => {
    expect(BONDE_LIVE_COST_SENTENCE).toContain('2 Massive snapshot calls');
    expect(BONDE_LIVE_COST_SENTENCE).toContain('260');
    expect(BONDE_LIVE_COST_SENTENCE).toContain('250 per call');
  });

  it('NEGATIVE — it is never the Hottest board’s 1,721-name count', () => {
    // backend/tests/test_bonde_live.py counts the chunks off SECTION_CAP and
    // prices._SNAP_CHUNK; Hottest's sentence is 7 / 13 calls over 1,721 names.
    expect(BONDE_LIVE_COST_SENTENCE).not.toContain('1,721');
    expect(BONDE_LIVE_COST_SENTENCE).not.toMatch(/\b7 snapshot\b/);
    expect(BONDE_LIVE_COST_SENTENCE).not.toMatch(/\b13\b/);
  });
});

describe('the year-over-year pair is a TRI-state', () => {
  it('false is a visible warning', () => {
    expect(periodMark(false)).toMatchObject({ text: '⚠ pair', cls: 'bd-pair-warn',
                                              title: PAIR_WARN_TITLE });
  });

  it('NEGATIVE — null is "unverified", never a silent pass', () => {
    // 352 of 2,078 scan rows carry no period keys. Collapsing them into `true`
    // would print a clean row over a pair nobody checked.
    expect(periodMark(null)).toMatchObject({ text: 'unverified', title: UNVERIFIED_TITLE });
    expect(periodMark(undefined)).toMatchObject({ text: 'unverified' });
  });

  it('true renders nothing at all', () => {
    expect(periodMark(true)).toBeNull();
  });
});

describe('the withheld tier', () => {
  it('prints the word when there is one', () => {
    expect(tierText('explosive')).toBe('explosive');
  });

  it('NEGATIVE — a withheld tier is an em-dash, never an empty cell', () => {
    expect(tierText(null)).toBe('—');
    expect(tierText(undefined)).toBe('—');
    expect(tierText('  ')).toBe('—');
  });
});

describe('the held-out sentence comes from the SERVED note', () => {
  const note = 'His screen: 1,051 of 2,076 pass. 164 passers are held OUT of the '
    + 'tiers because their newest quarter and its ‘year-ago’ slot are not four '
    + 'fiscal quarters apart; the \u{1F680} growth board refuses the same rows. '
    + 'Listed under the board.';

  it('lifts it rather than retyping it', () => {
    const s = heldOutSentence(note);
    expect(s).toContain('164 passers are held OUT');
    expect(s).toContain('Listed under the board.');
    expect(s).not.toContain('His screen: 1,051');
  });

  it('NEGATIVE — an older payload without the sentence yields null, not invented prose', () => {
    expect(heldOutSentence('nothing to see here')).toBeNull();
    expect(heldOutSentence(null)).toBeNull();
    expect(heldOutSentence(undefined)).toBeNull();
  });
});

describe('nothing here says "bounce" on a surface he reads', () => {
  it('every exported string is in the reversal wording', () => {
    const blob = [BONDE_LIVE_COST_SENTENCE, PAIR_WARN_TITLE, UNVERIFIED_TITLE,
                  basisLine(live()), basisLine(closed()),
                  todayCell({ today_pct: 1 }, live()).title,
                  todayCell({ today_pct: 1 }, closed()).title].join(' ');
    expect(blob.toLowerCase()).not.toContain('bounce');
  });
});
