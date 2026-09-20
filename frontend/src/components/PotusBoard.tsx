/* 🏛️ PotusBoard — the POTUS / U.S.-government tab on Chart Maps (2026-09-20).
 *
 * Ajay 2026-09-20: "I would like it to be in individual tickers but also in to
 * the potus page in chart maps" and "Anytime POTUS does new investments show
 * me those".
 *
 * TWO SECTIONS, AND THEY ARE NOT THE SAME KIND OF THING.
 *
 *   1. THE LIST. The curated disclosures — `backend/political/disclosures.json`
 *      served through /political/board. A row is here because a filing or a
 *      named report put it here, and nothing automatic ever adds one.
 *      Grouped in a FIXED order (govt_investment → govt_contractor →
 *      potus_family → inferred) with the group's count in the header, one
 *      Support-tab tile per name off the SAME /chart-maps/support payload the
 *      Support tab draws, so the bands and the AMD / Keltner reads cannot
 *      differ between the two surfaces (the HoldingsBoard pattern).
 *
 *   2. THE WATCH CANDIDATES. A REGEX OVER HEADLINES. Not a signal, not a
 *      measurement, not a filing — a classifier that says "this headline looks
 *      like a federal stake story" and puts it in front of him. The heuristic
 *      sentence comes from the server (`watch.note`) and is printed verbatim,
 *      because a sentence written here could drift from the gate that actually
 *      decides what gets pushed.
 *
 * A candidate whose headline names NO ticker the app can resolve is still
 * shown, as "unnamed — needs a ticker" with no link. Dropping it would hide
 * exactly the stories his ask is about — the reporting that names a company in
 * prose and never prints a cashtag.
 *
 * NOTHING HERE IS SORTED BY RETURN. The groups are the curator's grouping and
 * the candidates are newest-first as served.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import OverlayLegend from './OverlayLegend';
import { TickerLink } from './TickerLink';
import { SepaPoliticalChip } from './SepaPoliticalChip';
import { GrowthChip } from './GrowthChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { SignalWatchButton } from './SignalWatchButton';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { filterTile, loadHidden, presentGroups, saveHidden, studiesWanted } from '../lib/chartOverlays';
import { supportQuery } from '../lib/supportLevels';
import type { CmTile } from '../lib/chartMaps';

/* The order is FIXED and it is an editorial order, not a ranking: a disclosed
 * federal equity stake is a harder fact than a contractor relationship, which
 * is harder than a family disclosure, which is harder than a row this app
 * merely inferred. Never re-sorted by anything on the tile. */
export const GROUP_ORDER = [
  'govt_investment', 'govt_contractor', 'potus_family', 'inferred',
] as const;

export const GROUP_LABEL: Record<string, string> = {
  govt_investment: '🇺🇸 U.S. government equity stake',
  govt_contractor: '🛠️ Government contractor / program participant',
  potus_family: '🏛️ POTUS family disclosed',
  inferred: '🔍 Inferred — not directly disclosed',
};

const RESOLUTION_LABEL: Record<string, string> = {
  tag: 'cashtag',
  name: 'company name',
  unnamed: 'unnamed',
};

export type PotusEntry = {
  ticker: string; company?: string | null; sector?: string | null;
  categories: string[]; disclosureBand?: string | null; govtStake?: string | null;
  notes?: string | null; asOf?: string | null; addedOn?: string | null;
  is_new?: boolean;
};

export type PotusCandidate = {
  ticker: string | null; resolution?: string | null; company?: string | null;
  headline?: { title?: string | null; url?: string | null; source?: string | null;
               published?: number | string | null } | null;
  pattern?: string | null; agency?: string | null; size?: string | null;
  first_seen?: string | null; pushed?: boolean; heuristic?: boolean;
};

export type PotusPayload = {
  as_of?: string | null;
  new_days?: number | null;
  entries?: PotusEntry[];
  groups?: Record<string, string[]>;
  candidates?: PotusCandidate[];
  watch?: {
    last_run?: string | null; queries?: string[]; window_hours?: number | null;
    heuristic?: boolean; note?: string | null;
  } | null;
};

type TileRead = { tile: CmTile | null; last?: number | null; error?: string | null };

function publishedEt(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  const ms = typeof v === 'number' ? (v > 1e12 ? v : v * 1000) : Date.parse(String(v));
  if (!Number.isFinite(ms)) return '—';
  try {
    return new Date(ms).toLocaleString('en-US', { timeZone: 'America/New_York' });
  } catch {
    return new Date(ms).toISOString();
  }
}

export default function PotusBoard() {
  const [payload, setPayload] = useState<PotusPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reads, setReads] = useState<Record<string, TileRead>>({});
  const [loading, setLoading] = useState(false);

  const [hiddenOverlays, setHiddenOverlays] = useState<Set<string>>(() => loadHidden());
  const hiddenRef = useRef(hiddenOverlays);
  hiddenRef.current = hiddenOverlays;
  const [studiesOn, setStudiesOn] = useState<boolean>(() => studiesWanted(hiddenRef.current));

  const toggleOverlay = (key: string) => {
    setHiddenOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      setStudiesOn(studiesWanted(next));
      return next;
    });
  };

  useEffect(() => {
    let alive = true;
    setErr(null);
    fetch(`${API}/political/board`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (alive) setPayload(d || {});
      })
      .catch((e) => { if (alive) { setPayload({}); setErr(String(e?.message ?? e)); } });
    return () => { alive = false; };
  }, []);

  const byTicker = useMemo(() => {
    const m = new Map<string, PotusEntry>();
    for (const e of payload?.entries || []) {
      if (e?.ticker) m.set(String(e.ticker).toUpperCase(), e);
    }
    return m;
  }, [payload]);

  /* Groups exactly as served, in the fixed order. A ticker with two categories
   * is in two groups — that is the truth about the row (INTC is both a family
   * disclosure and a federal stake) and the header counts say so. */
  const groups = useMemo(() => GROUP_ORDER.map((key) => {
    const tickers = (payload?.groups?.[key] || []).map((t) => String(t).toUpperCase());
    return { key, tickers, entries: tickers.map((t) => byTicker.get(t)).filter(Boolean) as PotusEntry[] };
  }), [payload, byTicker]);

  const symbols = useMemo(() => {
    const seen: string[] = [];
    for (const g of groups) for (const t of g.tickers) if (!seen.includes(t)) seen.push(t);
    return seen;
  }, [groups]);

  const seq = useRef(0);
  const load = useCallback(async () => {
    if (!symbols.length) { setReads({}); return; }
    const my = ++seq.current;
    setLoading(true);
    const out: Record<string, TileRead> = {};
    await Promise.all(symbols.map(async (sym) => {
      try {
        const r = await fetch(
          `${API}/chart-maps/support?${supportQuery({ symbol: sym, window: '' })}`
          + (studiesOn ? '&studies=true' : ''),
          { credentials: 'include', cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const p = await r.json();
        if (p?.error || !p?.tile) {
          out[sym] = { tile: null, error: String(p?.error || 'no chart') };
          return;
        }
        out[sym] = { tile: p.tile as CmTile, last: p.last_price ?? null };
      } catch (e: any) {
        out[sym] = { tile: null, error: String(e?.message ?? e) };
      }
    }));
    if (my !== seq.current) return;
    setReads(out);
    setLoading(false);
  }, [symbols, studiesOn]);

  useEffect(() => { void load(); }, [load]);

  /* One bounce-room POST for every name on screen — the 🚀 / 🧨 / 🎯 chips read
   * that one map rather than firing a request per tile. */
  const room = useBounceRoom(symbols);

  const present = useMemo(
    () => presentGroups(symbols.map((s) => reads[s]?.tile).filter(Boolean) as CmTile[]),
    [symbols, reads]);

  const candidates = payload?.candidates || [];
  const watch = payload?.watch || null;
  const watchDays = Math.max(1, Math.round((watch?.window_hours ?? 24) / 24));

  if (payload === null) return <div className="cm-foot mono">Loading the POTUS list…</div>;

  if (!symbols.length) {
    return (
      <div className="cm-foot mono">
        {err ? `Could not read the political list (${err}).`
             : 'The political disclosure list is empty.'}
      </div>
    );
  }

  return (
    <div className="pb">
      <div className="cm-controls">
        <span className="cm-foot mono">
          {byTicker.size} name{byTicker.size === 1 ? '' : 's'} on the disclosure list
          {payload?.as_of ? ` · as of ${payload.as_of}` : ''}
          {loading ? ' · loading charts…' : ''}
        </span>
      </div>

      <OverlayLegend present={present} hidden={hiddenOverlays} onToggle={toggleOverlay} />

      {groups.map((g) => (
        <section className="pb-group" key={g.key} data-testid={`pb-group-${g.key}`}>
          <h3 className="pb-group__head">
            {GROUP_LABEL[g.key] || g.key} <span className="pb-count mono">({g.tickers.length})</span>
          </h3>
          {!g.tickers.length ? (
            <p className="cm-foot mono">No names in this group.</p>
          ) : (
            <div className="cm-grid">
              {g.tickers.map((sym) => {
                const e = byTicker.get(sym);
                const rd = reads[sym];
                const tile = rd?.tile ? filterTile(rd.tile, hiddenOverlays) : null;
                const roomRow = room.map.get(sym);
                return (
                  <div className="pb-tile" key={`${g.key}-${sym}`} data-testid={`pb-tile-${g.key}-${sym}`}>
                    <div className="pb-tile__head">
                      <TickerLink ticker={sym} fromLabel="POTUS tab" className="pb-tile__sym" />
                      {e?.company ? <span className="pb-tile__co">{e.company}</span> : null}
                      {e?.is_new ? <span className="pb-new mono">✨ NEW</span> : null}
                      {' '}<SepaPoliticalChip symbol={sym} />
                      {' '}<GrowthChip symbol={sym} />
                      {' '}<ExplosiveChip study={room.payload?.explosive_study}
                                          read={roomRow?.explosive} />
                      {' '}<EnterableChip read={roomRow?.enterable} />
                      {' '}<SignalWatchButton symbol={sym} />
                    </div>
                    {e?.govtStake ? (
                      <p className="pb-tile__stake mono">Government stake: {e.govtStake}</p>
                    ) : null}
                    {e?.disclosureBand ? (
                      <p className="pb-tile__band mono">Disclosed band: {e.disclosureBand}</p>
                    ) : null}
                    {/* The notes are the part that says a row is NOT what the
                      * group header implies — "no government agreement" on the
                      * inferred names. Readable on the tile, never a tooltip. */}
                    {e?.notes ? <p className="pb-tile__note">{e.notes}</p> : null}
                    {tile ? (
                      <PatternChart tile={tile} study={room.payload?.explosive_study} />
                    ) : (
                      <p className="cm-foot mono">{rd?.error || 'loading chart…'}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ))}

      <section className="pb-candidates" data-testid="pb-candidates">
        <h3 className="pb-group__head">
          🔎 Watch candidates (heuristic) <span className="pb-count mono">({candidates.length})</span>
        </h3>
        {watch?.note ? <p className="cm-note pb-heuristic">{watch.note}</p> : null}
        {watch?.last_run ? (
          <p className="cm-foot mono">Last watch run: {watch.last_run}</p>
        ) : null}
        {!candidates.length ? (
          <p className="cm-foot mono" data-testid="pb-no-candidates">
            No candidates in the last {watchDays} day{watchDays === 1 ? '' : 's'}.
          </p>
        ) : (
          <table className="pb-table">
            <thead>
              <tr>
                <th>Ticker</th><th>Resolved by</th><th>Headline</th><th>Source</th>
                <th>Published (ET)</th><th>Pattern</th><th>Agency</th><th>Size</th>
                <th>First seen</th><th>Pushed</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => {
                const sym = c.ticker ? String(c.ticker).toUpperCase() : null;
                return (
                  <tr key={`${sym || 'unnamed'}-${c.headline?.url || i}`}
                      data-testid={`pb-candidate-${sym || 'unnamed'}`}>
                    <td>
                      {sym
                        ? <TickerLink ticker={sym} fromLabel="POTUS watch" />
                        : <span className="pb-unnamed">unnamed — needs a ticker</span>}
                      {c.company ? <span className="pb-cand__co"> {c.company}</span> : null}
                    </td>
                    <td className="mono">{RESOLUTION_LABEL[c.resolution || ''] || c.resolution || '—'}</td>
                    <td>
                      {c.headline?.url
                        ? <a href={c.headline.url} target="_blank" rel="noreferrer">{c.headline?.title || c.headline.url}</a>
                        : <span>{c.headline?.title || '—'}</span>}
                    </td>
                    <td className="mono">{c.headline?.source || '—'}</td>
                    <td className="mono">{publishedEt(c.headline?.published)}</td>
                    <td className="mono">{c.pattern || '—'}</td>
                    <td className="mono">{c.agency || '—'}</td>
                    <td className="mono">{c.size || '—'}</td>
                    <td className="mono">{c.first_seen || '—'}</td>
                    <td className="mono">{c.pushed ? 'pushed' : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
