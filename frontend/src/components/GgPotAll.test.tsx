import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgPotAll, GgPotAllNotes, ggPotAllRows } from './GgPotAll';

/* 🧠 from every tab — the component (2026-11-24, potall spec §3.3, WP fe-potall). Every string is a SENTINEL in the shape
 * of pot_all.block; the component types no word, never sorts, guards every href with ggHref. */

const row = (sym: string, setup: string, over: Record<string, any> = {}) => ({
  symbol: sym, setup, tier: 'forming', text: `${sym} · served ${setup}`, href: null, ...over,
});
const blk = (over: Record<string, any> = {}): any => ({
  title: 'served title', order_text: 'served order', rule_text: 'served rule', as_of_text: 'served as of', live: false,
  rows: [row('ZZZ', 'kiss_fly'), row('AAA', 'intraday_vcp'), row('MMM', 'diverging')],
  n: 3, more_n: 0, more_text: null, faults_n: 0, fault_text: null, ...over,
});
const put = (el: ReactElement) => render(<MemoryRouter>{el}</MemoryRouter>);

afterEach(() => cleanup());

describe('GgPotAll', () => {
  it('rows print in SERVED order (never sorted), text verbatim', () => {
    put(<GgPotAll block={blk()} />);
    const items = within(screen.getByTestId('gg-potall')).getAllByRole('listitem');
    expect(items.map((i) => i.textContent)).toEqual(['ZZZ · served kiss_fly', 'AAA · served intraday_vcp', 'MMM · served diverging']);
  });

  it('a safe served href → a router link carrying the source; the row text is the link text', () => {
    put(<GgPotAll block={blk({ rows: [row('AAA', 'intraday_vcp', { href: '/chart-maps?tab=gajjala&sub=intraday_vcp&focus=AAA' })] })}
                  search="?tab=gajjala&sub=potential" />);
    const a = screen.getByTestId('gg-potall-link-AAA-intraday_vcp');
    expect(a.tagName).toBe('A');
    expect(a.textContent).toBe('AAA · served intraday_vcp');
    expect(a.getAttribute('href')).toContain('focus=AAA');
    expect(a.getAttribute('href')).toContain('from=chart-maps');
  });

  it('NEGATIVE: href null / "" / "//evil" / "https://x" / "javascript:" → plain text, no anchor', () => {
    const bad = [null, '', '//evil.example/x', 'https://x.example/', 'javascript:alert(1)', 42];
    const { container } = put(<GgPotAll block={blk({ rows: bad.map((h, i) => row(`S${i}`, 'kiss_fly', { href: h })) })} />);
    expect(container.querySelector('a')).toBeNull();
    bad.forEach((_, i) => expect(screen.getByTestId(`gg-potall-plain-S${i}-kiss_fly`).textContent).toBe(`S${i} · served kiss_fly`));
  });

  it('chips print the served words; absent / blank / non-string → no node', () => {
    put(<GgPotAll block={blk({ rows: [
      row('AAA', 'kiss_fly', { broke_text: 'served broke', alert_text: 'served alert', read_at_text: 'served read at',
        trader_text: 'served trader', promo_text: 'served promo', broker_text: 'served broker', state_label: 'served pill' }),
      row('BBB', 'kiss_fly', { broke_text: '  ', alert_text: null, read_at_text: 7, trader_text: '', broker_text: null }),
    ] })} />);
    expect(screen.getByTestId('gg-potall-broke-AAA-kiss_fly').textContent).toBe('served broke');
    expect(screen.getByTestId('gg-potall-alert-AAA-kiss_fly').textContent).toBe('served alert');
    expect(screen.getByTestId('gg-potall-readat-AAA-kiss_fly').textContent).toBe('served read at');
    expect(screen.getByTestId('gg-trader-potall-AAA-kiss_fly').textContent).toBe('served trader');
    expect(screen.getByTestId('gg-promo-potall-AAA-kiss_fly').textContent).toBe('served promo');
    expect(screen.getByTestId('gg-broker-potall-AAA-kiss_fly').textContent).toBe('served broker');
    expect(screen.getByTestId('gg-potall-row-AAA-kiss_fly').getAttribute('title')).toBe('served pill');
    for (const p of ['gg-potall-broke', 'gg-potall-alert', 'gg-potall-readat', 'gg-trader-potall', 'gg-promo-potall', 'gg-broker-potall']) {
      expect(screen.queryByTestId(`${p}-BBB-kiss_fly`), p).toBeNull();
    }
    expect(screen.getByTestId('gg-potall-row-BBB-kiss_fly').hasAttribute('title')).toBe(false);
  });

  it('NEGATIVE: the visible list never prints the title / order / rule / as-of words', () => {
    const { container } = put(<GgPotAll block={blk()} />);
    for (const w of ['served title', 'served order', 'served rule', 'served as of']) expect(container.textContent).not.toContain(w);
  });

  it('more / fault lines print; more only with rows; nothing when no row and no fault', () => {
    put(<GgPotAll block={blk({ more_text: 'served more', fault_text: 'served fault' })} />);
    expect(screen.getByTestId('gg-potall-more').textContent).toBe('served more');
    expect(screen.getByTestId('gg-potall-fault').textContent).toBe('served fault');
    cleanup();
    const a = put(<GgPotAll block={blk({ rows: [], more_text: 'served more' })} />);
    expect(a.container.innerHTML).toBe('');
    cleanup();
    put(<GgPotAll block={blk({ rows: [], fault_text: 'served fault' })} />);
    expect(screen.getByTestId('gg-potall-fault')).toBeTruthy();
    expect(screen.queryByTestId('gg-potall')).toBeNull();
    expect(screen.queryByTestId('gg-potall-more')).toBeNull();
  });

  it('NEGATIVE: null / undefined / non-object block / rows not an array → nothing', () => {
    for (const b of [null, undefined, 'x', blk({ rows: null }), blk({ rows: 'nope' })]) {
      const { container } = put(<GgPotAll block={b as any} />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: malformed rows (no symbol / setup / text) are skipped, the rest stand', () => {
    const rows = ggPotAllRows(blk({ rows: [null, { setup: 'x', text: 't' }, { symbol: 'A', text: 't' },
      { symbol: 'A', setup: 'x', text: '' }, row('OK', 'kiss_fly')] }));
    expect(rows.map((r) => r.symbol)).toEqual(['OK']);
  });
});

describe('GgPotAllNotes', () => {
  it('prints title / order / rule / as-of, each served', () => {
    put(<GgPotAllNotes block={blk()} />);
    expect(screen.getByTestId('gg-potall-title').textContent).toBe('served title');
    expect(screen.getByTestId('gg-potall-order').textContent).toBe('served order');
    expect(screen.getByTestId('gg-potall-rule').textContent).toBe('served rule');
    expect(screen.getByTestId('gg-potall-asof').textContent).toBe('served as of');
  });

  it('NEGATIVE: as_of_text null → no as-of node (never "None" / "null"); all null → nothing; never a row', () => {
    const a = put(<GgPotAllNotes block={blk({ as_of_text: null })} />);
    expect(screen.queryByTestId('gg-potall-asof')).toBeNull();
    expect(a.container.textContent).not.toMatch(/None|null|undefined/);
    expect(a.container.textContent).not.toContain('served kiss_fly');
    cleanup();
    const b = put(<GgPotAllNotes block={blk({ title: null, order_text: '', rule_text: null, as_of_text: null })} />);
    expect(b.container.innerHTML).toBe('');
    cleanup();
    const c = put(<GgPotAllNotes block={null} />);
    expect(c.container.innerHTML).toBe('');
  });
});
