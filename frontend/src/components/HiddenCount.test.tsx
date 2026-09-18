import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HiddenCount, UNHIDDEN_TITLE, UNHIDE_OFF_TITLE, UNHIDE_ON_TITLE, unhideOffClause } from './HiddenCount';
import type { EnterableReasonStat } from '../lib/enterable';

/* 🎯 HiddenCount — the line that makes a default-ON filter safe.
 *
 * The locks are all about what must NEVER go quiet: the line renders even at
 * zero hidden, it names the reasons in the server's own words, the way back is
 * always one click, and rows without a read are reported separately instead of
 * being counted as rejections.
 */

describe('HiddenCount', () => {
  it('renders even when nothing is hidden — the filter is never silent', () => {
    render(<HiddenCount hidden={0} enabled hiddenByReason={{}} />);
    expect(screen.getByText(/0 hidden/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'show all' })).toBeInTheDocument();
  });

  it('names the top three reasons in the served words', () => {
    render(<HiddenCount
      hidden={34}
      enabled
      hiddenByReason={{ 'no band': 22, 'room < 5%': 8, 'floor swept': 3, 'not at band': 1 }}
    />);
    const line = screen.getByText(/34 hidden/).textContent || '';
    expect(line).toContain('22 no band');
    expect(line).toContain('8 room < 5%');
    expect(line).toContain('3 floor swept');
    expect(line).not.toContain('1 not at band');
  });

  it('reports rows without a read separately, never as hidden', () => {
    render(<HiddenCount hidden={0} unread={1800} enabled hiddenByReason={{}} />);
    expect(screen.getByText(/1,800 without a read \(shown last\)/)).toBeInTheDocument();
  });

  it('NEGATIVE: no unread suffix when every row has a read', () => {
    render(<HiddenCount hidden={2} unread={0} enabled hiddenByReason={{ 'no band': 2 }} />);
    expect(screen.queryByText(/without a read/)).toBeNull();
  });

  it('the way back is one click', () => {
    const onShowAll = vi.fn();
    render(<HiddenCount hidden={5} enabled hiddenByReason={{ 'no band': 5 }} onShowAll={onShowAll} />);
    fireEvent.click(screen.getByRole('button', { name: 'show all' }));
    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it('says "showing all" with the way back ON when the filter is off', () => {
    const onEnterableOnly = vi.fn();
    render(<HiddenCount hidden={0} enabled={false} onEnterableOnly={onEnterableOnly} />);
    expect(screen.getByText(/showing all/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'enterable only' }));
    expect(onEnterableOnly).toHaveBeenCalledTimes(1);
  });

  it('falls back to the one callback when a caller wired a single toggle', () => {
    const onShowAll = vi.fn();
    render(<HiddenCount hidden={0} enabled={false} onShowAll={onShowAll} />);
    fireEvent.click(screen.getByRole('button', { name: 'enterable only' }));
    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: an n/a tab says the filter is inert and offers no count', () => {
    render(<HiddenCount hidden={0} enabled kind="n/a" hiddenByReason={{ 'no band': 9 }} />);
    expect(screen.getByText('no demand read for this tab · filter off')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('carries a board note (the server-cut list) in the title', () => {
    render(<HiddenCount hidden={1} enabled hiddenByReason={{ 'no band': 1 }} note="server-cut list" />);
    expect(screen.getByTitle('server-cut list')).toBeInTheDocument();
  });
});

/* 🎯 UN-HIDE BY REASON (Ajay 2026-09-17: "Can you give me a toggle for the room
 * too? I am not seeing all stocks on the selected filter due to this now").
 *
 * The words this line already printed become buttons. The locks:
 *   - NO retyped reason string lives in this component — every chip's text is
 *     the SERVED label, handed in as a prop (the fixtures below build the
 *     expectation from that same value, never from a literal);
 *   - with no `reasons` prop the line is what it was yesterday, 3-capped;
 *   - a chip calls back with the CODE, never the label;
 *   - a stat holding nothing back and not un-hidden never reaches the line;
 *   - the filter-OFF line names the un-hidden count, because no chip can render
 *     there and one click on `enterable only` would otherwise resurrect a set
 *     he cannot see.
 */
const stat = (over: Partial<EnterableReasonStat> & { code: string }): EnterableReasonStat => ({
  label: `${over.code} label`, total: 0, baseline: 0, hidden: 0, ignored: false,
  toggleable: true, ...over,
});

const AMD = [
  stat({ code: 'room', label: 'room < 5%', total: 25, baseline: 19, hidden: 19 }),
  stat({ code: 'proximity', label: 'not at band', total: 9, baseline: 9, hidden: 9 }),
  stat({ code: 'no_band', label: 'no band', total: 8, baseline: 8, hidden: 8 }),
  stat({ code: 'floor_broken', label: 'floor broken', total: 2, baseline: 2, hidden: 2 }),
  stat({ code: 'floor_swept', label: 'floor swept', total: 2, baseline: 2, hidden: 2 }),
];

describe('HiddenCount — un-hide chips (2026-09-17)', () => {
  it('names every served reason as a button, in the order it was handed them', () => {
    render(<HiddenCount hidden={40} enabled reasons={AMD} onToggleReason={() => {}} />);
    const line = screen.getByText(/40 hidden/).textContent || '';
    for (const r of AMD) expect(line).toContain(`${r.hidden} ${r.label}`);
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('data-reason')))
      .toHaveLength(AMD.length);
  });

  it('a click hands back the CODE, never the label', () => {
    const onToggleReason = vi.fn();
    render(<HiddenCount hidden={40} enabled reasons={AMD} onToggleReason={onToggleReason} />);
    fireEvent.click(screen.getByText(`${AMD[0].hidden} ${AMD[0].label}`));
    expect(onToggleReason).toHaveBeenCalledWith('room');
    expect(onToggleReason).not.toHaveBeenCalledWith(AMD[0].label);
  });

  it('an un-hidden reason reads ✓ <served label> and the line says how many came back', () => {
    const reasons = AMD.map((r) => (r.code === 'room' ? { ...r, hidden: 0, ignored: true } : r));
    render(<HiddenCount hidden={21} unhidden={19} enabled reasons={reasons}
                        onToggleReason={() => {}} unhideCount={1} />);
    const line = screen.getByText(/21 hidden/).textContent || '';
    expect(line).toContain(`✓ ${AMD[0].label}`);
    expect(line).toContain('19 un-hidden');
    expect(screen.getByText(`✓ ${AMD[0].label}`)).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(`✓ ${AMD[0].label}`)).toHaveAttribute('title', UNHIDE_ON_TITLE);
  });

  it('every chip un-hidden reads 0 hidden with a ✓ on each', () => {
    const reasons = AMD.map((r) => ({ ...r, hidden: 0, ignored: true }));
    render(<HiddenCount hidden={0} unhidden={40} enabled reasons={reasons}
                        onToggleReason={() => {}} unhideCount={5} />);
    const line = screen.getByText(/0 hidden/).textContent || '';
    for (const r of AMD) expect(line).toContain(`✓ ${r.label}`);
    expect(line).toContain('40 un-hidden');
  });

  it('the OFF chip title says the verdict does not move', () => {
    render(<HiddenCount hidden={40} enabled reasons={AMD} onToggleReason={() => {}} />);
    expect(screen.getByText(`19 ${AMD[0].label}`)).toHaveAttribute('title', UNHIDE_OFF_TITLE);
  });

  it('appends the page’s own sentence to one chip, keyed by code', () => {
    render(<HiddenCount hidden={40} enabled reasons={AMD} onToggleReason={() => {}}
                        reasonTitle={{ room: 'the server floor runs first' }} />);
    expect(screen.getByText(`19 ${AMD[0].label}`).getAttribute('title'))
      .toContain('the server floor runs first');
    expect(screen.getByText(`9 ${AMD[1].label}`).getAttribute('title'))
      .not.toContain('the server floor runs first');
  });

  it('NEGATIVE: with no reasons prop the line is exactly today’s 3-capped text', () => {
    const byReason = { 'no band': 22, 'room < 5%': 8, 'floor swept': 3, 'not at band': 1 };
    const { container: a } = render(<HiddenCount hidden={34} enabled hiddenByReason={byReason} />);
    const { container: b } = render(
      <HiddenCount hidden={34} enabled hiddenByReason={byReason} reasons={[]} unhidden={0}
                   onToggleReason={() => {}} unhideCount={0} />);
    expect(b.textContent).toBe(a.textContent);
    expect(a.textContent).toContain('22 no band');
    expect(a.textContent).not.toContain('1 not at band');
  });

  it('NEGATIVE: no chips without an onToggleReason — a dead control is worse than none', () => {
    render(<HiddenCount hidden={40} enabled reasons={AMD} hiddenByReason={{ 'no band': 40 }} />);
    expect(screen.queryByText(`19 ${AMD[0].label}`)).toBeNull();
    expect(screen.getByText(/40 hidden/).textContent).toContain('40 no band');
  });

  it('NEGATIVE: no chips on an n/a tab, and none when the filter is off', () => {
    const { container } = render(
      <HiddenCount hidden={0} enabled kind="n/a" reasons={AMD} onToggleReason={() => {}} />);
    expect(container.querySelector('[data-reason]')).toBeNull();
    const { container: off } = render(
      <HiddenCount hidden={0} enabled={false} reasons={AMD} onToggleReason={() => {}} />);
    expect(off.querySelector('[data-reason]')).toBeNull();
  });

  it('NEGATIVE: a stat the backend gave no label is TEXT, never a button', () => {
    const reasons = [stat({ code: 'blocked', label: '', hidden: 3, baseline: 3, toggleable: false })];
    const { container } = render(
      <HiddenCount hidden={3} enabled reasons={reasons} onToggleReason={() => {}} />);
    expect(container.querySelector('[data-reason]')).toBeNull();
    expect(screen.getByText(/3 hidden/).textContent).toContain('3 blocked');
  });

  it('NEGATIVE: a stat holding nothing back and not un-hidden never reaches the line', () => {
    const reasons = [
      stat({ code: 'room', label: 'room < 5%', hidden: 4, baseline: 4 }),
      stat({ code: 'no_break', label: 'no lid break', hidden: 0, baseline: 0 }),
    ];
    render(<HiddenCount hidden={4} enabled reasons={reasons} onToggleReason={() => {}} />);
    expect(screen.getByText(/4 hidden/).textContent).not.toContain('no lid break');
  });

  it('the filter-OFF line NAMES the un-hidden count, so nothing is resurrected in silence', () => {
    render(<HiddenCount hidden={0} enabled={false} unhideCount={2} onEnterableOnly={() => {}} />);
    expect(screen.getByText(/showing all/).textContent).toContain(unhideOffClause(2));
    expect(screen.getByText(unhideOffClause(2))).toHaveAttribute('title', UNHIDDEN_TITLE);
  });

  it('singular at one reason', () => {
    render(<HiddenCount hidden={0} enabled={false} unhideCount={1} onEnterableOnly={() => {}} />);
    expect(screen.getByText(/showing all/).textContent).toContain('1 reason un-hidden');
    expect(screen.getByText(/showing all/).textContent).not.toContain('1 reasons');
  });

  it('NEGATIVE: unhideCount 0 or absent leaves the filter-OFF line byte-identical to today', () => {
    const { container: a } = render(<HiddenCount hidden={0} enabled={false} onEnterableOnly={() => {}} />);
    const { container: b } = render(
      <HiddenCount hidden={0} enabled={false} unhideCount={0} onEnterableOnly={() => {}} />);
    expect(b.textContent).toBe(a.textContent);
    expect(a.textContent).toBe('showing all · enterable only');
  });

  it('NEGATIVE: the unread suffix survives the chips', () => {
    render(<HiddenCount hidden={40} unread={1800} enabled reasons={AMD} onToggleReason={() => {}} />);
    expect(screen.getByText(/1,800 without a read \(shown last\)/)).toBeInTheDocument();
  });
});
