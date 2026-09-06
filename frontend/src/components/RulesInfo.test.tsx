/* RulesInfo — the "ℹ️ Rules" pill + panel (Ajay 2026-09-06: every board
 * carries a short info section listing its rules).
 *
 * The panel renders ONLY what GET /supply-demand/rules sends: the three
 * labelled lists and the note, an empty list omitted, and NOTHING at all when
 * the section key is unknown or the fetch failed — a board never wears a
 * blank pill, and no rule text is ever authored on the client. One request
 * per app, shared by every pill. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RulesInfo } from './RulesInfo';
import { _resetRulesInfoCache, normalizeRules } from '../hooks/useRulesInfo';

const FIXTURE = {
  sections: {
    in_demand: {
      title: 'Back in Demand',
      emoji: '🟢',
      picks: ['pick line one', 'pick line two', 'pick line three'],
      stops: ['stop line one', 'target line two'],
      alerts: ['alert line one'],
      note: 'Owner settings, not advice.',
    },
    picks_only: {
      title: 'Quiet board',
      emoji: '',
      picks: ['the only pick rule'],
      stops: [],
      alerts: [],
      note: '',
    },
  },
};

function stubFetch(body: unknown = FIXTURE, ok = true) {
  const fn = vi.fn(async (_url?: string) => ({ ok, status: ok ? 200 : 503, json: async () => body }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

/** Let the stubbed fetch (microtasks) settle and the effect commit. */
async function settled(fn: ReturnType<typeof vi.fn>) {
  await waitFor(() => expect(fn).toHaveBeenCalled());
  await waitFor(() => Promise.resolve());
}

/* The shared test setup ships a localStorage with no methods (the component
 * tolerates that — every read/write is in try/catch); give the suite a real
 * in-memory Storage so the remembered open/closed can be tested. Pattern:
 * PromoCircuit.test.tsx. */
const mem = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: () => null,
    get length() { return m.size; },
  };
};

beforeEach(() => {
  _resetRulesInfoCache();
  vi.stubGlobal('localStorage', mem());
});
afterEach(() => vi.unstubAllGlobals());

describe('RulesInfo — renders what the endpoint sends', () => {
  it('shows the three labelled lists and the note once opened', async () => {
    stubFetch();
    render(<RulesInfo section="in_demand" />);
    const pill = await screen.findByTestId('rules-info-pill');
    expect(pill).toHaveTextContent('Rules');
    expect(screen.queryByTestId('rules-info-panel')).toBeNull();     // closed by default

    fireEvent.click(pill);
    expect(screen.getByText('🟢 Back in Demand')).toBeInTheDocument();
    expect(screen.getByText('Stock picks')).toBeInTheDocument();
    expect(screen.getByText('Stops & targets')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    for (const line of [...FIXTURE.sections.in_demand.picks, ...FIXTURE.sections.in_demand.stops, ...FIXTURE.sections.in_demand.alerts]) {
      expect(screen.getByText(line)).toBeInTheDocument();
    }
    expect(screen.getByTestId('rules-info-note')).toHaveTextContent('Owner settings, not advice.');
    // Every line is a list item, in the server's order.
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toEqual([...FIXTURE.sections.in_demand.picks, ...FIXTURE.sections.in_demand.stops, ...FIXTURE.sections.in_demand.alerts]);
  });

  it('toggles open and closed on the pill', async () => {
    stubFetch();
    render(<RulesInfo section="in_demand" />);
    const pill = await screen.findByTestId('rules-info-pill');
    expect(pill).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(pill);
    expect(screen.getByTestId('rules-info-panel')).toBeInTheDocument();
    expect(pill).toHaveAttribute('aria-expanded', 'true');
    expect(pill.className).toContain('is-active');

    fireEvent.click(pill);
    expect(screen.queryByTestId('rules-info-panel')).toBeNull();
    expect(pill).toHaveAttribute('aria-expanded', 'false');
    expect(pill.className).not.toContain('is-active');
  });

  it('omits an empty list and an empty note', async () => {
    stubFetch();
    render(<RulesInfo section="picks_only" />);
    fireEvent.click(await screen.findByTestId('rules-info-pill'));
    expect(screen.getByText('Stock picks')).toBeInTheDocument();
    expect(screen.getByText('the only pick rule')).toBeInTheDocument();
    expect(screen.queryByText('Stops & targets')).toBeNull();
    expect(screen.queryByText('Alerts')).toBeNull();
    expect(screen.queryByTestId('rules-info-note')).toBeNull();
    expect(screen.getByText('Quiet board')).toBeInTheDocument();      // no emoji → title alone
  });

  it('remembers open / closed per section across a remount', async () => {
    stubFetch();
    const first = render(<RulesInfo section="in_demand" />);
    fireEvent.click(await screen.findByTestId('rules-info-pill'));
    expect(localStorage.getItem('rulesInfo:open:in_demand')).toBe('1');
    first.unmount();

    render(<RulesInfo section="in_demand" />);
    await screen.findByTestId('rules-info-pill');
    expect(screen.getByTestId('rules-info-panel')).toBeInTheDocument();  // reopened from storage
    // A different section does not inherit it.
    expect(localStorage.getItem('rulesInfo:open:picks_only')).toBeNull();
  });

  it('compact renders the same panel as a floating popover under the pill', async () => {
    stubFetch();
    render(<RulesInfo section="in_demand" compact />);
    fireEvent.click(await screen.findByTestId('rules-info-pill'));
    const panel = screen.getByTestId('rules-info-panel');
    expect(panel.style.position).toBe('absolute');
    expect(screen.getByText('Stock picks')).toBeInTheDocument();
  });

  it('fetches the endpoint ONCE for every pill on the page', async () => {
    const fn = stubFetch();
    render(<><RulesInfo section="in_demand" /><RulesInfo section="picks_only" /></>);
    expect(await screen.findAllByTestId('rules-info-pill')).toHaveLength(2);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(String(fn.mock.calls[0]?.[0])).toContain('/supply-demand/rules');
  });

  it('still toggles when storage is blocked (private mode) — never a crash', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    stubFetch();
    render(<RulesInfo section="in_demand" />);
    const pill = await screen.findByTestId('rules-info-pill');
    fireEvent.click(pill);
    expect(screen.getByTestId('rules-info-panel')).toBeInTheDocument();
    fireEvent.click(pill);
    expect(screen.queryByTestId('rules-info-panel')).toBeNull();
  });
});

describe('RulesInfo — negatives: never a blank pill', () => {
  it('renders nothing when the section key is missing from the payload', async () => {
    const fn = stubFetch();
    const { container } = render(<RulesInfo section="no_such_board" />);
    await settled(fn);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the fetch rejects', async () => {
    const fn = vi.fn(async () => { throw new Error('network down'); });
    vi.stubGlobal('fetch', fn);
    const { container } = render(<RulesInfo section="in_demand" />);
    await settled(fn);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing on a non-2xx answer', async () => {
    const fn = stubFetch({ detail: 'nope' }, false);
    const { container } = render(<RulesInfo section="in_demand" />);
    await settled(fn);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when some other body answers the URL (no `sections`)', async () => {
    const fn = stubFetch({ rows: [], n: 0 });
    const { container } = render(<RulesInfo section="in_demand" />);
    await settled(fn);
    expect(container).toBeEmptyDOMElement();
  });

  it('a failed read is not cached: the next mount asks again', async () => {
    const bad = vi.fn(async () => { throw new Error('boom'); });
    vi.stubGlobal('fetch', bad);
    const first = render(<RulesInfo section="in_demand" />);
    await settled(bad);
    first.unmount();

    const good = stubFetch();
    render(<RulesInfo section="in_demand" />);
    expect(await screen.findByTestId('rules-info-pill')).toBeInTheDocument();
    expect(good).toHaveBeenCalledTimes(1);
  });
});

describe('normalizeRules — shapes the server JSON defensively', () => {
  it('drops non-string lines and fills missing fields', () => {
    const n = normalizeRules({ sections: { x: { title: 'X', picks: ['a', 3, '', null, 'b'] } } });
    expect(n?.sections.x).toEqual({ title: 'X', emoji: '', picks: ['a', 'b'], stops: [], alerts: [], note: '' });
  });

  it('returns null without a sections object', () => {
    expect(normalizeRules(null)).toBeNull();
    expect(normalizeRules({})).toBeNull();
    expect(normalizeRules({ sections: [] })).toBeNull();
    expect(normalizeRules({ sections: 'nope' })).toBeNull();
  });
});
