import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import IpoUpcomingStrip from './IpoUpcomingStrip';
import { blankIfRecycled, isRecycled } from '../lib/ipoTab';

/* 🗓️ "Coming up" — the pinned forward-IPO strip (2026-09-20).
 *
 * Ajay: "Also potential future IPOs coming up if stocktwitz has". The rows are
 * the MEASURED 2026-09-20 forward calendar (spec §1.6: PTT 09-30, AMRO 09-23,
 * BMB 09-23), so a shape change that would have emptied his strip fails by
 * name. Pinned means pinned: it renders while the board is warming, while the
 * board has failed, and when the calendar came back with nothing. */

/* The fact sheet itself is exercised in IpoUpcomingModal.test.tsx; here it is
 * stubbed so these tests pin the WIRING — that a click opens the sheet for
 * THAT row, and that nothing opens (and nothing is fetched) before one. */
vi.mock('./IpoUpcomingModal', () => ({
  IpoUpcomingModal: ({ row, onClose }: any) => (
    <div data-testid="ipo-drill-mock" onClick={onClose}>{row.symbol}</div>
  ),
}));

const FORWARD = [
  { symbol: 'AMRO', name: 'Amaroq Minerals', date: '2026-09-23',
    exchange: 'NASDAQ Global', price: '4.00-5.00', numberOfShares: '5,000,000',
    totalSharesValue: '22500000', status: 'expected' },
  { symbol: 'BMB', name: 'Bumble Bee Foods', date: '2026-09-23',
    exchange: 'NYSE', price: '8.00', numberOfShares: '3,000,000',
    totalSharesValue: '24000000', status: 'expected' },
  { symbol: 'PTT', name: 'Portis Tech', date: '2026-09-30',
    exchange: 'NASDAQ Capital', price: '14.00-16.00', numberOfShares: '2,000,000',
    totalSharesValue: '30000000', status: 'expected' },
];

describe('IpoUpcomingStrip', () => {
  it('renders the three measured forward rows', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    expect(screen.getByTestId('ipo-upcoming-AMRO')).toBeTruthy();
    expect(screen.getByTestId('ipo-upcoming-BMB')).toBeTruthy();
    expect(screen.getByTestId('ipo-upcoming-PTT')).toBeTruthy();
    expect(screen.getByTestId('ipo-upcoming-list').children.length).toBe(3);
  });

  it('prints the price RANGE and the share count verbatim', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    const ptt = screen.getByTestId('ipo-upcoming-PTT');
    expect(ptt.textContent).toContain('14.00-16.00');
    expect(ptt.textContent).toContain('2,000,000');
    expect(ptt.textContent).toContain('2026-09-30');
    expect(ptt.textContent).toContain('expected');
  });

  it('accepts the whole board payload, not just the array', () => {
    render(<IpoUpcomingStrip data={{ upcoming: FORWARD }} />);
    expect(screen.getByTestId('ipo-upcoming-list').children.length).toBe(3);
  });

  it('renders the named empty sentence on zero rows and does NOT throw', () => {
    render(<IpoUpcomingStrip data={[]} corroboration={{ available: true }} />);
    const empty = screen.getByTestId('ipo-upcoming-empty');
    expect(empty.textContent).toContain('Finnhub calendar');
    expect(screen.queryByTestId('ipo-upcoming-list')).toBeNull();
  });

  it('renders — pinned — with no data at all (board warming or failed)', () => {
    render(<IpoUpcomingStrip />);
    expect(screen.getByTestId('ipo-upcoming-strip')).toBeTruthy();
    expect(screen.getByTestId('ipo-upcoming-empty')).toBeTruthy();
  });

  it('survives junk rows instead of taking the board down', () => {
    render(<IpoUpcomingStrip data={[null, 7, {}, FORWARD[0]] as any} />);
    expect(screen.getByTestId('ipo-upcoming-list').children.length).toBe(1);
  });

  it('says out loud when the calendar could not be read', () => {
    render(<IpoUpcomingStrip data={[]}
                             corroboration={{ available: false, reason: 'rate limit' }} />);
    expect(screen.getByTestId('ipo-upcoming-basis').textContent).toContain('rate limit');
  });

  it('prints the dropped-uncorroborated count through counts', () => {
    render(<IpoUpcomingStrip data={FORWARD}
                             corroboration={{ available: true, forward_to: '2026-10-20' }}
                             counts={{ dropped_uncorroborated: 22 }} />);
    expect(screen.getByTestId('ipo-upcoming-basis').textContent)
      .toContain('22 uncorroborated dropped');
  });

  it('prints no drop sentence on an outage, where nothing is dropped', () => {
    render(<IpoUpcomingStrip data={FORWARD}
                             corroboration={{ available: false, reason: 'rate limit' }}
                             counts={{ dropped_uncorroborated: 22 }} />);
    const basis = screen.getByTestId('ipo-upcoming-basis').textContent || '';
    expect(basis).toContain('rate limit');
    expect(basis).not.toContain('dropped');
  });

  it('renders with no counts prop at all (board warming)', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    expect(screen.getByTestId('ipo-upcoming-basis').textContent)
      .not.toContain('dropped');
  });

  it('says nothing here is measured', () => {
    render(<IpoUpcomingStrip data={FORWARD} />);
    expect(screen.getByTestId('ipo-upcoming-strip').textContent)
      .toContain('Nothing here is measured and nothing here is a signal.');
  });
});

describe('a recycled tile prints no price-derived stat', () => {
  /* The tile itself is a Chart Maps tile rendered by PatternChart; what is
   * pinned here is the RULE the tile's stats go through. */
  const recycled = { symbol: 'RECYC', recycled: true, ipo_status: 'recycled' };
  const confirmed = { symbol: 'GOODCO', recycled: false, ipo_status: 'confirmed' };

  it('blanks day-1 and week-1 even if a number arrived on the payload', () => {
    expect(blankIfRecycled(recycled, '+312.0%')).toBe('—');
    expect(blankIfRecycled(recycled, '+480.0%')).toBe('—');
  });

  it('leaves a confirmed tile alone', () => {
    expect(isRecycled(confirmed)).toBe(false);
    expect(blankIfRecycled(confirmed, '+20.0%')).toBe('+20.0%');
  });
});

describe('the symbol opens its fact sheet (2026-09-20)', () => {
  it('clicking the symbol opens the sheet for THAT row', async () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    fireEvent.click(screen.getByTestId('ipo-upcoming-open-AMRO'));
    const sheet = await screen.findByTestId('ipo-drill-mock');
    expect(sheet.textContent).toBe('AMRO');
  });

  it('opens the sheet of the row clicked, not the first row', async () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    fireEvent.click(screen.getByTestId('ipo-upcoming-open-PTT'));
    const sheet = await screen.findByTestId('ipo-drill-mock');
    expect(sheet.textContent).toBe('PTT');
  });

  it('NEGATIVE: no sheet is mounted before a click — nothing is fetched on the board build', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    expect(screen.queryByTestId('ipo-drill-mock')).toBeNull();
  });

  it('closes again, leaving the strip intact', async () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    fireEvent.click(screen.getByTestId('ipo-upcoming-open-BMB'));
    fireEvent.click(await screen.findByTestId('ipo-drill-mock'));
    expect(screen.queryByTestId('ipo-drill-mock')).toBeNull();
    expect(screen.getByTestId('ipo-upcoming-list').children.length).toBe(3);
  });

  it('every row carries a named, labelled button', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    for (const sym of ['AMRO', 'BMB', 'PTT']) {
      const b = screen.getByTestId(`ipo-upcoming-open-${sym}`);
      expect(b.tagName).toBe('BUTTON');
      expect(b.getAttribute('aria-label')).toBe(`Open ${sym} fact sheet`);
      expect(b.className).toContain('ipo-up-link');
      expect(b.textContent).toBe(sym);
    }
  });

  it('says the symbols are clickable', () => {
    render(<IpoUpcomingStrip data={FORWARD} corroboration={{ available: true }} />);
    expect(screen.getByTestId('ipo-upcoming-strip').textContent)
      .toContain('click a symbol for its fact sheet');
  });
});
