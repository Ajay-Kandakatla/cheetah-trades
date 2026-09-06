import { describe, it, expect } from 'vitest';
import {
  NAV_SYNONYMS, EXTRA_ENTRIES, buildIndex, searchNav, normalize, isExternal, type NavEntry,
} from './navSearch';
import type { Menu } from '../hooks/useMyMenu';

/* navSearch — the ⌘K palette's index + ranking (Ajay 2026-09-06: "if I wanna
   search or related like notification I want them to show up from all the
   navigational menu"). Fixture mirrors the backend menu shape
   (backend/access/store.py build_menu) with the real catalog labels. */

const MENU: Pick<Menu, 'primary' | 'scanners' | 'misc' | 'profile' | 'admin'> = {
  primary: [
    { to: '/morning',    label: 'Morning Brief', feature: 'morning' },
    { to: '/overnight',  label: 'Overnight',     feature: 'overnight' },
    { to: '/portfolio',  label: 'Portfolio',     feature: 'portfolio' },
    { to: '/chart-maps', label: '🗺️ Chart Maps', feature: 'chart-maps' },
    { to: '/desk',       label: '🧠 Desk',       feature: 'desk' },
  ],
  scanners: [
    { to: '/sepa',        label: 'SEPA',             feature: 'sepa' },
    { to: '/pullback-ma', label: 'Pullback to MA',   feature: 'pullback-ma' },
  ],
  misc: [
    { to: '/trading',       label: '🤖 Auto-Pilot',   feature: 'trading' },
    { to: '/supply-demand', label: 'Supply / Demand', feature: 'supply-demand' },
    { to: '/demand-zones',  label: 'Demand Zones',    feature: 'demand-zones' },
    { to: '/live',          label: 'Live Stream',     feature: 'live' },
    { to: '/market-gauge',  label: 'Market Gauge',    feature: 'market-gauge' },
    { to: '/catalysts',     label: 'Catalysts',       feature: 'catalysts' },
    { to: '/research',      label: 'Research',        feature: 'research' },
    { to: '/alerts',        label: '🔔 Alerts',       feature: 'alerts' },
  ],
  profile: [
    { to: '/notifications', label: 'Notifications', feature: 'notifications' },
    { to: '/watchlist',     label: 'Watchlist',     feature: 'watchlist' },
  ],
  admin: [
    { to: '/admin/access', label: 'User Access' },
  ],
};

const SUBGROUP: Record<string, string> = {
  trading: 'Trade', 'supply-demand': 'Screeners', 'demand-zones': 'Zones', live: 'Tape',
  'market-gauge': 'Signals', catalysts: 'Signals', research: 'Signals', alerts: 'Signals',
};
const subgroupOf = (f?: string) => SUBGROUP[f ?? ''] ?? 'More';

const index = buildIndex(MENU, subgroupOf);
const tos = (rows: NavEntry[]) => rows.map((r) => r.to);

describe('NAV_SYNONYMS — the seed map', () => {
  it('bridges notifications ↔ alerts both ways', () => {
    expect(NAV_SYNONYMS.notifications).toContain('alerts');
    expect(NAV_SYNONYMS.alerts).toContain('notification');
  });

  it('carries the seeded ids, even ones a menu may not have', () => {
    for (const id of ['notifications', 'alerts', 'supply-demand', 'chart-maps', 'demand-zones', 'trading',
      'catalysts', 'sepa', 'market-gauge', 'portfolio', 'watchlist', 'research', 'live', 'morning', 'desk']) {
      expect(NAV_SYNONYMS[id]?.length, id).toBeGreaterThan(0);
    }
    expect(NAV_SYNONYMS['supply-demand']).toContain('in demand');
    expect(NAV_SYNONYMS['chart-maps']).toContain('deep demand');
  });
});

describe('buildIndex', () => {
  it('keeps menu order and names every group', () => {
    const groups = index.map((e) => e.group);
    expect(index[0]).toMatchObject({ to: '/morning', group: 'Primary' });
    expect(groups.indexOf('Primary')).toBeLessThan(groups.indexOf('Scanners'));
    expect(groups.indexOf('Scanners')).toBeLessThan(groups.indexOf('Tools ▸ Trade'));
    expect(groups.lastIndexOf('Tools ▸ Signals')).toBeLessThan(groups.indexOf('Profile'));
    expect(groups.indexOf('Profile')).toBeLessThan(groups.indexOf('Admin'));
    expect(index.find((e) => e.to === '/alerts')?.group).toBe('Tools ▸ Signals');
    expect(index.find((e) => e.to === '/admin/access')).toMatchObject({ group: 'Admin', feature: undefined });
  });

  it('falls back to a bare "Tools" group when no subgroup is known', () => {
    const idx = buildIndex(MENU);
    expect(idx.find((e) => e.to === '/alerts')?.group).toBe('Tools');
  });

  it('attaches synonyms as lower-cased keywords', () => {
    const alerts = index.find((e) => e.to === '/alerts')!;
    expect(alerts.keywords).toContain('notification');
    expect(alerts.keywords).toContain('why quiet');
    const notif = index.find((e) => e.to === '/notifications')!;
    expect(notif.keywords).toContain('alerts');
  });

  it('adds the Chart Maps tab deep links right after Chart Maps, only when Chart Maps is in the menu', () => {
    const at = index.findIndex((e) => e.to === '/chart-maps');
    expect(index[at + 1]).toMatchObject({ to: '/chart-maps?tab=zones', label: 'Chart Maps ▸ Demand zones', group: 'Primary' });
    expect(tos(index)).toEqual(expect.arrayContaining([
      '/chart-maps?tab=deep_demand', '/chart-maps?tab=catalysts', '/chart-maps?tab=ict', '/chart-maps?tab=overnight',
    ]));
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(tos(without).some((t) => t.startsWith('/chart-maps'))).toBe(false);
  });

  it('adds the SEPA supply tab only when SEPA is in the menu', () => {
    expect(tos(index)).toContain('/sepa?tab=supply');
    const without = buildIndex({ ...MENU, scanners: [] }, subgroupOf);
    expect(tos(without)).not.toContain('/sepa?tab=supply');
  });

  it('dedupes by `to` — a duplicate destination folds its words into the first entry', () => {
    expect(new Set(tos(index)).size).toBe(index.length);
    // The Notifications / Trading extras share their parent's `to`, so they
    // become keywords rather than a second row.
    expect(index.filter((e) => e.to === '/notifications')).toHaveLength(1);
    expect(index.find((e) => e.to === '/notifications')!.keywords).toContain('push settings');
    expect(index.find((e) => e.to === '/trading')!.keywords).toContain('journal');
    // A menu that repeats a destination across sections still yields one row.
    const dup = buildIndex({ ...MENU, profile: [...MENU.profile, { to: '/morning', label: 'Morning again', feature: 'morning' }] }, subgroupOf);
    expect(dup.filter((e) => e.to === '/morning')).toHaveLength(1);
  });

  it('every EXTRA_ENTRIES parent is a real feature id and every `to` is an in-app path', () => {
    for (const ex of EXTRA_ENTRIES) {
      expect(ex.parent).toMatch(/^[a-z-]+$/);
      expect(ex.to.startsWith('/')).toBe(true);
      expect(ex.label).toContain('▸');
    }
  });

  it('tolerates an empty / partial menu', () => {
    expect(buildIndex({ primary: [], scanners: [], misc: [], profile: [], admin: [] })).toEqual([]);
    expect(buildIndex({ primary: [{ to: '', label: 'broken' }], scanners: [], misc: [], profile: [], admin: [] })).toEqual([]);
  });
});

describe('searchNav — ranking', () => {
  it('"notification" returns Notifications first AND the Alerts page', () => {
    const r = searchNav(index, 'notification');
    expect(r[0].to).toBe('/notifications');
    expect(tos(r)).toContain('/alerts');
  });

  it('"alert" returns Alerts first and Notifications too', () => {
    const r = searchNav(index, 'alert');
    expect(r[0].to).toBe('/alerts');
    expect(tos(r)).toContain('/notifications');
  });

  it('"in demand" finds Supply / Demand and Chart Maps ▸ Demand zones', () => {
    const r = tos(searchNav(index, 'in demand'));
    expect(r).toContain('/supply-demand');
    expect(r).toContain('/chart-maps?tab=zones');
    expect(r.slice(0, 3)).toEqual(expect.arrayContaining(['/supply-demand', '/chart-maps?tab=zones']));
  });

  it('empty / blank / punctuation-only query returns menu order, capped at limit', () => {
    expect(tos(searchNav(index, ''))).toEqual(tos(index).slice(0, 8));
    expect(tos(searchNav(index, '   '))).toEqual(tos(index).slice(0, 8));
    expect(tos(searchNav(index, '/?!'))).toEqual(tos(index).slice(0, 8));
    expect(searchNav(index, '', 3)).toHaveLength(3);
    expect(searchNav(index, '', 0)).toEqual([]);
  });

  it('exact label beats prefix beats whole-word beats keyword', () => {
    const r = searchNav(index, 'demand zones');
    expect(r[0].to).toBe('/demand-zones');                       // exact
    expect(tos(r)).toContain('/chart-maps?tab=zones');           // whole-word ("Chart Maps ▸ Demand zones")
    const zones = searchNav(index, 'zones');
    expect(zones[0].to).toBe('/demand-zones');                   // label word beats the many 'zones' synonyms
    expect(tos(zones)).toContain('/supply-demand');
  });

  it('is case-insensitive, trims, and ignores punctuation / emoji', () => {
    expect(searchNav(index, '  NOTIFICATION ')[0].to).toBe('/notifications');
    expect(searchNav(index, 'auto-pilot')[0].to).toBe('/trading');
    expect(searchNav(index, 'auto pilot')[0].to).toBe('/trading');
    expect(searchNav(index, 'chart maps')[0].to).toBe('/chart-maps');   // label carries 🗺️
    expect(searchNav(index, 'supply/demand')[0].to).toBe('/supply-demand');
  });

  it('fuzzy subsequence "chrtmp" finds Chart Maps', () => {
    const r = searchNav(index, 'chrtmp');
    expect(r[0].to).toBe('/chart-maps');
  });

  it('synonyms reach pages whose label says nothing of the word', () => {
    expect(tos(searchNav(index, 'whatsapp'))).toEqual(['/notifications']);
    expect(tos(searchNav(index, 'autopilot'))).toContain('/trading');
    expect(tos(searchNav(index, 'holdings'))).toContain('/portfolio');
    expect(tos(searchNav(index, 'regime'))).toContain('/market-gauge');
    expect(tos(searchNav(index, '8-k'))).toContain('/catalysts');
    expect(tos(searchNav(index, 'why quiet'))).toContain('/alerts');
  });

  it('group words find the whole group', () => {
    const r = tos(searchNav(index, 'signals'));
    expect(r).toEqual(expect.arrayContaining(['/market-gauge', '/catalysts', '/research', '/alerts']));
  });

  it('respects the limit and returns nothing for gibberish', () => {
    expect(searchNav(index, 'e', 2)).toHaveLength(2);
    expect(searchNav(index, 'qqqqzzzz')).toEqual([]);
    expect(searchNav([], 'anything')).toEqual([]);
  });

  it('never mutates the index', () => {
    const before = JSON.stringify(index);
    searchNav(index, 'demand');
    searchNav(index, '');
    expect(JSON.stringify(index)).toBe(before);
  });
});

describe('helpers', () => {
  it('normalize lower-cases, strips punctuation + emoji, collapses spaces', () => {
    expect(normalize('  🔔  Alerts!  ')).toBe('alerts');
    expect(normalize('Supply / Demand')).toBe('supply demand');
    expect(normalize('')).toBe('');
  });

  it('isExternal only for absolute http(s) URLs', () => {
    expect(isExternal('https://example.com')).toBe(true);
    expect(isExternal('/sepa')).toBe(false);
    expect(isExternal('')).toBe(false);
  });
});
