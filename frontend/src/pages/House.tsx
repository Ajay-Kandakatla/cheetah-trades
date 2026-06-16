import { useMemo, useState } from 'react';
import {
  useHouseDashboard,
  saveHouseConfig,
  saveSnapshot,
  runScrape,
  addComp,
  removeComp,
  addEvent,
  removeEvent,
  type HouseConfig,
  type HouseComp,
  type HouseEvent,
} from '../hooks/useHouse';

const fmtMoney = (v?: number | null) => v == null ? '—' : `$${v.toLocaleString()}`;
const fmtNum   = (v?: number | null) => v == null ? '—' : v.toLocaleString();

/* localStorage keys for "marked done" checklist items — survives reloads
   without polluting Mongo. */
const DONE_KEY = 'house_checklist_done_v1';
function loadDone(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(DONE_KEY) || '[]')); }
  catch { return new Set(); }
}
function saveDone(set: Set<string>) {
  try { localStorage.setItem(DONE_KEY, JSON.stringify([...set])); }
  catch { /* quota — ignore */ }
}

export default function HousePage() {
  const { data, loading, allowed, reload } = useHouseDashboard();
  const [editConfig, setEditConfig] = useState(false);

  if (!allowed) {
    // Stealth — look identical to a real 404 so non-owners don't discover
    // the module exists.
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 className="display" style={{ margin: 0 }}>404</h1>
        <p className="lede" style={{ marginTop: '0.5rem' }}>Page not found.</p>
      </div>
    );
  }

  if (loading || !data) {
    return <div style={{ padding: '2rem' }}>Loading house dashboard…</div>;
  }

  const { config, latest, history, comps, events, playbook } = data;
  const hasConfig = !!config?.address;

  return (
    <div className="house-page" style={{ padding: '1.2rem 1.6rem', maxWidth: 1200, margin: '0 auto' }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div className="eyebrow">Personal · House Sale Dashboard</div>
          <h1 className="display" style={{ margin: '0.25rem 0 0' }}>
            {config?.address || 'Set your house address →'}
          </h1>
          {hasConfig && (
            <p className="lede" style={{ margin: '0.4rem 0 0' }}>
              Listed {fmtMoney(config.list_price)} · {playbook.dom} day{playbook.dom === 1 ? '' : 's'} on market · {playbook.phase_label}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="sepa-btn" onClick={() => setEditConfig((v) => !v)}>
            {editConfig ? 'Close config' : (hasConfig ? '✎ Edit config' : '+ Set up house')}
          </button>
          <button className="sepa-btn" onClick={reload}>↻ Reload</button>
        </div>
      </div>

      {/* ── Config form (collapsed unless toggled or no config yet) ─────── */}
      {(editConfig || !hasConfig) && (
        <ConfigForm
          initial={config}
          onSaved={async () => { setEditConfig(false); await reload(); }}
        />
      )}

      {!hasConfig ? (
        <div className="sepa-empty-card" style={{ marginTop: '1rem' }}>
          <p>Add your house address + list price + Redfin/Zillow URLs above to get started. Everything else flows from those.</p>
        </div>
      ) : (
        <>
          {/* ── Daily scrape status ─────────────────────────────────────
             Shows when the last automated update landed + how it got
             there. Helps the owner know if today's 8am ET cron actually
             succeeded before they start interpreting the KPIs. */}
          <DailyScrapeStatus latest={latest} />

          {/* ── KPI strip ──────────────────────────────────────────────── */}
          <KpiStrip data={data} />

          {/* ── Two-column grid: Today's metrics | Daily checklist ─────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: '1rem', marginTop: '1rem' }}>
            <PlatformPanel data={data} onReload={reload} />
            <ChecklistPanel data={data} />
          </div>

          {/* ── Strategy paragraphs ─────────────────────────────────────── */}
          <StrategyPanel paragraphs={playbook.strategy} phase={playbook.phase} />

          {/* ── Manual snapshot entry (above-the-fold for daily use) ─── */}
          <SnapshotForm latest={latest} prior={history.length >= 2 ? history[history.length - 2] : null} onSaved={reload} />

          {/* ── Activity timeline (last 14 days view+save totals) ─────── */}
          <TimelinePanel history={history} />

          {/* ── Comps + Events as two columns ──────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: '1rem', marginTop: '1rem' }}>
            <CompsPanel comps={comps} onReload={reload} />
            <EventsPanel events={events} onReload={reload} />
          </div>
        </>
      )}
    </div>
  );
}

/* ============================================================================
   Config form
   ========================================================================== */
function ConfigForm({ initial, onSaved }: { initial: HouseConfig; onSaved: () => void }) {
  const [c, setC] = useState<HouseConfig>(initial || {});
  const set = <K extends keyof HouseConfig>(k: K, v: HouseConfig[K]) => setC({ ...c, [k]: v });
  const num = (s: string) => (s === '' ? undefined : Number(s));

  const save = async () => {
    await saveHouseConfig(c);
    onSaved();
  };

  return (
    <div style={{ marginTop: '1rem', padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow" style={{ marginBottom: '0.6rem' }}>House config</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.6rem' }}>
        <Field label="Address" value={c.address || ''} onChange={(v) => set('address', v)} placeholder="1234 Maple Ln, McKinney, TX 75070" />
        <Field label="City"   value={c.city  || ''} onChange={(v) => set('city',  v)} />
        <Field label="State"  value={c.state || ''} onChange={(v) => set('state', v)} />
        <Field label="ZIP"    value={c.zip   || ''} onChange={(v) => set('zip',   v)} />
        <Field label="List price ($)" value={c.list_price?.toString() || ''} onChange={(v) => set('list_price', num(v))} type="number" />
        <Field label="Listed on (YYYY-MM-DD)" value={c.listed_on || ''} onChange={(v) => set('listed_on', v)} placeholder="2026-04-22" />
        <Field label="Beds"   value={c.beds?.toString() || ''} onChange={(v) => set('beds', num(v))} type="number" />
        <Field label="Baths"  value={c.baths?.toString() || ''} onChange={(v) => set('baths', num(v))} type="number" />
        <Field label="Sqft"   value={c.sqft?.toString() || ''} onChange={(v) => set('sqft', num(v))} type="number" />
        <Field label="Year built" value={c.year_built?.toString() || ''} onChange={(v) => set('year_built', num(v))} type="number" />
        <Field label="Zestimate ($)" value={c.zestimate?.toString() || ''} onChange={(v) => set('zestimate', num(v))} type="number" />
        <Field label="Redfin estimate ($)" value={c.redfin_estimate?.toString() || ''} onChange={(v) => set('redfin_estimate', num(v))} type="number" />
        <Field label="Redfin URL"  value={c.redfin_url  || ''} onChange={(v) => set('redfin_url', v)}  full placeholder="https://www.redfin.com/TX/McKinney/..." />
        <Field label="Zillow URL"  value={c.zillow_url  || ''} onChange={(v) => set('zillow_url', v)}  full placeholder="https://www.zillow.com/homedetails/..." />
        <Field label="Realtor URL" value={c.realtor_url || ''} onChange={(v) => set('realtor_url', v)} full placeholder="https://www.realtor.com/realestateandhomes-detail/..." />
        <Field label="MLS ID"      value={c.mls_id      || ''} onChange={(v) => set('mls_id', v)} />
        <Field label="Agent name"  value={c.agent_name  || ''} onChange={(v) => set('agent_name', v)} />
        <Field label="Agent phone" value={c.agent_phone || ''} onChange={(v) => set('agent_phone', v)} />
      </div>
      <div style={{ marginTop: '0.6rem' }}>
        <button className="sepa-btn sepa-btn--primary" onClick={save}>Save config</button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type, placeholder, full }: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; full?: boolean;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.78rem', gridColumn: full ? '1 / -1' : undefined }}>
      <span style={{ color: 'var(--cm-slate, #888)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>{label}</span>
      <input
        type={type || 'text'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ padding: '5px 8px', font: 'inherit', fontSize: '0.85rem', border: '1px solid var(--rule, #ccc)', borderRadius: 3, background: 'var(--bg, #fff)' }}
      />
    </label>
  );
}

/* ============================================================================
   Daily-scrape status banner
   ----------------------------------------------------------------------------
   Surfaces the freshness of today's auto-scrape data. The 8am ET cron
   (backend/house/daily_scrape.py) writes both `captured_at` (epoch
   seconds) and `source` ("scraper" / "manual" / merged label) onto the
   snapshot. We translate those into a one-line indicator + a soft
   warning when nothing's landed today.

   Why surface this prominently: the owner reads the KPIs to make
   pricing/staging decisions. Knowing whether the numbers reflect
   today's snapshot or yesterday's is more important than the numbers
   themselves.
   ========================================================================== */
function DailyScrapeStatus({ latest }: { latest: any }) {
  const captured = latest?.captured_at as number | undefined;
  const source   = (latest?.source as string | undefined) || 'manual';
  const dateEt   = latest?.date_et as string | undefined;

  // Pull "today" in ET via Intl so we don't depend on the browser's
  // local clock (user could be in IST/PT/etc and still want ET).
  const today = new Date().toLocaleDateString('en-CA', {
    timeZone: 'America/New_York',
  });
  const isToday = dateEt === today;

  let ageLine = '';
  if (captured) {
    const ageMin = Math.max(0, Math.floor((Date.now() / 1000 - captured) / 60));
    ageLine = ageMin < 60
      ? `${ageMin}m ago`
      : ageMin < 60 * 24
        ? `${Math.floor(ageMin / 60)}h ago`
        : `${Math.floor(ageMin / 60 / 24)}d ago`;
  }

  // Visual tone — green if today's scrape landed, amber if no data
  // yet today (cron may not have run, or sources blocked).
  const toneColor = isToday ? 'var(--positive, #10b981)' : 'var(--warn, #d97706)';
  const toneBg = isToday ? 'rgba(16,185,129,0.06)' : 'rgba(217,119,6,0.06)';

  return (
    <div
      style={{
        marginTop: '0.9rem',
        padding: '0.5rem 0.8rem',
        background: toneBg,
        border: `1px solid ${toneColor}`,
        borderRadius: 5,
        fontSize: '0.78rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.4rem',
      }}
    >
      <span style={{ color: toneColor }}>
        {isToday
          ? `✓ Today's snapshot: updated ${ageLine || 'recently'}`
          : `⚠ No snapshot for today yet${ageLine ? ` — last update ${ageLine}` : ''}`}
        <span style={{ color: 'var(--cm-slate)', marginLeft: 8 }}>
          · source: {source}
        </span>
      </span>
      <span style={{ color: 'var(--cm-slate)', fontSize: '0.7rem' }}>
        Auto-scrape runs daily at 8 AM ET. Daily summary push (🏡) lands then if you've enabled the
        <em> House · daily summary</em> notification.
      </span>
    </div>
  );
}

/* ============================================================================
   KPI strip — top-of-page numbers
   ========================================================================== */
function KpiStrip({ data }: { data: { config: HouseConfig; playbook: any; latest: any } }) {
  const { config, playbook, latest } = data;
  const askVsZest = config.zestimate && config.list_price
    ? ((config.list_price - config.zestimate) / config.zestimate) * 100 : null;
  const askPpsf = config.list_price && config.sqft ? Math.round(config.list_price / config.sqft) : null;
  const compMedian = playbook.comp_signal.comp_median_ppsf;
  const ppsfDelta = askPpsf && compMedian ? ((askPpsf - compMedian) / compMedian) * 100 : null;
  const trend = playbook.velocity.trend;
  const trendEmoji = trend === 'heating' ? '🔥' : trend === 'cooling' ? '🥶' : trend === 'stable' ? '→' : '·';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem', marginTop: '1rem' }}>
      <Kpi label="Days on market" value={String(playbook.dom)} sub={playbook.phase_label} />
      <Kpi label="Interested (today)" value={String(playbook.totals.saves + playbook.totals.tours)}
           sub={`${playbook.totals.saves} saves · ${playbook.totals.tours} tours`}
           tone={playbook.totals.saves > 30 ? 'good' : playbook.totals.saves > 10 ? 'neutral' : 'warn'} />
      <Kpi label="Total views (today)" value={fmtNum(playbook.totals.views)}
           sub={trend === 'cooling' ? `${trendEmoji} cooling vs prior 3d` : trend === 'heating' ? `${trendEmoji} heating vs prior 3d` : 'across Redfin + Zillow'}
           tone={trend === 'heating' ? 'good' : trend === 'cooling' ? 'warn' : 'neutral'} />
      <Kpi label="List price" value={fmtMoney(config.list_price)}
           sub={askPpsf ? `$${askPpsf}/sqft` : '—'} />
      <Kpi label="Vs Zestimate" value={askVsZest != null ? `${askVsZest >= 0 ? '+' : ''}${askVsZest.toFixed(1)}%` : '—'}
           sub={config.zestimate ? `Zest ${fmtMoney(config.zestimate)}` : 'add Zestimate in config'}
           tone={askVsZest == null ? 'neutral' : askVsZest > 5 ? 'warn' : askVsZest < -2 ? 'good' : 'neutral'} />
      <Kpi label="Vs comp $/sqft" value={ppsfDelta != null ? `${ppsfDelta >= 0 ? '+' : ''}${ppsfDelta.toFixed(1)}%` : '—'}
           sub={compMedian ? `median $${compMedian}/sqft (n=${playbook.comp_signal.comp_count})` : 'add comps below'}
           tone={ppsfDelta == null ? 'neutral' : ppsfDelta > 5 ? 'warn' : ppsfDelta < 0 ? 'good' : 'neutral'} />
      <Kpi label="Offers" value={String(latest?.offers_received ?? 0)}
           sub={(latest?.offers_received ?? 0) > 0 ? '📩 review now' : 'none yet'}
           tone={(latest?.offers_received ?? 0) > 0 ? 'good' : 'neutral'} />
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'good' | 'warn' | 'neutral' }) {
  const color = tone === 'good' ? 'var(--positive, #10b981)'
              : tone === 'warn' ? 'var(--warn, #d97706)'
              : 'var(--ink, inherit)';
  return (
    <div style={{ padding: '0.7rem 0.85rem', border: '1px solid var(--rule, #ddd)', borderRadius: 5, background: 'var(--bg-raised)' }}>
      <div className="eyebrow" style={{ fontSize: '0.66rem' }}>{label}</div>
      <div style={{ font: '700 1.4rem var(--serif, serif)', color, marginTop: 2 }}>{value}</div>
      {sub && <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #888)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* ============================================================================
   Per-platform breakdown
   ========================================================================== */
function PlatformPanel({ data, onReload }: { data: any; onReload: () => void }) {
  const { platforms } = data.playbook;
  const [scraping, setScraping] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null);

  const doScrape = async () => {
    setScraping(true); setScrapeMsg(null);
    try {
      const r = await runScrape();
      if (!r.ok) setScrapeMsg(r.reason || 'scraper found nothing');
      else setScrapeMsg('✓ scraped + merged into today\'s snapshot');
      await onReload();
    } catch { setScrapeMsg('scraper failed'); }
    finally { setScraping(false); }
  };

  return (
    <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div className="eyebrow">Today's interest by platform</div>
        <button className="sepa-btn" onClick={doScrape} disabled={scraping} title="Best-effort scrape of Redfin/Zillow/Realtor — fills today's snapshot">
          {scraping ? '…scraping' : '↻ scrape now'}
        </button>
      </div>
      <PlatformRow name="Redfin"  views={platforms.redfin.views}  saves={platforms.redfin.saves}  tours={platforms.redfin.tours}
                   prevViews={platforms.redfin.prev_views} prevSaves={platforms.redfin.prev_saves} prevTours={platforms.redfin.prev_tours}
                   url={platforms.redfin.url} />
      <PlatformRow name="Zillow"  views={platforms.zillow.views}  saves={platforms.zillow.saves}
                   prevViews={platforms.zillow.prev_views} prevSaves={platforms.zillow.prev_saves}
                   url={platforms.zillow.url} />
      <PlatformRow name="Realtor" saves={platforms.realtor.saves} prevSaves={platforms.realtor.prev_saves} url={platforms.realtor.url} />
      {scrapeMsg && <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: 'var(--cm-slate)' }}>{scrapeMsg}</div>}
    </section>
  );
}

function PlatformRow({ name, views, saves, tours, prevViews, prevSaves, prevTours, url }: {
  name: string; views?: number; saves?: number; tours?: number;
  prevViews?: number; prevSaves?: number; prevTours?: number; url?: string;
}) {
  const empty = views == null && saves == null && tours == null;
  const delta = (cur?: number, prev?: number) => {
    if (cur == null || prev == null) return null;
    const d = cur - prev;
    if (d === 0) return ' (=)';
    return ` (${d > 0 ? '+' : ''}${d} vs y'day)`;
  };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '0.5rem', padding: '0.45rem 0', borderBottom: '1px dashed var(--hairline, #eee)' }}>
      <div style={{ fontWeight: 700 }}>
        {url ? <a href={url} target="_blank" rel="noreferrer" style={{ color: 'inherit' }}>{name} ↗</a> : name}
      </div>
      <div className="mono" style={{ fontSize: '0.85rem' }}>
        {views != null && <>views <strong>{fmtNum(views)}</strong><span style={{ color: 'var(--cm-slate)' }}>{delta(views, prevViews)}</span>{'  '}</>}
        {saves != null && <>· saves <strong>{fmtNum(saves)}</strong><span style={{ color: 'var(--cm-slate)' }}>{delta(saves, prevSaves)}</span>{'  '}</>}
        {tours != null && <>· tours <strong>{fmtNum(tours)}</strong><span style={{ color: 'var(--cm-slate)' }}>{delta(tours, prevTours)}</span></>}
        {empty && (
          <span style={{ color: 'var(--warn, #d97706)' }}>
            no data — enter manually below ↓
            {(prevViews != null || prevSaves != null) && (
              <span style={{ color: 'var(--cm-slate)', marginLeft: '0.4rem' }}>
                (yesterday: {prevViews != null ? `${fmtNum(prevViews)} views` : ''}{prevViews != null && prevSaves != null ? ' · ' : ''}{prevSaves != null ? `${fmtNum(prevSaves)} saves` : ''})
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}

/* ============================================================================
   Daily checklist
   ========================================================================== */
function ChecklistPanel({ data }: { data: any }) {
  const { checklist } = data.playbook;
  const [done, setDone] = useState<Set<string>>(loadDone);
  const toggle = (id: string) => {
    const next = new Set(done);
    if (next.has(id)) next.delete(id); else next.add(id);
    setDone(next);
    saveDone(next);
  };

  return (
    <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow" style={{ marginBottom: '0.6rem' }}>Today's checklist · {data.playbook.phase_label}</div>
      {checklist.map((c: any) => {
        const isDone = done.has(c.id);
        return (
          <div key={c.id} style={{ display: 'flex', gap: '0.55rem', padding: '0.45rem 0', borderBottom: '1px dashed var(--hairline, #eee)', opacity: isDone ? 0.55 : 1 }}>
            <input type="checkbox" checked={isDone} onChange={() => toggle(c.id)} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, textDecoration: isDone ? 'line-through' : 'none' }}>
                {c.priority === 'high' && <span style={{ color: 'var(--negative, #ef4444)' }}>● </span>}
                {c.priority === 'med'  && <span style={{ color: 'var(--warn, #d97706)' }}>● </span>}
                {c.label}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--cm-slate, #888)', marginTop: 2 }}>{c.why}</div>
            </div>
          </div>
        );
      })}
      {checklist.length === 0 && <div style={{ color: 'var(--cm-slate)' }}>Nothing on the list — set up your house config first.</div>}
    </section>
  );
}

/* ============================================================================
   Strategy paragraphs
   ========================================================================== */
function StrategyPanel({ paragraphs, phase }: { paragraphs: string[]; phase: string }) {
  if (!paragraphs.length) return null;
  const tone = phase === 'launch' ? 'var(--positive, #10b981)'
             : phase === 'reset'  ? 'var(--ink, inherit)'
             : phase === 'reduce' ? 'var(--warn, #d97706)'
             :                      'var(--negative, #ef4444)';
  return (
    <section style={{ marginTop: '1rem', padding: '0.9rem 1.1rem', border: `1px solid ${tone}40`, borderLeft: `4px solid ${tone}`, borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow" style={{ color: tone }}>Strategy — {phase} phase</div>
      {paragraphs.map((p, i) => (
        <p key={i} style={{ margin: '0.5rem 0 0', fontSize: '0.9rem', lineHeight: 1.55 }}>{p}</p>
      ))}
    </section>
  );
}

/* ============================================================================
   Manual snapshot entry
   ========================================================================== */
function SnapshotForm({ latest, prior, onSaved }: { latest: any; prior: any | null; onSaved: () => void }) {
  const [s, setS] = useState<any>({});
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const num = (v: string) => (v === '' ? undefined : Number(v));
  // Yesterday's value as a placeholder hint — tap-to-replace is faster
  // than typing the same number again on a phone.
  const ph = (k: string): string | undefined => {
    const v = (latest && latest[k]) ?? (prior && prior[k]);
    return v != null ? `y'day: ${v}` : undefined;
  };
  const useYesterday = () => {
    if (!prior) return;
    setS({
      redfin_views: prior.redfin_views, redfin_saves: prior.redfin_saves, redfin_tours: prior.redfin_tours,
      zillow_views: prior.zillow_views, zillow_saves: prior.zillow_saves,
      realtor_saves: prior.realtor_saves,
    });
  };

  const submit = async () => {
    await saveSnapshot(s);
    setSavedAt(Date.now());
    setS({});
    await onSaved();
  };

  return (
    <section style={{ marginTop: '1rem', padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow">Today's numbers — manual entry</div>
      <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate, #888)', margin: '0.25rem 0 0.7rem' }}>
        Open Redfin / Zillow / Realtor on your phone, copy today's view + save + tour counts here. Auto-merges with anything the scraper already pulled today.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem' }}>
        <Field label="Redfin views"  placeholder={ph('redfin_views')}  value={s.redfin_views?.toString()  || ''} onChange={(v) => setS({ ...s, redfin_views:  num(v) })} type="number" />
        <Field label="Redfin saves"  placeholder={ph('redfin_saves')}  value={s.redfin_saves?.toString()  || ''} onChange={(v) => setS({ ...s, redfin_saves:  num(v) })} type="number" />
        <Field label="Redfin tours"  placeholder={ph('redfin_tours')}  value={s.redfin_tours?.toString()  || ''} onChange={(v) => setS({ ...s, redfin_tours:  num(v) })} type="number" />
        <Field label="Zillow views"  placeholder={ph('zillow_views')}  value={s.zillow_views?.toString()  || ''} onChange={(v) => setS({ ...s, zillow_views:  num(v) })} type="number" />
        <Field label="Zillow saves"  placeholder={ph('zillow_saves')}  value={s.zillow_saves?.toString()  || ''} onChange={(v) => setS({ ...s, zillow_saves:  num(v) })} type="number" />
        <Field label="Realtor saves" placeholder={ph('realtor_saves')} value={s.realtor_saves?.toString() || ''} onChange={(v) => setS({ ...s, realtor_saves: num(v) })} type="number" />
        <Field label="Showings today" value={s.showings_today?.toString() || ''} onChange={(v) => setS({ ...s, showings_today: num(v) })} type="number" />
        <Field label="Open houses scheduled" value={s.open_houses_scheduled?.toString() || ''} onChange={(v) => setS({ ...s, open_houses_scheduled: num(v) })} type="number" />
        <Field label="Offers received" value={s.offers_received?.toString() || ''} onChange={(v) => setS({ ...s, offers_received: num(v) })} type="number" />
        <Field label="Current list price (if changed)" value={s.current_list_price?.toString() || ''} onChange={(v) => setS({ ...s, current_list_price: num(v) })} type="number" />
      </div>
      <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
        <button className="sepa-btn sepa-btn--primary" onClick={submit}>Save today's snapshot</button>
        {prior && <button className="sepa-btn" onClick={useYesterday} title="Pre-fill all view/save/tour fields with yesterday's numbers">↻ copy yesterday</button>}
        {savedAt && <span style={{ fontSize: '0.78rem', color: 'var(--positive, #10b981)' }}>✓ saved</span>}
        {latest && <span style={{ fontSize: '0.78rem', color: 'var(--cm-slate)' }}>last saved: {latest.date_et}</span>}
      </div>
    </section>
  );
}

/* ============================================================================
   Activity timeline — sparkline of total views/saves last 14 days
   ========================================================================== */
function TimelinePanel({ history }: { history: any[] }) {
  const points = useMemo(() => {
    const last = history.slice(-14);
    return last.map((h) => ({
      date: h.date_et,
      views: (h.redfin_views || 0) + (h.zillow_views || 0),
      saves: (h.redfin_saves || 0) + (h.zillow_saves || 0) + (h.realtor_saves || 0),
      tours: (h.redfin_tours || 0),
    }));
  }, [history]);

  if (points.length === 0) {
    return null;
  }

  const maxViews = Math.max(1, ...points.map((p) => p.views));
  const maxSaves = Math.max(1, ...points.map((p) => p.saves));
  const W = 600, H = 110, P = 24;
  const xStep = points.length > 1 ? (W - P * 2) / (points.length - 1) : 0;
  const viewPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${P + i * xStep},${H - P - (p.views / maxViews) * (H - P * 2)}`).join(' ');
  const savePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${P + i * xStep},${H - P - (p.saves / maxSaves) * (H - P * 2)}`).join(' ');

  return (
    <section style={{ marginTop: '1rem', padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow">Activity — last {points.length} day{points.length === 1 ? '' : 's'}</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, marginTop: '0.4rem' }}>
        <path d={viewPath} fill="none" stroke="#3b82f6" strokeWidth="2" />
        <path d={savePath} fill="none" stroke="#10b981" strokeWidth="2" />
      </svg>
      <div style={{ display: 'flex', gap: '1rem', fontSize: '0.78rem', marginTop: '0.4rem' }}>
        <span><span style={{ display: 'inline-block', width: 10, height: 2, background: '#3b82f6', verticalAlign: 'middle', marginRight: 4 }} />views</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 2, background: '#10b981', verticalAlign: 'middle', marginRight: 4 }} />saves</span>
      </div>
    </section>
  );
}

/* ============================================================================
   Comps
   ========================================================================== */
function CompsPanel({ comps, onReload }: { comps: HouseComp[]; onReload: () => void }) {
  const [adding, setAdding] = useState(false);
  const [c, setC] = useState<HouseComp>({ address: '' });
  const num = (v: string) => (v === '' ? undefined : Number(v));

  const submit = async () => {
    if (!c.address) return;
    await addComp(c);
    setC({ address: '' });
    setAdding(false);
    await onReload();
  };

  return (
    <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div className="eyebrow">Comps — recent solds</div>
        <button className="sepa-btn" onClick={() => setAdding((v) => !v)}>{adding ? 'cancel' : '+ comp'}</button>
      </div>
      {adding && (
        <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem' }}>
          <Field label="Address"      value={c.address || ''}              onChange={(v) => setC({ ...c, address: v })} full />
          <Field label="Sold price"   value={c.sold_price?.toString() || ''} onChange={(v) => setC({ ...c, sold_price: num(v) })} type="number" />
          <Field label="Sold date"    value={c.sold_date  || ''}            onChange={(v) => setC({ ...c, sold_date: v })} placeholder="2026-04-01" />
          <Field label="Sqft"         value={c.sqft?.toString() || ''}      onChange={(v) => setC({ ...c, sqft: num(v) })} type="number" />
          <Field label="Beds"         value={c.beds?.toString() || ''}      onChange={(v) => setC({ ...c, beds: num(v) })} type="number" />
          <Field label="Baths"        value={c.baths?.toString() || ''}     onChange={(v) => setC({ ...c, baths: num(v) })} type="number" />
          <Field label="Distance (mi)" value={c.distance_mi?.toString() || ''} onChange={(v) => setC({ ...c, distance_mi: num(v) })} type="number" />
          <button className="sepa-btn sepa-btn--primary" onClick={submit} style={{ gridColumn: '1 / -1' }}>Save comp</button>
        </div>
      )}
      <table className="mono" style={{ width: '100%', marginTop: '0.5rem', fontSize: '0.78rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--cm-slate, #888)' }}>
            <th>Address</th><th>Sold</th><th>$/sqft</th><th></th>
          </tr>
        </thead>
        <tbody>
          {comps.map((c) => (
            <tr key={c.address} style={{ borderTop: '1px dashed var(--hairline, #eee)' }}>
              <td>{c.address}</td>
              <td>{fmtMoney(c.sold_price)} · {c.sold_date || '—'}</td>
              <td>${c.ppsf ?? '—'}</td>
              <td><button onClick={async () => { await removeComp(c.address); await onReload(); }} style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer' }}>✕</button></td>
            </tr>
          ))}
          {comps.length === 0 && <tr><td colSpan={4} style={{ color: 'var(--cm-slate)', padding: '0.5rem 0' }}>No comps yet — add 3-5 recent solds in your subdivision/0.5mi for the playbook to recommend price action.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}

/* ============================================================================
   Events log — open houses, showings, offers, price drops
   ========================================================================== */
function EventsPanel({ events, onReload }: { events: HouseEvent[]; onReload: () => void }) {
  const [adding, setAdding] = useState(false);
  const [e, setE] = useState<Partial<HouseEvent>>({ kind: 'note' });

  const submit = async () => {
    if (!e.label) return;
    await addEvent(e);
    setE({ kind: 'note' });
    setAdding(false);
    await onReload();
  };

  return (
    <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div className="eyebrow">Events log</div>
        <button className="sepa-btn" onClick={() => setAdding((v) => !v)}>{adding ? 'cancel' : '+ event'}</button>
      </div>
      {adding && (
        <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem' }}>
          <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.78rem' }}>
            <span style={{ color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Kind</span>
            <select value={e.kind} onChange={(ev) => setE({ ...e, kind: ev.target.value as any })} style={{ padding: 5 }}>
              <option value="open_house">open house</option>
              <option value="showing">showing</option>
              <option value="offer">offer</option>
              <option value="price_drop">price drop</option>
              <option value="feedback">feedback</option>
              <option value="note">note</option>
            </select>
          </label>
          <Field label="Label" value={e.label || ''} onChange={(v) => setE({ ...e, label: v })} full placeholder="Sat 1-3pm open house" />
          <Field label="Notes" value={e.notes || ''} onChange={(v) => setE({ ...e, notes: v })} full />
          <button className="sepa-btn sepa-btn--primary" onClick={submit} style={{ gridColumn: '1 / -1' }}>Add event</button>
        </div>
      )}
      <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
        {events.map((ev) => (
          <li key={ev._id} style={{ padding: '0.4rem 0', borderTop: '1px dashed var(--hairline, #eee)', display: 'flex', justifyContent: 'space-between' }}>
            <span>
              <span className="mono" style={{ color: 'var(--cm-slate)', marginRight: '0.4rem' }}>{new Date(ev.ts * 1000).toLocaleDateString()}</span>
              <strong>{ev.kind}</strong> · {ev.label}
              {ev.notes && <span style={{ color: 'var(--cm-slate)', fontStyle: 'italic' }}> — {ev.notes}</span>}
            </span>
            <button onClick={async () => { if (ev._id) { await removeEvent(ev._id); await onReload(); } }} style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer' }}>✕</button>
          </li>
        ))}
        {events.length === 0 && <li style={{ color: 'var(--cm-slate)', padding: '0.5rem 0' }}>No events yet. Log open houses, showings, offers, and price drops here so the playbook can correlate them with view/save trends.</li>}
      </ul>
    </section>
  );
}
