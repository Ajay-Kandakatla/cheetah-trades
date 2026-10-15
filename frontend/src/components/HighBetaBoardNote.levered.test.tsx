/* HighBetaBoardNote — the 🔗 leveraged-ETF column + board line (2026-10-14).
 *
 * Ajay 2026-10-14, verbatim: "Can you add a short tag on these stocks for
 * their Leverage equivalents like IRE for IREN, VSTL for VST". Fixture =
 * high_beta_levered_2026_10_14.json, DUMPED from the real backend functions
 * (backend/tests/test_high_beta_levered.py pins it equal to a rebuild) over
 * the real 10-14 Massive reference fixture: IREN, NBIS, VST + AAA (no fund).
 * Every chip is asserted against the served text / parts / titles: the
 * component prints them, it composes nothing. */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HighBetaBoardNote from './HighBetaBoardNote';
import FIXTURE from './__fixtures__/high_beta_levered_2026_10_14.json';
import type { CmHighBetaBoard, CmHighBetaRow, CmLeveredChip } from '../lib/highBeta';

type Payload = { high_beta_board: CmHighBetaBoard; rows: CmHighBetaRow[] };
const F = FIXTURE as unknown as Payload;
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const BOARD = F.high_beta_board;
const ROWS = F.rows;
const row = (s: string) => ROWS.find((r) => r.symbol === s) as CmHighBetaRow;

function draw(board: unknown = BOARD, rows: unknown = ROWS) {
  return render(
    <MemoryRouter>
      <HighBetaBoardNote board={board as CmHighBetaBoard} rows={rows as CmHighBetaRow[]} onSort={vi.fn()} />
    </MemoryRouter>,
  );
}

describe('HighBetaBoardNote — 🔗 leveraged-ETF tags', () => {
  it('the served column head sits right after Symbol', () => {
    draw();
    const heads = Array.from(document.querySelectorAll('[data-testid^="cm-hb-col-"]')).map((th) => th.textContent);
    const served = (BOARD.table?.columns ?? []).map((c) => c.label);
    expect(heads).toEqual(served);
    expect(heads.slice(0, 2)).toEqual(['Symbol', 'Leveraged ETFs']);
  });

  it('each chip prints its served text; every etf part is a link to its own tape page', () => {
    draw();
    for (const s of ['IREN', 'NBIS', 'VST']) {
      const chip = row(s).levered_chip as CmLeveredChip;
      const el = screen.getByTestId(`cm-hb-lev-${s}`);
      expect(el.textContent).toBe(chip.text);
      const links = Array.from(el.querySelectorAll('a'));
      expect(links.map((a) => a.textContent)).toEqual(chip.shown);
      for (const a of links) {
        expect(a.getAttribute('href')?.startsWith(`/sepa/${a.textContent}?tab=tape`)).toBe(true);
      }
    }
    expect(screen.getByTestId('cm-hb-lev-IREN').textContent).toBe('\u{1F517} 2× IRE · IREX · IREG +1');
    expect(screen.getByTestId('cm-hb-lev-VST').textContent).toBe('\u{1F517} 2× VSTL');
  });

  it('the fund name is the link title; the "+1" title is the served rest; the badge title is the legend', () => {
    draw();
    const el = screen.getByTestId('cm-hb-lev-IREN');
    const ire = Array.from(el.querySelectorAll('a')).find((a) => a.textContent === 'IRE');
    expect(ire?.getAttribute('title')).toBe('Defiance Daily Target 2X Long IREN ETF');
    const more = Array.from(el.querySelectorAll('span')).find((sp) => sp.textContent === ' +1');
    expect(more?.getAttribute('title')).toBe(row('IREN').levered_chip?.rest);
    expect(more?.getAttribute('title')).toBe('IREZ −2×');
    expect(el.getAttribute('title')).toBe(BOARD.levered?.legend);
  });

  it('a short fund in the shown three keeps its served −2× group label', () => {
    const rows = clone(ROWS);
    const iren = rows.find((r) => r.symbol === 'IREN') as CmHighBetaRow;
    iren.levered_chip = {
      text: '\u{1F517} 2× IRE · −2× IREZ', shown: ['IRE', 'IREZ'], more: 0, rest: null,
      parts: [{ text: '\u{1F517} ' }, { text: '2× ' }, { etf: 'IRE' }, { text: ' · −2× ' }, { etf: 'IREZ' }],
    };
    draw(BOARD, rows);
    expect(screen.getByTestId('cm-hb-lev-IREN').textContent).toBe('\u{1F517} 2× IRE · −2× IREZ');
  });

  it('prints the served board line after the categories line', () => {
    draw();
    const line = screen.getByTestId('cm-hb-levered');
    expect(line.textContent).toBe(BOARD.levered?.line);
    const cats = screen.getByTestId('cm-hb-categories');
    expect(cats.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: a row with no fund draws an empty cell and no badge', () => {
    draw();
    expect(row('AAA').levered_chip).toBeNull();
    expect(screen.queryByTestId('cm-hb-lev-AAA')).toBeNull();
    expect(screen.getByTestId('cm-hb-cell-levered-AAA').textContent).toBe('');
  });

  it('NEGATIVE: a malformed chip renders nothing and never crashes', () => {
    const rows = clone(ROWS);
    const bad: unknown[] = [{ text: 'x', parts: 'nope' }, { text: 'x', parts: [{ foo: 1 }] }, 'junk', 7,
      { text: 'x', parts: [{ text: '\u{1F517} ' }] }];
    rows.slice(0, bad.length).forEach((r, i) => { (r as Record<string, unknown>).levered_chip = bad[i % bad.length]; });
    draw(BOARD, rows);
    expect(document.querySelectorAll('[data-testid^="cm-hb-lev-"]').length).toBe(0);
    expect(screen.getByTestId('cm-hb-table')).toBeTruthy();
  });

  it('NEGATIVE: no board `levered` (or no line) prints no line; the chips keep no legend title', () => {
    const b = clone(BOARD) as unknown as Record<string, unknown>;
    delete b.levered;
    draw(b);
    expect(screen.queryByTestId('cm-hb-levered')).toBeNull();
    expect(screen.getByTestId('cm-hb-lev-IREN').getAttribute('title')).toBeNull();
  });

  it('NEGATIVE: a stale map serves its own line and no row carries a chip', () => {
    const b = clone(BOARD) as unknown as Record<string, unknown>;
    b.levered = { ...(b.levered as object), state: 'stale', legend: null,
      line: '\u{1F517} Leveraged-ETF tags hidden — the Massive reference list was last read 09-20 (15 days ago; tags hide past 7 days).' };
    const rows = clone(ROWS).map((r) => ({ ...r, levered: [], levered_chip: null }));
    draw(b, rows);
    expect(screen.getByTestId('cm-hb-levered').textContent).toBe((b.levered as { line: string }).line);
    expect(document.querySelectorAll('[data-testid^="cm-hb-lev-"]').length).toBe(0);
  });

  it('NEGATIVE: while warming nothing levered is drawn', () => {
    const b = { ...clone(BOARD), state: 'warming', table: null } as unknown as Record<string, unknown>;
    draw(b);
    expect(screen.queryByTestId('cm-hb-levered')).toBeNull();
    expect(screen.queryByTestId('cm-hb-table')).toBeNull();
  });
});
