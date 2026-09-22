/* 🌀 hottestAmd — the served read, printed, and nothing else (2026-09-22).
 *
 * WHAT IS PINNED HERE
 * -------------------
 * 1. Every word on screen is the SERVED word. This file composes no sentence,
 *    so a test that asserts a sentence asserts that it came back byte-for-byte.
 * 2. NO COLOUR, on any grade. The AMD read is MEASURED INVERTED on its own
 *    claim (−4.2pp [−6.92, −1.89] against a bar inside its own live base), and
 *    `raided` — the state the 🌀 AMD tab paints GREEN — is the exact state that
 *    was measured going the wrong way. `amdCell` must return `dim` for it, and
 *    `hs-amd-good` must never come out of a cell.
 * 3. WHOLE TOKENS. `contracts.mjs` harvests `hs-[a-z0-9-]+` out of the raw TSX
 *    and fails on a class with no rule, so `amdToneClass` must never return a
 *    bare prefix for any input — junk included.
 * 4. A blank is never a zero, never an empty cell, and never wears the words of
 *    a real read ("AMD no cycle" is `turning_bullish.py:361`'s fallback for an
 *    UNGRADEABLE row — the backend refuses to lend it, and so does this).
 * 6. TWO SERVED WORDINGS, AND NO SURGERY BETWEEN THEM (2026-09-22, *"last
 *    column is hidded"*). The CELL prints the served `short`, the HOVER keeps
 *    the served long `text`. A payload with no `short` prints the long string
 *    UNCHANGED — the negative below feeds `text: 'AMD raided · 2d ago'` with no
 *    `short` and pins that the cell prints all of it, prefix included, which is
 *    the proof that this file slices nothing.
 * 5. The expand-all depth rule, which is load-bearing rather than cosmetic: in
 *    the DEFAULT view a sector's names hang off the INDUSTRY caret, so ⊞ has to
 *    reach the industries — but never the 📰 news-briefing rows.
 */
import { describe, expect, it } from 'vitest';
import {
  AMD_COL, AMD_TONE_CLASS, amdCell, amdCoverageNote, amdGroupCell, amdHeadTitle,
  amdToneClass, showAmdCol,
} from './hottestAmd';
import type { HsAmd, HsAmdSummary } from './hottestAmd';
import { inheritsAll, isGroupOpen } from '../components/HottestSectors';
import type { HsOpen } from '../components/HottestSectors';

/* Shaped exactly as backend/rotation/hottest_amd.py serves it. Every string
 * here stands in for a served one — none of it is composed on this surface. */
const HONESTY =
  '🌀 AMD is the app’s manipulation read: … IT IS MEASURED INVERTED ON ITS OWN CLAIM. '
  + '51.9% vs 56.1%, −4.2pp [−6.92, −1.89] … It sorts nothing, filters nothing, '
  + 'orders nothing, colours nothing and gates nothing.';
const NO_COLOUR =
  'This column is deliberately colourless. The 🌀 AMD tab paints “raided” green, but that '
  + 'is the exact state measured 51.9% vs 56.1%, −4.2pp [−6.92, −1.89] against its own placebo.';
const GROUP_NOTE =
  'No AMD state on a sector, industry or roster row. A cycle phase has no median, and a '
  + 'count over the names printed here would describe a different population.';
const HEAD_TITLE = 'Which AMD cycle phase this name is in, from the nightly sweep. ' + HONESTY;
const COVERAGE =
  '🌀 AMD read for 412 of 518 names on this board (106 not in the nightly sweep) · '
  + 'raided 61 · base failed 150 · swept Sun 21 Sep 17:20 ET.';
const STALE_NOTE =
  'The AMD sweep runs weekdays at 17:20 ET. This read is from 2026-09-18; the newest '
  + 'sweep that was due is 2026-09-19.';

const summary = (over: Partial<HsAmdSummary> = {}): HsAmdSummary => ({
  available: true, n: 518, n_known: 412, n_blank: 106,
  blank_reasons: { not_in_store: 106 }, grades: { raided: 61, failed: 150, basing: 201 },
  grade_order: ['marked_up', 'raided', 'stale', 'failed', 'basing', 'none'],
  /* Served (`_summary`'s `grade_labels`), so a consumer that needs to name a
   * grade reads the word off the wire instead of typing it a second time. */
  grade_labels: {
    marked_up: 'marked up', raided: 'raided', stale: 'raid stale',
    failed: 'base failed', basing: 'basing', none: 'no cycle',
  },
  built_at: '2026-09-21T21:20:16.344000+00:00', built_at_et: '2026-09-21T17:20:16.344000-04:00',
  built_at_date: '2026-09-21', last_session: '2026-09-19', due_session: '2026-09-19',
  stale: false, stale_note: STALE_NOTE, n_scanned: 2693, n_rows: 2682,
  honesty: HONESTY, head_title: HEAD_TITLE, group_note: GROUP_NOTE,
  no_sort_reason: 'This column does not sort.', sortable: false,
  no_colour_reason: NO_COLOUR, coloured: false,
  coverage_note: COVERAGE, unavailable_note: null, label: '🌀 AMD',
  ...over,
});

/** A KNOWN read, exactly as `read_one` builds it. `tone` is the 🌀 AMD tab's
 *  own tone, carried for fidelity — this column must not paint with it. */
const raided: HsAmd = {
  known: true, grade: 'raided', phase: 'raid', text: 'AMD raided · 2d ago',
  short: 'raided · 2d ago',
  tone: 'good', title: 'KRMN: AMD raided · 2d ago. ' + HONESTY,
  bars_ago: 2, base_bars: 34, reason: null, reason_text: null,
};
const failed: HsAmd = {
  known: true, grade: 'failed', phase: 'failed', text: 'AMD base failed · 9d ago',
  short: 'base failed · 9d ago',
  tone: 'warn', title: 'RCAT: AMD base failed · 9d ago. ' + HONESTY,
  bars_ago: 9, base_bars: 41, reason: null, reason_text: null,
};
const notInStore: HsAmd = {
  known: false, grade: null, phase: null, text: null, tone: null, title: null,
  /* A refusal has no wording of its own to shorten — `blank()` serves
   * `short: None` for exactly the reason it serves `text: None`. */
  short: null,
  bars_ago: null, base_bars: null, reason: 'not_in_store',
  /* VERBATIM `rotation.hottest_amd.REASON_TEXT['not_in_store']`. A backend
   * test reads this file and pins the two against each other, so the fixture
   * cannot drift from the sentence the board actually serves. */
  reason_text: 'Not read: this name is not in the nightly AMD sweep, so this app has no '
    + 'AMD cycle for it. A blank here means UNKNOWN — it is not a verdict, and it '
    + 'does not say the name is un-manipulated.',
};

describe('amdCell — the served read, printed', () => {
  it('the CELL prints the served SHORT and the HOVER keeps the served LONG', () => {
    const c = amdCell(raided, summary());
    expect(c.text).toBe('raided · 2d ago');
    // the long sentence is still readable — on the hover, in full
    expect(c.title).toContain('KRMN: AMD raided · 2d ago.');
    expect(c.title).toContain(HONESTY);
    // and the cell no longer repeats the word its own header already prints
    expect(c.text).not.toContain('AMD ');
    expect(c.text.length).toBeLessThan(String(raided.text).length);
  });

  it('the second grade too — the short is the SERVED one, not a rule applied here', () => {
    const c = amdCell(failed, summary());
    expect(c.text).toBe('base failed · 9d ago');
    expect(c.title).toContain('RCAT: AMD base failed · 9d ago.');
  });

  it('NEGATIVE: this file does NO string surgery — an arbitrary short is printed verbatim', () => {
    /* If the cell were derived here (text.slice(4), a regex, anything) this
     * would print "raided · 2d ago" instead of the string the server sent.
     * The two wordings are BOTH served; this file only chooses between them. */
    const c = amdCell({ ...raided, short: 'ZZ-SERVED-SHORT' }, summary());
    expect(c.text).toBe('ZZ-SERVED-SHORT');
    expect(c.text).not.toBe('raided · 2d ago');
    expect(c.title).toContain('AMD raided · 2d ago');
  });

  it('NEGATIVE: no served short (an older build) → the served LONG text, unchanged', () => {
    for (const s of [undefined, null, '', '   ']) {
      const c = amdCell({ ...raided, short: s as string | null }, summary());
      // the whole served sentence, prefix included — never a locally composed
      // "raided · 2d ago" stripped out of it
      expect(c.text).toBe('AMD raided · 2d ago');
      expect(c.text).not.toBe('raided · 2d ago');
      expect(c.tone).toBe('dim');
    }
  });

  it('NEGATIVE: a `good` tone still renders dim — green on the inverted state is a ranking', () => {
    const c = amdCell(raided, summary());
    expect(c.tone).toBe('dim');
    expect(amdToneClass(c.tone)).toBe('hs-amd-dim');
    expect(amdToneClass(c.tone)).not.toBe(AMD_TONE_CLASS.good);
    expect(c.title).toContain(NO_COLOUR);
  });

  it('NEGATIVE: a `warn` tone renders dim too, and the refusal is on the hover', () => {
    const c = amdCell(failed, summary());
    expect(c.tone).toBe('dim');
    expect(amdToneClass(c.tone)).toBe('hs-amd-dim');
    expect(c.title).toContain(NO_COLOUR);
  });

  it('NEGATIVE: no cell ever yields hs-amd-good or hs-amd-warn, for ANY served tone', () => {
    for (const t of ['good', 'warn', 'muted', '', null, undefined, 'bad']) {
      const c = amdCell({ ...raided, tone: t as string | null }, summary());
      expect(c.tone).toBe('dim');
      expect(amdToneClass(c.tone)).toBe('hs-amd-dim');
    }
  });

  it('NEGATIVE: known:false → em-dash with the SERVED reason, never "no cycle" or a zero', () => {
    const c = amdCell(notInStore, summary());
    expect(c.text).toBe('—');
    expect(c.text).not.toBe('0');
    expect(c.tone).toBe('dim');
    expect(c.title).toBe(notInStore.reason_text);
    /* NEVER the words of a real read: "AMD no cycle" is what
     * turning_bullish.py:361's `or table["none"]` fallback would lend an
     * UNGRADEABLE row. The sentence must instead say, in as many words, that a
     * blank is neither of the two things it looks like. */
    /* The words of a REAL read must not appear at all, not even inside a
     * denial: a hover skimmed at speed reads the words, not the negation.
     * What must appear is the MEANING — unknown, and not a claim that the
     * name is un-manipulated. Same belt as the backend's REASON_TEXT. */
    expect(c.title.toLowerCase()).not.toContain('no cycle');
    expect(c.title.toLowerCase()).not.toContain('clean');
    expect(c.title.toUpperCase()).toContain('UNKNOWN');
    expect(c.title.toLowerCase()).toContain('un-manipulated');
    /* THE SHORT FORM DOES NOT OPEN A SECOND DOOR. `_grade_label('none')`
     * legitimately returns "no cycle" for a REAL read, so the rule that must
     * stay pinned is the narrow one: a REFUSAL wears none of the grade words,
     * in the cell or on the hover. Read them off the wire, do not type them. */
    const words = Object.values(summary().grade_labels || {});
    expect(words).toContain('no cycle');
    for (const w of words) {
      expect(c.text.toLowerCase()).not.toContain(w);
      expect(c.title.toLowerCase()).not.toContain(w);
    }
  });

  it('NEGATIVE: a blank with NO served sentence still says what a blank means', () => {
    const c = amdCell({ known: false, reason: 'no_verdict' }, summary());
    expect(c.text).toBe('—');
    expect(c.title.toUpperCase()).toContain('UNKNOWN');
    expect(c.title.toLowerCase()).not.toContain('no cycle');
  });

  it('NEGATIVE: known:true with empty text → em-dash and a "Not read" title, never a blank cell', () => {
    const c = amdCell({ ...raided, text: '' }, summary());
    expect(c.text).toBe('—');
    expect(c.title.startsWith('Not read:')).toBe(true);
    /* AND A SHORT CANNOT RESURRECT IT. The long form is the one every other
     * consumer reads (the hover, the 🌀 tab, the coverage histogram); a row
     * carrying a short and no long is a broken row, not a printable one. */
    expect(c.text).not.toContain('raided');
  });

  it('NEGATIVE: a missing cell → em-dash, not a crash and not an empty string', () => {
    for (const r of [undefined, null]) {
      const c = amdCell(r, summary());
      expect(c.text).toBe('—');
      expect(c.tone).toBe('dim');
      expect(c.title.length).toBeGreaterThan(0);
    }
  });
});

describe('amdToneClass — WHOLE tokens, for every input', () => {
  it('never returns a bare prefix, whatever it is fed', () => {
    for (const t of ['good', 'warn', 'muted', 'dim', '', '  ', null, undefined, 'WAT', '-']) {
      const cls = amdToneClass(t as string | null);
      expect(cls).toMatch(/^hs-amd-[a-z]+$/);
      expect(cls.endsWith('-')).toBe(false);
    }
  });
  it('maps the two toned states to whole tokens, for the day colour is turned on', () => {
    expect(amdToneClass('good')).toBe('hs-amd-good');
    expect(amdToneClass('warn')).toBe('hs-amd-warn');
    expect(amdToneClass('muted')).toBe('hs-amd-dim');
  });
  it('the column declares itself unsortable', () => {
    expect(AMD_COL.sortable).toBe(false);
    expect(AMD_COL.key).toBe('amd');
  });
});

describe('amdGroupCell — a group row has no AMD state, ever', () => {
  it('is ALWAYS an em-dash with the served reason, whatever it is handed', () => {
    for (const s of [summary(), summary({ grades: { raided: 500 } }), undefined, null]) {
      const c = amdGroupCell(s);
      expect(c.text).toBe('—');
      expect(c.tone).toBe('dim');
      expect(c.title.length).toBeGreaterThan(0);
    }
    expect(amdGroupCell(summary()).title).toBe(GROUP_NOTE);
  });
});

describe('showAmdCol — the SERVER decides, twice over', () => {
  it('true only when the block is there and says the read is available', () => {
    expect(showAmdCol({ amd_summary: summary() })).toBe(true);
  });
  it('NEGATIVE: false with no block at all (the member-table-unavailable shape)', () => {
    expect(showAmdCol(undefined)).toBe(false);
    expect(showAmdCol(null)).toBe(false);
    expect(showAmdCol({})).toBe(false);
    expect(showAmdCol({ amd_summary: null })).toBe(false);
  });
  it('NEGATIVE: false when the sweep document could not be read', () => {
    expect(showAmdCol({ amd_summary: summary({ available: false }) })).toBe(false);
  });
});

describe('the served sentences reach the screen byte-for-byte', () => {
  it('amdHeadTitle is the served head_title', () => {
    expect(amdHeadTitle(summary())).toBe(HEAD_TITLE);
  });
  it('amdHeadTitle falls back to a sentence rather than an empty hover', () => {
    expect(amdHeadTitle(undefined)).toContain('not read');
    expect(amdHeadTitle(summary({ head_title: undefined }))).toContain('not read');
  });
  it('amdCoverageNote is the served coverage sentence, alone, when nothing is stale', () => {
    expect(amdCoverageNote(summary())).toBe(COVERAGE);
  });
  it('a stale read adds the served stale sentence — both verbatim', () => {
    const note = amdCoverageNote(summary({ stale: true }));
    expect(note).toContain(COVERAGE);
    expect(note).toContain(STALE_NOTE);
  });
  it('NEGATIVE: an unavailable read prints the served unavailable line, not the coverage one', () => {
    const note = amdCoverageNote(summary({
      available: false, unavailable_note: '🌀 AMD: the nightly sweep document could not be read.',
    }));
    expect(note).toBe('🌀 AMD: the nightly sweep document could not be read.');
    expect(note).not.toContain(COVERAGE);
  });
  it('NEGATIVE: no block, or no sentence, prints no line at all', () => {
    expect(amdCoverageNote(undefined)).toBe(null);
    expect(amdCoverageNote(summary({ coverage_note: undefined }))).toBe(null);
  });
});

/* ── ⊞ the depth rule ──────────────────────────────────────────────────────── */

describe('inheritsAll — the depth follows the view', () => {
  it('NEGATIVE: an industry key inherits ONLY while "Break into industries" is on', () => {
    expect(inheritsAll('s:Technology|i:Semiconductors', true)).toBe(true);
    expect(inheritsAll('s:Technology|i:Semiconductors', false)).toBe(false);
  });
  it('NEGATIVE: a 📰 news-tag key NEVER inherits, in either view', () => {
    expect(inheritsAll('s:Technology|tag', true)).toBe(false);
    expect(inheritsAll('s:Technology|tag', false)).toBe(false);
  });
  it('rosters and sectors always inherit', () => {
    for (const v of [true, false]) {
      expect(inheritsAll('t:defense', v)).toBe(true);
      expect(inheritsAll('s:Technology', v)).toBe(true);
    }
  });
});

describe('isGroupOpen — a caret moved by hand always wins', () => {
  const allOpen: HsOpen = { all: true, ov: {} };
  it('an explicit close survives the blanket open, in both views', () => {
    const o: HsOpen = { all: true, ov: { 't:defense': false } };
    expect(isGroupOpen(o, 't:defense', true)).toBe(false);
    expect(isGroupOpen(o, 't:defense', false)).toBe(false);
    expect(isGroupOpen(allOpen, 't:defense', true)).toBe(true);
  });
  it('an explicit open survives the blanket close — including an industry with the checkbox off', () => {
    const o: HsOpen = { all: false, ov: { 's:Technology|i:Semiconductors': true } };
    expect(isGroupOpen(o, 's:Technology|i:Semiconductors', false)).toBe(true);
    expect(isGroupOpen(o, 's:Technology', false)).toBe(false);
  });
  it('NEGATIVE: never-chosen (all: null) is closed, and 📰 rows stay closed under ⊞', () => {
    expect(isGroupOpen({ all: null, ov: {} }, 's:Technology', true)).toBe(false);
    expect(isGroupOpen(allOpen, 's:Technology|tag', true)).toBe(false);
    expect(isGroupOpen(allOpen, 's:Technology|i:Semiconductors', false)).toBe(false);
  });
});
