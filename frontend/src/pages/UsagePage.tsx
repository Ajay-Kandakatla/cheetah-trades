/* /usage — Usage Heatmap. What Ajay actually uses, for future context.
 *
 * Page-usage + a weekday×hour heatmap come from the existing page-view analytics
 * (real dwell history); in-page feature clicks come from usageTracker. Owner-only
 * (gated by the `usage` feature flag). Educational/insight, no trading content.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { InfoButton } from '../components/InfoButton';

type Row = { key: string; visits?: number; total_sec?: number; count?: number };
type Summary = {
  available: boolean;
  total_visits: number;
  total_sec: number;
  window_days: number;
  modules: Row[];
  routes: Row[];
  heatmap: Record<string, number>;
  features: Row[];
};

const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

function fmtDur(sec: number): string {
  const h = sec / 3600;
  return h >= 1 ? `${h.toFixed(1)}h` : `${Math.round(sec / 60)}m`;
}

const PageInfo = (
  <>
    <p>
      <strong>Usage Heatmap</strong> shows which pages and features you lean on, and
      when — built from your own page-view history plus in-page interactions.
    </p>
    <ul>
      <li><strong>Heatmap</strong> — page views by weekday × hour (ET), so your real rhythm shows.</li>
      <li><strong>Top pages</strong> — by visit count and total on-screen time.</li>
      <li><strong>Top features</strong> — filters/chips/modals you actually click.</li>
    </ul>
    <p className="mono">Stores route/feature names only — no PII, no payloads.</p>
  </>
);

export function UsagePage() {
  const [s, setS] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/usage/summary?days=30`);
        if (r.ok) setS(await r.json());
      } catch {
        /* keep empty */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const heat = s?.heatmap ?? {};
  const maxHeat = Math.max(1, ...Object.values(heat));
  const maxMod = Math.max(1, ...(s?.modules ?? []).map((m) => m.visits ?? 0));
  const maxFeat = Math.max(1, ...(s?.features ?? []).map((f) => f.count ?? 0));

  return (
    <div className="sepa-page usage-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Usage · what you actually use</div>
          <h1 className="display sepa-page__h1"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Usage Heatmap
            <InfoButton inline title="Usage Heatmap">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Which pages and features you lean on, and when — so future context knows
            what actually matters to you.
          </p>
        </div>
      </div>

      {loading && !s && <p className="mono" style={{ opacity: 0.7 }}>…reading your usage</p>}

      {s && !s.available && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No usage yet</div>
          <p>Once you've browsed a few pages this fills in — it reads your own page-view history.</p>
        </div>
      )}

      {s && s.available && (
        <>
          <div className="uh-stats mono">
            {s.total_visits.toLocaleString()} page views · {fmtDur(s.total_sec)} on-screen · last {s.window_days} days
          </div>

          {/* Weekday × hour heatmap */}
          <section className="uh-card">
            <div className="eyebrow">When you use it · weekday × hour (ET)</div>
            <div className="uh-heat">
              <div className="uh-heat__row uh-heat__row--head">
                <span className="uh-heat__wd" />
                {HOURS.map((h) => <span key={h} className="uh-heat__hr">{h % 6 === 0 ? h : ''}</span>)}
              </div>
              {WD.map((label, wd) => (
                <div key={wd} className="uh-heat__row">
                  <span className="uh-heat__wd">{label}</span>
                  {HOURS.map((h) => {
                    const c = heat[`${wd}_${h}`] || 0;
                    const i = c / maxHeat;
                    return (
                      <span
                        key={h}
                        className="uh-cell"
                        title={`${label} ${h}:00 — ${c} views`}
                        style={{ background: c
                          ? `color-mix(in srgb, var(--gold-strong, #d4af37) ${Math.round(15 + 85 * i)}%, transparent)`
                          : 'rgba(255,255,255,0.04)' }}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </section>

          {/* Top pages */}
          <section className="uh-card">
            <div className="eyebrow">Top pages · by visits + time</div>
            {s.modules.map((m) => (
              <div key={m.key} className="uh-bar">
                <span className="uh-bar__label">{m.key}</span>
                <span className="uh-bar__track">
                  <span className="uh-bar__fill" style={{ width: `${Math.round(100 * (m.visits ?? 0) / maxMod)}%` }} />
                </span>
                <span className="uh-bar__num mono">{m.visits} · {fmtDur(m.total_sec ?? 0)}</span>
              </div>
            ))}
          </section>

          {/* Top features */}
          <section className="uh-card">
            <div className="eyebrow">Top features · in-page clicks</div>
            {s.features.length === 0 && (
              <p className="mono" style={{ opacity: 0.6 }}>
                No feature clicks tracked yet — interact with filters/chips and they'll show here.
              </p>
            )}
            {s.features.map((f) => (
              <div key={f.key} className="uh-bar">
                <span className="uh-bar__label">{f.key}</span>
                <span className="uh-bar__track">
                  <span className="uh-bar__fill uh-bar__fill--alt" style={{ width: `${Math.round(100 * (f.count ?? 0) / maxFeat)}%` }} />
                </span>
                <span className="uh-bar__num mono">{f.count}</span>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
