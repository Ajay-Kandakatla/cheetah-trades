/**
 * Ajay 2026-09-16: "I see two rules also with icons ... can you collapse all of
 * these please?" — three measured-study banners, four paragraphs each, stacked
 * above the charts.
 *
 * THE INVARIANT THESE TESTS PROTECT: the VERDICT never folds. The banners are
 * the reason a `no_signal` ordering is not read as a prediction; folding the
 * headline would defeat them. Only the justification folds.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StudyNote } from './StudyNote';

const HEAD = 'MEASURED 2026-09-16: NO SIGNAL SEPARATES (no lift larger than 2.80pp)';
const BODY = 'Measured on 24,994 episodes in 2025-03-10 → 2026-08-17, 3,716 names, broad.';
const LIMITS = 'Bands are BOARD geometry on CLOSED bars.';

function view(over: Record<string, unknown> = {}) {
  return render(
    <StudyNote id="t" headline={HEAD} body={BODY} limits={LIMITS}
               testId="study" {...over} />,
  );
}

describe('StudyNote — the verdict stays, the justification folds', () => {
  // The shared test setup replaces localStorage with a partial stub (see
  // PromoCircuit.test.tsx) — give this suite a real in-memory Storage so the
  // remembered fold can be tested at all. The component itself must survive
  // BOTH: a working store and one that throws (last case below).
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
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('shows the headline and hides the body by default', () => {
    view();
    expect(screen.getByText(HEAD)).toBeInTheDocument();
    const el = screen.getByTestId('study') as HTMLDetailsElement;
    expect(el.open).toBe(false);
  });

  it('opening it reveals every served paragraph', () => {
    view({ fallbackNote: 'ordered by ceiling thickness instead', extra: 'scope line',
           extraTestId: 'scope' });
    const el = screen.getByTestId('study') as HTMLDetailsElement;
    el.open = true;
    fireEvent(el, new Event('toggle'));
    expect(screen.getByText(BODY)).toBeInTheDocument();
    expect(screen.getByText('ordered by ceiling thickness instead')).toBeInTheDocument();
    expect(screen.getByText(LIMITS)).toBeInTheDocument();
    expect(screen.getByTestId('scope')).toHaveTextContent('scope line');
  });

  it('NEGATIVE: the headline is NEVER inside the folded part', () => {
    view();
    const el = screen.getByTestId('study') as HTMLDetailsElement;
    const summary = el.querySelector('summary');
    expect(summary).not.toBeNull();
    expect(summary!.textContent).toContain(HEAD);
  });

  it('remembers that he opened it, and that he closed it again', () => {
    const { unmount } = view();
    const el = screen.getByTestId('study') as HTMLDetailsElement;
    el.open = true;
    fireEvent(el, new Event('toggle'));
    unmount();

    view();
    const again = screen.getByTestId('study') as HTMLDetailsElement;
    expect(again.open).toBe(true);
    again.open = false;
    fireEvent(again, new Event('toggle'));
    expect(localStorage.getItem('cm.study.open.t')).toBe('0');
  });

  it('NEGATIVE: a study with nothing to fold renders a plain note, not an empty drawer', () => {
    render(<StudyNote id="bare" headline={HEAD} testId="bare" />);
    const el = screen.getByTestId('bare');
    expect(el.tagName.toLowerCase()).not.toBe('details');
    expect(el).toHaveTextContent(HEAD);
  });

  it('NEGATIVE: storage that throws must not take the board down', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
      removeItem: () => {}, clear: () => {}, key: () => null, length: 0,
    });
    expect(() => view()).not.toThrow();
    expect(screen.getByText(HEAD)).toBeInTheDocument();
    const el = screen.getByTestId('study') as HTMLDetailsElement;
    el.open = true;
    expect(() => fireEvent(el, new Event('toggle'))).not.toThrow();
  });

  it('NEGATIVE: an environment with NO localStorage at all still renders', () => {
    vi.stubGlobal('localStorage', undefined);
    expect(() => view()).not.toThrow();
    expect(screen.getByText(HEAD)).toBeInTheDocument();
  });

  it('keeps the study its own colour class so three folded rows stay distinct', () => {
    view({ className: 'cm-band-study' });
    const el = screen.getByTestId('study');
    expect(el.className).toContain('cm-band-study');
    expect(el.className).toContain('cm-note');
    expect(el.className).toContain('cm-study');
  });
});

/* #7 (2026-10-12, his "yes" to "Open the top line by default, or when a new
 * batch arrives?"): `freshKey` = the newest served stamp of what the note
 * folds. Open for a viewer who never folded it; re-open when the key is newer
 * than the one stored at his last fold; otherwise his fold is kept. */
describe('StudyNote — freshKey (open on a new batch)', () => {
  const mem = (init: Record<string, unknown> = {}) => {
    const m = new Map<string, unknown>(Object.entries(init));
    return {
      getItem: (k: string) => (m.has(k) ? m.get(k) : null),
      setItem: (k: string, v: string) => { m.set(k, String(v)); },
      removeItem: (k: string) => { m.delete(k); },
      clear: () => m.clear(),
      key: () => null,
      get length() { return m.size; },
      _m: m,
    };
  };
  const OLD = '2026-10-05T02:29:05+00:00';
  const NEW = '2026-10-12T02:29:05+00:00';
  const note = (fk: string | null | undefined, id = 'f') => (
    <StudyNote id={id} headline={HEAD} body={BODY} testId="study" freshKey={fk} />
  );
  const det = () => screen.getByTestId('study') as HTMLDetailsElement;
  const fold = () => { const el = det(); el.open = false; fireEvent(el, new Event('toggle')); };
  afterEach(() => { vi.unstubAllGlobals(); });

  it('no memory → OPEN on first paint', () => {
    vi.stubGlobal('localStorage', mem());
    render(note(NEW));
    expect(det().open).toBe(true);
  });

  it('folded with the SAME key → stays folded', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.f': '0', 'cm.study.fresh.f': NEW }));
    render(note(NEW));
    expect(det().open).toBe(false);
  });

  it('NEGATIVE: folded with a NEWER stored key than served (older batch) → stays folded', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.f': '0', 'cm.study.fresh.f': NEW }));
    render(note(OLD));
    expect(det().open).toBe(false);
  });

  it('folded with an OLDER key → re-opens; folding again stores the new key', () => {
    const store = mem({ 'cm.study.open.f': '0', 'cm.study.fresh.f': OLD });
    vi.stubGlobal('localStorage', store);
    const { unmount } = render(note(NEW));
    expect(det().open).toBe(true);
    fold();
    expect(store._m.get('cm.study.open.f')).toBe('0');
    expect(store._m.get('cm.study.fresh.f')).toBe(NEW);
    unmount();
    render(note(NEW));
    expect(det().open).toBe(false);
  });

  it('[C7] folded while mounted, then the PROP changes to a newer key → opens without a remount', () => {
    vi.stubGlobal('localStorage', mem());
    const { rerender } = render(note(OLD));
    expect(det().open).toBe(true);
    fold();
    expect(det().open).toBe(false);
    rerender(note(OLD));                 // a refetch of the same batch: no-op
    expect(det().open).toBe(false);
    rerender(note(NEW));
    expect(det().open).toBe(true);
  });

  it('a remembered OPEN stays open whatever the key', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.f': '1', 'cm.study.fresh.f': NEW }));
    render(note(OLD));
    expect(det().open).toBe(true);
  });

  it('NEGATIVE: a folder from before the stamp existed (no fresh key stored) re-opens once', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.f': '0' }));
    render(note(NEW));
    expect(det().open).toBe(true);
  });

  it('NEGATIVE: a non-string stored key is treated as absent → open', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.f': '0', 'cm.study.fresh.f': 12345 }));
    render(note(NEW));
    expect(det().open).toBe(true);
  });

  it('NEGATIVE: throwing storage with a freshKey → OPEN, folds without throwing', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
      removeItem: () => {}, clear: () => {}, key: () => null, length: 0,
    });
    expect(() => render(note(NEW))).not.toThrow();
    expect(det().open).toBe(true);
    expect(() => fold()).not.toThrow();
    expect(det().open).toBe(false);
  });

  it('NEGATIVE: NO storage at all with a freshKey → OPEN', () => {
    vi.stubGlobal('localStorage', undefined);
    render(note(NEW));
    expect(det().open).toBe(true);
  });

  it.each([[undefined], [null], ['']])(
    'NEGATIVE: freshKey %s → today\'s rule (folded, remembered fold honoured, no fresh key written)',
    (fk) => {
      const store = mem();
      vi.stubGlobal('localStorage', store);
      const { unmount } = render(note(fk as string | null | undefined));
      expect(det().open).toBe(false);
      const el = det();
      el.open = true;
      fireEvent(el, new Event('toggle'));
      expect(store._m.get('cm.study.open.f')).toBe('1');
      expect(store._m.has('cm.study.fresh.f')).toBe(false);
      unmount();
      render(note(fk as string | null | undefined));
      expect(det().open).toBe(true);
    },
  );

  it('NEGATIVE: ids keep separate memories (the strip vs the board line)', () => {
    vi.stubGlobal('localStorage', mem({ 'cm.study.open.a': '0', 'cm.study.fresh.a': NEW }));
    render(<>{note(NEW, 'a')}<StudyNote id="b" headline={HEAD} body={BODY} testId="study-b" freshKey={NEW} /></>);
    expect(det().open).toBe(false);
    expect((screen.getByTestId('study-b') as HTMLDetailsElement).open).toBe(true);
  });
});
