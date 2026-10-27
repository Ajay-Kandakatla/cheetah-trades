/* LanePnlBlock — 💵 P&L by lane on the Auto-Pilot Dashboard (2026-10-27).
 *
 * Ajay 2026-10-27: "Also in autopilot looks like Gajjala's strategy is making
 * money.. Anyway you can can show me which tab made money or not?"
 * BUILD_SPEC28 §3.15 / WP-C. Every word is served by trading/journal.lane_pnl;
 * these tests pin that the block prints the served strings in the served order
 * and nothing else, colors only from the served tone, renders nothing on a
 * missing payload, and fits a 430 px phone (no table, wrapping chips).
 */
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LanePnlBlock, type LanePnl, type LanePnlRow } from './LanePnlBlock';

const ROWS: LanePnlRow[] = [
  {
    key: 'options_zone', label: '🎛️ Options', url: '/trading?view=options', link_text: '→ Options tab',
    closed: 18, open: 3, held: 3, unbooked: 0, unheld: 0, wins: 9, losses: 9, win_rate_pct: 50,
    realized_pnl: -983, unrealized_pnl: 1100.25, total_pnl: 117.25, first_ts: '2026-09-06T14:00:00Z', last_ts: '2026-10-27T19:00:00Z',
    total_text: '+$117.25', record_text: '18 closed · 9 W / 9 L · 50% won', realized_text: 'realized -$983.00',
    open_text: 'open +$1,100.25 on 3 held', dates_text: '2026-09-06 → 2026-10-27', note_text: null, tone: 'up',
  },
  {
    key: 'gajjala', label: '🚩 Gajjala', url: '/trading?view=gajjala', link_text: '→ 🚩 Gajjala tab',
    closed: 5, open: 1, held: 0, unbooked: 0, unheld: 1, wins: 2, losses: 3, win_rate_pct: 40,
    realized_pnl: -232.58, unrealized_pnl: null, total_pnl: -232.58, first_ts: '2026-10-20T14:00:00Z', last_ts: '2026-10-27T19:00:00Z',
    total_text: '-$232.58', record_text: '5 closed · 2 W / 3 L · 40% won', realized_text: 'realized -$232.58',
    open_text: 'nothing held at the broker', dates_text: '2026-10-20 → 2026-10-27',
    note_text: "1 open in the lane's book but not held at the broker — no open $", tone: 'down',
  },
  {
    key: 'breakout', label: '🚀 breakout (S/D supply band)', url: '/trading?view=journal', link_text: '→ Journal',
    closed: 22, open: 0, held: 0, unbooked: 0, unheld: 0, wins: 8, losses: 14, win_rate_pct: 36.4,
    realized_pnl: -825.38, unrealized_pnl: null, total_pnl: -825.38, first_ts: '2026-09-05T14:00:00Z', last_ts: '2026-10-24T19:00:00Z',
    total_text: '-$825.38', record_text: '22 closed · 8 W / 14 L · 36% won', realized_text: 'realized -$825.38',
    open_text: 'nothing open', dates_text: '2026-09-05 → 2026-10-24', note_text: null, tone: 'down',
  },
];

const FIXTURE: LanePnl = {
  title: '💵 Which lane made money',
  as_of: '2026-10-27T21:24:00Z',
  since: '2026-07-13',
  verdict_text: '1 of 3 lanes net positive on paper since 2026-07-13: 🎛️ Options +$117.25 (18 closed, 3 held) · biggest loser 🚀 breakout (S/D supply band) -$825.38 (22 closed).',
  honesty_text: "Paper account, gross of fees. Realized $ = each lane's own book; engine sells are booked at the broker's fill. Open $ = the broker's unrealized P&L on what it holds now. UNMEASURED — a tally of what happened, not a study; small n.",
  account: { starting: 98203.6, equity: 87183.56, total_pnl: -11020.04, unrealized_pnl: 851, realized_pnl: -11871.04 },
  account_text: 'Account since 2026-07-13: -$11,020.04 (-$11,871.04 closed · +$851.00 open)',
  lanes_total: { realized_pnl: -2040.96, unrealized_pnl: 1100.25, total_pnl: -940.71 },
  unexplained: { realized_pnl: -9830.08, unrealized_pnl: -249.25 },
  unexplained_text: "Not attributed to a lane: -$9,830.08 closed · -$249.25 open — the account's P&L minus every lane's book.",
  rows: ROWS,
  untraded: ['catalyst', 'hot_pullback'],
  untraded_text: 'No trades yet: 🗞️ catalyst · 🔥 hot pullback',
  positions_text: null,
};

const clone = (): LanePnl => JSON.parse(JSON.stringify(FIXTURE));
const draw = (data: LanePnl | null | undefined) => render(<MemoryRouter><LanePnlBlock data={data} /></MemoryRouter>);

/** Every string the server sent that the block is allowed to print. */
function served(d: LanePnl): string[] {
  const out: Array<string | null | undefined> = [
    d.title, d.verdict_text, d.untraded_text, d.positions_text, d.account_text, d.unexplained_text, d.honesty_text,
  ];
  for (const r of d.rows || []) {
    out.push(r.label, r.total_text, r.record_text, r.realized_text, r.open_text, r.dates_text, r.note_text);
    if (r.url) out.push(r.link_text);
  }
  return out.filter((s): s is string => typeof s === 'string' && s.length > 0);
}

describe('LanePnlBlock — served rows', () => {
  it('renders title, verdict, one row per served row in SERVED order, every *_text verbatim, the lane link', () => {
    draw(FIXTURE);
    const block = screen.getByTestId('lane-pnl');
    expect(within(block).getByText(FIXTURE.title!)).toBeInTheDocument();
    expect(screen.getByTestId('lane-pnl-verdict')).toHaveTextContent(FIXTURE.verdict_text!);
    const rows = screen.getAllByTestId('lane-pnl-row');
    expect(rows.map((r) => r.getAttribute('data-lane'))).toEqual(['options_zone', 'gajjala', 'breakout']);
    ROWS.forEach((r, i) => {
      const el = rows[i];
      for (const t of [r.label, r.total_text, r.record_text, r.realized_text, r.open_text, r.dates_text, r.link_text]) {
        expect(within(el).getByText(t!)).toBeInTheDocument();
      }
    });
    expect(within(rows[1]).getByText(ROWS[1].note_text!)).toBeInTheDocument();
    const gg = within(rows[1]).getByRole('link', { name: '→ 🚩 Gajjala tab' });
    expect(gg.getAttribute('href')).toBe('/trading?view=gajjala');
    for (const t of [FIXTURE.untraded_text, FIXTURE.account_text, FIXTURE.unexplained_text, FIXTURE.honesty_text]) {
      expect(within(block).getByText(t!)).toBeInTheDocument();
    }
  });

  it('colors the total only from the served tone: up → green, down → red', () => {
    draw(FIXTURE);
    const totals = screen.getAllByTestId('lane-pnl-row').map((r) => r.querySelector('.lane-pnl__total') as HTMLElement);
    expect(totals[0].getAttribute('style') || '').toMatch(/rgb\(16, 185, 129\)|#10b981/i);
    expect(totals[1].getAttribute('style') || '').toMatch(/rgb\(239, 68, 68\)|#ef4444/i);
    // NEGATIVE: the up row is never red, the down row never green.
    expect(totals[0].getAttribute('style') || '').not.toMatch(/rgb\(239, 68, 68\)|#ef4444/i);
    expect(totals[1].getAttribute('style') || '').not.toMatch(/rgb\(16, 185, 129\)|#10b981/i);
  });
});

describe('LanePnlBlock — negatives', () => {
  it('NEGATIVE: null / undefined render nothing; an error payload renders only its served text', () => {
    const a = draw(null);
    expect(a.container.textContent).toBe('');
    expect(screen.queryByTestId('lane-pnl')).toBeNull();
    a.unmount();
    const b = draw(undefined);
    expect(b.container.textContent).toBe('');
    b.unmount();
    const c = draw({ error: 'P&L by lane unavailable (KeyError)' });
    const block = screen.getByTestId('lane-pnl');
    expect(block.textContent).toBe('P&L by lane unavailable (KeyError)');
    expect(screen.queryAllByTestId('lane-pnl-row')).toHaveLength(0);
    expect(screen.queryByTestId('lane-pnl-verdict')).toBeNull();
    c.unmount();
  });

  it('NEGATIVE: a row with note_text null has no note; a row with url null has no link', () => {
    const d = clone();
    d.rows![1].url = null;
    draw(d);
    const rows = screen.getAllByTestId('lane-pnl-row');
    expect(rows[0].querySelector('.lane-pnl__note')).toBeNull();
    expect(rows[2].querySelector('.lane-pnl__note')).toBeNull();
    expect(rows[1].querySelector('.lane-pnl__note')).not.toBeNull();
    expect(rows[1].querySelector('a')).toBeNull();
    expect(within(rows[1]).queryByText('→ 🚩 Gajjala tab')).toBeNull();
    expect(rows[0].querySelector('a')).not.toBeNull();
  });

  it('NEGATIVE: prints nothing the server did not send — a mutated string shows, and no extra letters remain', () => {
    const d = clone();
    d.rows![0].record_text = 'ZZZ';
    const { container } = draw(d);
    expect(within(screen.getAllByTestId('lane-pnl-row')[0]).getByText('ZZZ')).toBeInTheDocument();
    expect(container.textContent).not.toContain(FIXTURE.rows![0].record_text!);
    let rest = container.textContent || '';
    for (const s of served(d).sort((x, y) => y.length - x.length)) rest = rest.split(s).join('');
    expect(rest.trim()).toBe('');
    // The control: the same stripping over the unmutated fixture's strings leaves "ZZZ" behind.
    let rest2 = container.textContent || '';
    for (const s of served(FIXTURE).sort((x, y) => y.length - x.length)) rest2 = rest2.split(s).join('');
    expect(rest2.trim()).toBe('ZZZ');
  });
});

describe('LanePnlBlock — 📱 430 px phone', () => {
  it('no inline px width over 430, no <table>, every flex container wraps with min-width 0', () => {
    const d = clone();
    d.positions_text = 'Broker positions not read — open $ not shown.';
    const { container } = render(
      <MemoryRouter><div style={{ width: '430px' }}><LanePnlBlock data={d} /></div></MemoryRouter>,
    );
    const block = screen.getByTestId('lane-pnl');
    expect(container.querySelector('table')).toBeNull();
    const all = [block, ...Array.from(block.querySelectorAll<HTMLElement>('*'))];
    let flexCount = 0;
    for (const el of all) {
      const w = el.style.width;
      if (w) {
        const px = /^([\d.]+)px$/.exec(w);
        if (px) expect(Number(px[1])).toBeLessThanOrEqual(430);
      }
      expect(el.style.overflowX).toBe('');
      if (el.style.display === 'flex') {
        flexCount += 1;
        expect(el.style.flexWrap).toBe('wrap');
        expect(el.style.minWidth).toMatch(/^0(px)?$/);
      }
    }
    expect(flexCount).toBe(6); // a head + a chip strip per served row
    expect(block.style.minWidth).toMatch(/^0(px)?$/);
    expect(block.style.maxWidth).toBe('100%');
  });
});
