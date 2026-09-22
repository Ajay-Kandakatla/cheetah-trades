import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { PromoOriginChip } from './PromoOriginChip';
import { promoOriginChip, fetchPromoOriginTags, _resetPromoOriginCache } from '../hooks/usePromoOriginTags';

/* 🎪 PromoOriginChip — Ajay 2026-09-21: "check if we can use them and ... add
 * them to our list as they come through".
 *
 * Four rules it must never break:
 *   1. it renders NOTHING for a name that did not enter through the lane;
 *   2. the sentence says the tag is promotion, never foresight — and never
 *      claims the lane is the ONLY reason the name is here (UBS-class names);
 *   3. it reads `measurement pending` until the study fills MEASURED;
 *   4. a catalysts outage is silent and costs ONE fetch per page, not one
 *      per tile.
 */

/* The real payload shape of GET /catalysts/promo-curate/tags. */
const PAYLOAD = {
  tags: {
    GRRR: { accounts: ['stockbossup', 'traderpanda'], tier: 'S', first_tagged_at: '2026-09-15T13:41:02+00:00', added_at: '2026-09-21T12:10:00+00:00' },
    NMAX: { accounts: ['pennystock_pete'], tier: 'B', first_tagged_at: '2026-09-18T14:02:11+00:00', added_at: '2026-09-21T12:10:00+00:00' },
  },
  measured: null as null | { verdict: string },
  note: 'the tag is promotion, never foresight',
};

function stub(ok = true, body: unknown = PAYLOAD) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok, json: async () => body,
  }) as unknown as Response));
}

describe('PromoOriginChip', () => {
  beforeEach(() => _resetPromoOriginCache());
  afterEach(() => vi.unstubAllGlobals());

  it('marks a name that entered through the promo lane, with account/tier/date in the title', async () => {
    stub();
    const { container } = render(<PromoOriginChip symbol="GRRR" />);
    await waitFor(() => expect(screen.getByText('🎪 promo')).toBeTruthy());
    const el = container.querySelector('span')!;
    const title = el.getAttribute('title')!;
    expect(title.startsWith('Entered the scan universe through the promo-circuit lane')).toBe(true);
    expect(title).toContain('@stockbossup +1 more');
    expect(title).toContain('(tier S)');
    expect(title).toContain('on 2026-09-15');
    expect(title).toContain('the tag is promotion, never foresight');
    expect(title).toContain('Not a pick.');
    expect(el.className).toContain('cm-badge-promo');
  });

  it('NEGATIVE: the title never says "ONLY because"', async () => {
    stub();
    const { container } = render(<PromoOriginChip symbol="GRRR" />);
    await waitFor(() => expect(screen.getByText('🎪 promo')).toBeTruthy());
    expect(container.querySelector('span')!.getAttribute('title')).not.toMatch(/ONLY because/i);
  });

  it('NEGATIVE: renders nothing for a name that did not come through the lane', async () => {
    stub();
    const { container } = render(<PromoOriginChip symbol="NVDA" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('NEGATIVE: a failing endpoint renders nothing and does not throw', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const { container } = render(<PromoOriginChip symbol="GRRR" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('NEGATIVE: a non-200 renders nothing rather than crashing the host board', async () => {
    stub(false, {});
    const { container } = render(<PromoOriginChip symbol="GRRR" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('reads "measurement pending" until the study fills MEASURED', async () => {
    stub();
    const { container } = render(<PromoOriginChip symbol="NMAX" />);
    await waitFor(() => expect(screen.getByText('🎪 promo')).toBeTruthy());
    expect(container.querySelector('span')!.getAttribute('title')).toContain('Measured: measurement pending.');
  });

  it('shows the measured verdict once it is set', async () => {
    stub(true, { ...PAYLOAD, measured: { verdict: 'no_signal — 24% win, median R −1.0' } });
    const { container } = render(<PromoOriginChip symbol="NMAX" />);
    await waitFor(() => expect(screen.getByText('🎪 promo')).toBeTruthy());
    const title = container.querySelector('span')!.getAttribute('title')!;
    expect(title).toContain('Measured: no_signal — 24% win, median R −1.0.');
    expect(title).not.toContain('measurement pending');
  });

  it('fetches ONCE for a whole grid of tiles, not once per tile', async () => {
    stub();
    const spy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    render(<><PromoOriginChip symbol="GRRR" /><PromoOriginChip symbol="NMAX" /><PromoOriginChip symbol="NVDA" /></>);
    await waitFor(() => expect(screen.getAllByText('🎪 promo').length).toBe(2));
    expect(spy.mock.calls.length).toBe(1);
  });

  it('caches the miss too — a dead endpoint is not retried per tile', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const spy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    await fetchPromoOriginTags();
    await fetchPromoOriginTags();
    await fetchPromoOriginTags();
    expect(spy.mock.calls.length).toBe(1);
  });

  it('promoOriginChip is case-insensitive, single-account, and null for an absent name', () => {
    const p = { tags: PAYLOAD.tags, measured: null };
    expect(promoOriginChip(p, 'nmax')?.text).toBe('🎪 promo');
    expect(promoOriginChip(p, 'nmax')?.title).toContain('@pennystock_pete (tier B)');
    expect(promoOriginChip(p, 'nmax')?.title).not.toContain('more');
    expect(promoOriginChip(p, 'NOPE')).toBeNull();
    expect(promoOriginChip({ tags: {}, measured: null }, 'GRRR')).toBeNull();
  });

  it('carries the board className through, so table variants keep their geometry', async () => {
    stub();
    const { container } = render(<PromoOriginChip symbol="GRRR" className="sb-chip" />);
    await waitFor(() => expect(screen.getByText('🎪 promo')).toBeTruthy());
    expect(container.querySelector('span')!.className).toBe('sb-chip sb-chip-promo');
  });
});

/* ── style guard (2026-09-21) ─────────────────────────────────────────────────
 * The chip renders `${className} ${className}-promo`, so EVERY board family it
 * is dropped into needs its own `-promo` rule. `hs-badge` (🔥 Hottest) shipped
 * without one: `.hs-badge` is layout only, so the chip rendered in the table's
 * inherited ink and read like a neutral label — invisible as a warning.
 *
 * The guard derives the families from the render sites themselves (`?raw`, the
 * same technique as EarningsFreshChip's source guards), so the next board that
 * passes a new className fails here until its colour exists.
 */
const TSX = (import.meta as any).glob('../**/*.tsx',
  { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;
const AMBER = 'color: #f59e0b; background: rgba(245,158,11,0.12);';

/* `../styles.css?raw` comes back EMPTY: vitest.config.ts sets `css: false`, so
 * the css plugin stubs the module and the ?raw query with it. Read the bytes —
 * same shape Notifications.price_alert.test.tsx uses (import.meta.url is not a
 * file URL under the transform, so resolve from cwd, which vitest sets to
 * frontend/). Read-only, so it is safe beside the parallel workers. */
async function css(): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/src/styles.css`, 'utf8');
}

function renderedFamilies(): string[] {
  const fams = new Set<string>(['cm-badge']); // the component's own default
  for (const [path, src] of Object.entries(TSX)) {
    if (path.includes('PromoOriginChip')) continue;
    for (const m of src.matchAll(/<PromoOriginChip\b[^>]*?className="([^"]+)"/g)) fams.add(m[1]);
  }
  return [...fams].sort();
}

describe('PromoOriginChip style guard', () => {
  it('every board family the chip is rendered with has an amber -promo colour', async () => {
    const CSS = await css();
    const fams = renderedFamilies();
    expect(fams).toEqual(['bd-gchip', 'cm-badge', 'hs-badge', 'sb-chip']);
    for (const fam of fams) {
      const rule = new RegExp(`\\.${fam}-promo\\b[^{]*\\{([^}]*)\\}`).exec(CSS);
      expect(rule, `.${fam}-promo is not defined in styles.css`).toBeTruthy();
      const body = rule![1].replace(/\s+/g, ' ').trim();
      expect(body, `.${fam}-promo must carry the amber tone`).toContain(AMBER);
    }
  });

  it('NEGATIVE: no -promo rule wears the growth cyan or the refusal red', async () => {
    const CSS = await css();
    for (const m of CSS.matchAll(/\.[a-z-]+-promo\b[^{]*\{([^}]*)\}/g)) {
      expect(m[1]).not.toContain('#22d3ee');
      expect(m[1]).not.toContain('#f85149');
    }
  });

  it('NEGATIVE: a family with no colour of its own is caught, not passed', async () => {
    const CSS = await css();
    // The exact shape of the bug this guard was written for: `.hs-badge` exists
    // (layout) while `.hs-badge-promo` does not. Matching the base must never
    // satisfy the check.
    const base = /\.hs-badge\b[^-][^{]*\{([^}]*)\}/.exec(CSS);
    expect(base).toBeTruthy();
    expect(base![1]).not.toContain('#f59e0b');
    expect(/\.hs-badge-promo\b/.test(CSS)).toBe(true);
  });
});
