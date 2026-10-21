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

/* The learning + volleyball pages left the catalog 2026-09-20 — Ajay: "Remove
   volleyball and learning of stocks I do dont wanna see them they are spamming
   too much" — and later the same day "Delete Flashcards please" took /learn and
   /chart-school (the flash-card bank and its chart quiz) out of the tree. The
   palette is built from the SERVER menu, so the entries vanish with the
   catalog; what had to go from this file is the synonym rows that would
   otherwise have kept pointing at them. */
describe('retired 2026-09-20 · learning + volleyball + flash cards', () => {
  it('has no synonym row for learn, learning or chart-school', () => {
    expect(NAV_SYNONYMS.learn).toBeUndefined();
    expect(NAV_SYNONYMS.learning).toBeUndefined();
    // chart-school went with the flashcards DELETE — its only data source was
    // GET /flashcards/chart-quiz
    expect(NAV_SYNONYMS['chart-school']).toBeUndefined();
  });

  it('NEGATIVE: searching "volleyball" or "learning" returns no page', () => {
    const index = buildIndex(MENU, (f) => SUBGROUP[f ?? '']);
    expect(searchNav(index, 'volleyball')).toEqual([]);
    expect(searchNav(index, 'learning')).toEqual([]);
    expect(searchNav(index, 'chart school')).toEqual([]);
    // control: the palette still finds a page that IS in the menu
    expect(searchNav(index, 'notification').length).toBeGreaterThan(0);
  });

  it('NEGATIVE: a stale menu row for a retired page brings no synonyms with it', () => {
    const stale = { ...MENU, profile: [...MENU.profile!, { to: '/learn', label: 'Learning', feature: 'learn' }] };
    const index = buildIndex(stale as any, (f) => SUBGROUP[f ?? '']);
    const row = index.find((e) => e.to === '/learn')!;
    expect(row.keywords).not.toContain('lessons');
  });

  it('NEGATIVE: a stale chart-school menu row brings no synonyms either', () => {
    const stale = { ...MENU, profile: [...MENU.profile!, { to: '/chart-school', label: 'Chart School', feature: 'chart-school' }] };
    const index = buildIndex(stale as any, (f) => SUBGROUP[f ?? '']);
    const row = index.find((e) => e.to === '/chart-school')!;
    expect(row.keywords).not.toContain('lessons');
    expect(row.keywords).not.toContain('charts');
  });
});


describe('🔑 Key Levels tab deep link (2026-09-28)', () => {
  it('"key level" finds /chart-maps?tab=key_levels', () => {
    expect(tos(searchNav(index, 'key level'))).toContain('/chart-maps?tab=key_levels');
    expect(tos(searchNav(index, 'prior week low'))).toContain('/chart-maps?tab=key_levels');
    expect(tos(searchNav(index, 'pwl'))).toContain('/chart-maps?tab=key_levels');
  });

  it('NEGATIVE: exactly one entry, and none without Chart Maps in the menu', () => {
    expect(EXTRA_ENTRIES.filter((e) => e.to === '/chart-maps?tab=key_levels')).toHaveLength(1);
    expect(index.filter((e) => e.to === '/chart-maps?tab=key_levels')).toHaveLength(1);
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(tos(without)).not.toContain('/chart-maps?tab=key_levels');
  });

  it('NEGATIVE: an unrelated query does not surface it', () => {
    expect(tos(searchNav(index, 'whatsapp'))).not.toContain('/chart-maps?tab=key_levels');
  });
});

describe('🧬 Medical catalysts deep link (2026-09-29)', () => {
  const MED = '/chart-maps?tab=catalysts&sub=medical';
  it('"fda", "phase 3", "clinical hold", "mrna" find the 🧬 Medical sub-tab', () => {
    for (const q of ['fda', 'fda approval', 'phase 3', 'clinical hold', 'mrna', 'medical', 'pdufa']) {
      expect(tos(searchNav(index, q)), q).toContain(MED);
    }
    expect(NAV_SYNONYMS.catalysts).toEqual(expect.arrayContaining(['medical', 'fda', 'biotech']));
  });
  it('exactly one entry, only when Chart Maps is in the menu', () => {
    expect(EXTRA_ENTRIES.filter((e) => e.to === MED)).toHaveLength(1);
    expect(index.filter((e) => e.to === MED)).toHaveLength(1);
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(tos(without)).not.toContain(MED);
  });
  it('NEGATIVE: an unrelated query does not surface it', () => {
    expect(tos(searchNav(index, 'whatsapp'))).not.toContain(MED);
    expect(tos(searchNav(index, 'key level'))).not.toContain(MED);
  });
});

describe('🏎️ Dual Momentum tab deep link (2026-09-29)', () => {
  const DM = '/chart-maps?tab=dual_momentum';
  it('"dual momentum" and "antonacci" find the tab', () => {
    for (const q of ['dual momentum', 'antonacci', 'momentum leaders', 'absolute momentum']) {
      expect(tos(searchNav(index, q)), q).toContain(DM);
    }
  });

  it('NEGATIVE: exactly one entry, and none without Chart Maps in the menu', () => {
    expect(EXTRA_ENTRIES.filter((e) => e.to === DM)).toHaveLength(1);
    expect(index.filter((e) => e.to === DM)).toHaveLength(1);
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(tos(without)).not.toContain(DM);
  });

  it('NEGATIVE: an unrelated query does not surface it', () => {
    expect(tos(searchNav(index, 'whatsapp'))).not.toContain(DM);
    expect(tos(searchNav(index, 'key level'))).not.toContain(DM);
  });
});

describe('🏔️ ATH tab deep link (2026-09-29)', () => {
  const ATH = '/chart-maps?tab=ath';
  it('"all time high" and "ath" find the tab', () => {
    for (const q of ['all time high', 'ath', 'all-time high', 'slipping']) {
      expect(tos(searchNav(index, q)), q).toContain(ATH);
    }
  });

  it('NEGATIVE: exactly one entry, and none without Chart Maps in the menu', () => {
    expect(EXTRA_ENTRIES.filter((e) => e.to === ATH)).toHaveLength(1);
    expect(index.filter((e) => e.to === ATH)).toHaveLength(1);
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(tos(without)).not.toContain(ATH);
  });

  it('NEGATIVE: an unrelated query does not surface it', () => {
    expect(tos(searchNav(index, 'whatsapp'))).not.toContain(ATH);
    expect(tos(searchNav(index, 'dual momentum'))).not.toContain(ATH);
  });
});

/* 🚩 Gajjala's in the palette (2026-10-21). Ajay: "Also I need this tab and its
   subtabs sercheable in global search". The rows are GENERATED from
   lib/gajjala.GG_SUBS, so the tests read the same list — a sub added to the
   strip must land here with no edit to navSearch.ts. */
import { GAJJALA_ENTRIES, GG_TAB_TO, GG_LANE_TO } from './navSearch';
import { GG_SUBS, GG_SUB_PARAM, parseGgSub } from './gajjala';

describe("🚩 Gajjala's tab + every sub in ⌘K (2026-10-21)", () => {
  const subTo = (key: string) => `${GG_TAB_TO}&${GG_SUB_PARAM}=${key}`;
  const ggRows = (rows: NavEntry[]) => rows.filter((e) => e.to === GG_TAB_TO || e.to.startsWith(`${GG_TAB_TO}&`));

  it('one tab row + one row per GG_SUBS sub, each carrying the sub label and emoji, all under chart-maps', () => {
    expect(GG_SUBS.length).toBeGreaterThanOrEqual(10);
    const tab = GAJJALA_ENTRIES.find((e) => e.to === GG_TAB_TO)!;
    expect(tab).toMatchObject({ parent: 'chart-maps', label: "Chart Maps ▸ 🚩 Gajjala's" });
    for (const s of GG_SUBS) {
      const rows = GAJJALA_ENTRIES.filter((e) => e.to === subTo(s.key));
      expect(rows, s.key).toHaveLength(1);
      expect(rows[0].parent).toBe('chart-maps');
      expect(rows[0].label).toBe(`Chart Maps ▸ 🚩 Gajjala's ▸ ${s.emoji} ${s.label}`);
      expect(rows[0].keywords).toContain('gajjala');
      // the URL the row opens resolves to that very sub on the board (lib/gajjala.parseGgSub)
      expect(parseGgSub(s.key)).toBe(s.key);
    }
    // the lane row is the only one outside chart-maps
    expect(GAJJALA_ENTRIES.filter((e) => e.parent !== 'chart-maps')).toEqual([expect.objectContaining({ parent: 'trading', to: GG_LANE_TO })]);
    expect(GAJJALA_ENTRIES).toHaveLength(GG_SUBS.length + 2);
  });

  it('the rows sit in the index right after the other Chart Maps deep links, once each', () => {
    for (const e of GAJJALA_ENTRIES) {
      if (e.parent !== 'chart-maps') continue;
      expect(index.filter((r) => r.to === e.to), e.to).toHaveLength(1);
      expect(index.find((r) => r.to === e.to)!.group).toBe('Primary');
    }
    expect(index.find((e) => e.to === GG_LANE_TO)).toMatchObject({ feature: 'trading', group: 'Tools ▸ Trade' });
  });

  it('"gajjala" ranks the tab first and lists every sub and the lane', () => {
    const r = searchNav(index, 'gajjala', 20);
    expect(r[0].to).toBe(GG_TAB_TO);
    expect(tos(r)).toEqual(expect.arrayContaining([...GG_SUBS.map((s) => subTo(s.key)), GG_LANE_TO]));
    // the default cap still leads with the tab
    expect(searchNav(index, 'gajjala')[0].to).toBe(GG_TAB_TO);
    expect(searchNav(index, "gajjala's")[0].to).toBe(GG_TAB_TO);
    expect(searchNav(index, 'GAJJALA ')[0].to).toBe(GG_TAB_TO);
  });

  it("his setup names land on their own sub — the sub above the tab", () => {
    const cases: Array<[string, string]> = [
      ['bull flag', 'bull_flag'], ['flag', 'bull_flag'],
      ['kiss', 'kiss_fly'], ['kiss and fly', 'kiss_fly'], ['ema kiss', 'kiss_fly'],
      ['horizontal fade', 'horizontal_fade'], ['fade', 'horizontal_fade'],
      ['intraday vcp', 'intraday_vcp'],
      ['reversal squeeze', 'reversal_squeeze'], ['squeeze', 'reversal_squeeze'], ['tennis ball', 'reversal_squeeze'],
      ['premarket', 'premarket'], ['pre-market', 'premarket'],
      ['post-market', 'postmarket'], ['after hours', 'postmarket'],
      ['playbook', 'playbook'], ['his rules', 'playbook'],
      ['potential', 'potential'], ['potentials', 'potential'],
      ['track record', 'track_record'], ['graded', 'track_record'],
    ];
    for (const [q, key] of cases) {
      const r = tos(searchNav(index, q, 20));
      expect(r, q).toContain(subTo(key));
      if (r.includes(GG_TAB_TO)) expect(r.indexOf(subTo(key)), `${q}: sub above tab`).toBeLessThan(r.indexOf(GG_TAB_TO));
    }
  });

  it('the tab answers to his name, GG and his universe words', () => {
    for (const q of ['goverdhan', 'gg', 'small caps', 'small cap', 'five minute', 'a plus', 'setups']) {
      expect(tos(searchNav(index, q, 20)), q).toContain(GG_TAB_TO);
    }
    expect(NAV_SYNONYMS['chart-maps']).toContain('gajjala');
  });

  it('the lane row opens the Trading page on its 🚩 view and answers to "lane"', () => {
    expect(GG_LANE_TO).toBe('/trading?view=gajjala');
    expect(tos(searchNav(index, 'gajjala lane'))[0]).toBe(GG_LANE_TO);
    expect(tos(searchNav(index, 'lane', 20))).toContain(GG_LANE_TO);
  });

  it('NEGATIVE: no Gajjala row without Chart Maps in the menu; the lane row stays (its parent is Trading)', () => {
    const without = buildIndex({ ...MENU, primary: MENU.primary.filter((m) => m.feature !== 'chart-maps') }, subgroupOf);
    expect(ggRows(without)).toEqual([]);
    expect(tos(searchNav(without, 'gajjala', 20))).toEqual([GG_LANE_TO]);
    expect(tos(searchNav(without, 'kiss'))).not.toContain(subTo('kiss_fly'));
  });

  it('NEGATIVE: no lane row without Trading in the menu (a Chart-Maps-only user); the tab rows stay', () => {
    const noTrading = buildIndex({ ...MENU, misc: MENU.misc.filter((m) => m.feature !== 'trading') }, subgroupOf);
    expect(tos(noTrading)).not.toContain(GG_LANE_TO);
    expect(ggRows(noTrading)).toHaveLength(GG_SUBS.length + 1);
    expect(searchNav(noTrading, 'gajjala')[0].to).toBe(GG_TAB_TO);
  });

  it('NEGATIVE: nothing Gajjala on an unrelated query, and "medical" / "key level" stay theirs', () => {
    for (const q of ['whatsapp', 'notification', 'fda', 'key level', 'dual momentum', 'volleyball']) {
      expect(ggRows(searchNav(index, q, 20)), q).toEqual([]);
      expect(tos(searchNav(index, q, 20)), q).not.toContain(GG_LANE_TO);
    }
  });

  it('NEGATIVE: no row types "bounce" — "reversal", never "bounce", on a surface he reads', () => {
    for (const e of GAJJALA_ENTRIES) {
      expect(normalize(e.label), e.to).not.toContain('bounce');
      expect(e.keywords.join(' '), e.to).not.toContain('bounce');
    }
  });

  it('NEGATIVE: no sub key is typed twice — every sub row is generated from GG_SUBS', () => {
    const typed = GAJJALA_ENTRIES.filter((e) => e.to.startsWith(`${GG_TAB_TO}&`)).map((e) => e.to);
    expect(new Set(typed).size).toBe(GG_SUBS.length);
    const keys = new Set(GG_SUBS.map((s) => s.key as string));
    for (const to of typed) expect(keys.has(to.split('=').pop()!), to).toBe(true);
  });

  it('NEGATIVE: an unknown sub in the URL would fall back to the default — so no row may carry one', () => {
    expect(parseGgSub('not_a_sub')).toBe(GG_SUBS[0].key);
    for (const e of GAJJALA_ENTRIES) {
      const m = /[?&]sub=([a-z_]+)/.exec(e.to);
      if (m) expect(parseGgSub(m[1]), e.to).toBe(m[1]);
    }
  });
});
