import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { readCache, writeCache } from '../lib/swrCache';

type Activity = {
  id: string;
  name: string;
  framework: string;
  age_min: number;
  age_max: number;
  duration_min: number;
  materials: string[];
  skill: string;
  mess_level: number;
  setup_min: number | string;
  reset_min: number;
  notes: string;
  source: string;
  search_query: string;
  /** Validated YouTube video — populated by kids/video_resolver pipeline
   *  (Gemma + YouTube scrape + oEmbed validation). Direct link when present. */
  validated_video?: {
    video_id: string;
    video_url: string;
    title: string;
    author_name: string;
    thumbnail?: string;
  };
};

type Influencer = {
  name: string;
  framework: string;
  blurb: string;
  links: { label: string; url: string }[];
};

type TodayResponse = {
  date_et: string;
  picks: Activity[];
  filter: { age: number; mess_max: number; duration_max: number; framework: string | null };
  recent_count: number;
  frameworks: Record<string, string>;
};

export default function KidsPage() {
  // SWR — render from localStorage instantly, refresh in background.
  // Same pattern as food/sepa: zero loading delay on revisit.
  const KIDS_CACHE_KEY = 'kids.today';
  const KIDS_INF_KEY = 'kids.influencers';
  const [data, setData] = useState<TodayResponse | null>(() => {
    const env = readCache<TodayResponse>(KIDS_CACHE_KEY);
    return env?.data ?? null;
  });
  const [allowed, setAllowed] = useState(true);
  const [loading, setLoading] = useState(() => readCache<TodayResponse>(KIDS_CACHE_KEY) === null);
  const [influencers, setInfluencers] = useState<Influencer[]>(() => {
    const env = readCache<{influencers: Influencer[]}>(KIDS_INF_KEY);
    return env?.data?.influencers ?? [];
  });
  const [showInfluencers, setShowInfluencers] = useState(false);

  // Filter state — persisted per-user via localStorage
  const [age, setAge] = useState<number>(() => Number(localStorage.getItem('kids.age') || '3.5'));
  const [messMax, setMessMax] = useState<number>(() => Number(localStorage.getItem('kids.messMax') || '5'));
  const [durationMax, setDurationMax] = useState<number>(() => Number(localStorage.getItem('kids.durationMax') || '60'));
  const [framework, setFramework] = useState<string>(() => localStorage.getItem('kids.framework') || '');

  useEffect(() => { localStorage.setItem('kids.age', String(age)); }, [age]);
  useEffect(() => { localStorage.setItem('kids.messMax', String(messMax)); }, [messMax]);
  useEffect(() => { localStorage.setItem('kids.durationMax', String(durationMax)); }, [durationMax]);
  useEffect(() => { localStorage.setItem('kids.framework', framework); }, [framework]);

  const reload = async () => {
    try {
      const params = new URLSearchParams({
        age: String(age),
        mess_max: String(messMax),
        duration_max: String(durationMax),
      });
      if (framework) params.set('framework', framework);
      const r = await fetch(`${API}/kids/today?${params}`);
      if (r.status === 403 || r.status === 404) { setAllowed(false); return; }
      if (r.ok) {
        const fresh = await r.json();
        setData(fresh);
        writeCache(KIDS_CACHE_KEY, fresh);
      }
      setAllowed(true);
    } finally { setLoading(false); }
  };

  useEffect(() => { reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [age, messMax, durationMax, framework]);
  useEffect(() => {
    fetch(`${API}/kids/influencers`)
      .then((r) => r.ok ? r.json() : { influencers: [] })
      .then((j) => { setInfluencers(j.influencers || []); writeCache(KIDS_INF_KEY, j); });
  }, []);

  const logDone = async (id: string) => {
    await fetch(`${API}/kids/log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activity_id: id }),
    });
    reload();
  };

  if (!allowed) {
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 className="display" style={{ margin: 0 }}>404</h1>
        <p className="lede" style={{ marginTop: '0.5rem' }}>Page not found.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '1.2rem 1.6rem', maxWidth: 1100, margin: '0 auto' }}>
      <div className="eyebrow">Family · Kids Activities</div>
      <h1 className="display" style={{ margin: '0.25rem 0 0' }}>Today's Play</h1>
      <p className="lede" style={{ margin: '0.4rem 0 0' }}>
        Household-item activities for the 3.5-year-old. Grounded in Montessori, RIE, Reggio,
        Whole-Brain Child + Big Little Feelings research.
      </p>

      {/* ── FILTERS ─────────────────────────────────────────────────────── */}
      <section className="kids-filters">
        <label>
          <span className="kids-label">Age</span>
          <input type="number" step="0.5" min="1" max="10" value={age}
                 onChange={(e) => setAge(Number(e.target.value))} />
        </label>
        <label>
          <span className="kids-label">Max mess level</span>
          <select value={messMax} onChange={(e) => setMessMax(Number(e.target.value))}>
            <option value={1}>1 — clean only</option>
            <option value={2}>2 — light</option>
            <option value={3}>3 — normal</option>
            <option value={4}>4 — bring it</option>
            <option value={5}>5 — full chaos</option>
          </select>
        </label>
        <label>
          <span className="kids-label">Max duration (min)</span>
          <select value={durationMax} onChange={(e) => setDurationMax(Number(e.target.value))}>
            <option value={15}>15 — quick</option>
            <option value={30}>30 — medium</option>
            <option value={60}>60 — long</option>
            <option value={180}>180 — anything</option>
          </select>
        </label>
        <label>
          <span className="kids-label">Framework</span>
          <select value={framework} onChange={(e) => setFramework(e.target.value)}>
            <option value="">Any</option>
            {data && Object.keys(data.frameworks).map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
        </label>
        <button className="sepa-btn" onClick={reload}>↻ New picks</button>
      </section>

      {/* ── TODAY'S PICKS ───────────────────────────────────────────────── */}
      {loading && <p style={{ marginTop: '1rem' }}>Loading…</p>}
      {data && data.picks.length === 0 && (
        <p style={{ marginTop: '1rem', color: 'var(--cm-slate)' }}>
          No matches with current filters. Try widening max mess or duration.
        </p>
      )}
      {data && data.picks.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
          {data.picks.map((a) => (
            <ActivityCard key={a.id} a={a} onDone={() => logDone(a.id)} />
          ))}
        </div>
      )}

      {/* ── INFLUENCERS / RESEARCH ──────────────────────────────────────── */}
      <section style={{ marginTop: '1.5rem', padding: '1rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div>
            <div className="eyebrow">📚 The research behind these</div>
            <p style={{ fontSize: '0.85rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0' }}>
              Every activity here cites a parenting framework. Click below to dig into the source authors.
            </p>
          </div>
          <button className="sepa-btn" onClick={() => setShowInfluencers((v) => !v)}>
            {showInfluencers ? 'Hide' : 'Show'} ({influencers.length})
          </button>
        </div>
        {showInfluencers && (
          <div style={{ marginTop: '0.8rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.7rem' }}>
            {influencers.map((inf) => (
              <div key={inf.name} style={{ padding: '0.7rem 0.85rem', border: '1px solid var(--hairline)', borderRadius: 5, background: 'var(--bg-surface, var(--bg-raised))' }}>
                <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{inf.name}</div>
                <div className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 2 }}>
                  {inf.framework}
                </div>
                <p style={{ fontSize: '0.82rem', marginTop: '0.4rem', lineHeight: 1.45 }}>
                  {inf.blurb}
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.45rem' }}>
                  {inf.links.map((l) => (
                    <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="food-link food-link--recipe">
                      {l.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/* ============================================================================
   Activity card
   ========================================================================== */
function ActivityCard({ a, onDone }: { a: Activity; onDone: () => void }) {
  const messEmoji = '🟢🟡🟠🔴🔥'.split('').slice(0, a.mess_level).join('');
  return (
    <article style={{ padding: '1rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {a.framework} · ages {a.age_min}-{a.age_max}
      </div>
      <h3 style={{ margin: '0.3rem 0 0', fontSize: '1.05rem' }}>{a.name}</h3>
      <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginTop: '0.25rem' }}>
        ⏱ {a.duration_min} min · setup {a.setup_min}min · reset {a.reset_min}min · mess {messEmoji}
      </div>

      <div style={{ marginTop: '0.7rem' }}>
        <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>You'll need</div>
        <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.84rem', lineHeight: 1.4 }}>
          {a.materials.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      </div>

      <div style={{ marginTop: '0.7rem' }}>
        <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>How</div>
        <p style={{ fontSize: '0.86rem', margin: 0, lineHeight: 1.5 }}>{a.notes}</p>
      </div>

      <div style={{ marginTop: '0.55rem', fontSize: '0.7rem', color: 'var(--ink-muted)', fontStyle: 'italic' }}>
        Source: {a.source}
      </div>

      <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.7rem', flexWrap: 'wrap' }}>
        <button onClick={onDone} className="sepa-btn sepa-btn--primary">✓ Did this today</button>
        {/* Validated direct video when resolver has cached one — Gemma
            picked + oEmbed-confirmed live. Otherwise fall back to YouTube
            search query. */}
        {a.validated_video ? (
          <a
            href={a.validated_video.video_url}
            target="_blank"
            rel="noreferrer"
            className="food-link food-link--video food-link--validated"
            title={`✓ Validated · ${a.validated_video.author_name} — ${a.validated_video.title}`}
          >
            ▶ {a.validated_video.author_name}
          </a>
        ) : (
          <a href={`https://www.youtube.com/results?search_query=${encodeURIComponent(a.search_query)}`}
             target="_blank" rel="noreferrer" className="food-link food-link--video">
            ▶ Video search
          </a>
        )}
        <a href={`https://www.google.com/search?q=${encodeURIComponent(a.search_query)}`}
           target="_blank" rel="noreferrer" className="food-link food-link--recipe">
          🔍 More
        </a>
      </div>

      <div className="kids-skill" style={{ marginTop: '0.55rem', fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
        Develops: {a.skill.replace(/_/g, ' ').replace(/ · /g, ', ')}
      </div>
    </article>
  );
}
