/* Volleyball — personal fitness module.
 *
 *  Four sections in tabs:
 *    1. Today    — today's workout blueprint + supplements + injury protocols
 *    2. Weekly   — full 7-day rotation
 *    3. Rehab    — finger plantar plate + shoulder protocols (always-on)
 *    4. Education — ~30 cards across 8 topics (shoulder/fingers/jumps/knees/
 *                   recovery/supplements/technique/longevity)
 *
 *  Two entry paths:
 *    - /volleyball                        → "Today" tab
 *    - /volleyball?from=alert             → "Today" + back-to-alerts link
 *    - /volleyball?topic=supplements      → "Education" tab pre-filtered
 *      (the magnesium push uses this so tapping it opens the supplements topic)
 *
 *  Data sources:
 *    GET /vb/today      → today's session + supplements + rehab
 *    GET /vb/weekly     → 7-day plan
 *    GET /vb/education  → full card bank by topic
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { usePageContext } from '../hooks/usePageContext';

type Exercise = string;
type Block = { label: string; exercises: Exercise[] };
type Session = {
  name: string;
  focus: string;
  duration_min: number;
  tags: string[];
  blocks: Block[];
};
type Supplement = { name: string; time: string; with: string; why: string };
type RehabVideo = { id: string; title: string; channel: string; note: string };
type Rehab = {
  issue: string;
  always: string[];
  weekly: string[];
  see_doc: string;
  /** Optional curated YouTube videos for this protocol — backend
   *  populates plan.py REHAB_PROTOCOLS[].videos; render as thumbnail
   *  cards under the protocol so the user has visual instructions
   *  inline (no need to leave the page to search). */
  videos?: RehabVideo[];
};
type EducationCard = { id: string; topic: string; title: string; body: string; source?: string };

type TodayResp = {
  weekday: number;
  session: Session;
  supplements: Supplement[];
  rehab: Rehab[];
  date_et: string;
};
type WeeklyResp = { days: (Session & { weekday: number })[]; supplements: Supplement[]; rehab: Rehab[] };
type EducationResp = { by_topic: Record<string, EducationCard[]>; total_count: number; today_card: EducationCard };

type Video = {
  id: string;
  title: string;
  channel: string;
  year: number;
  category: string;
  duration: string;
  relevance: string;
  url: string;
  thumbnail_url: string;
};
type VideoCategoryMeta = { label: string; emoji: string; tone: string };
type VideosResp = {
  by_category:   Record<string, Video[]>;
  category_meta: Record<string, VideoCategoryMeta>;
  total_count:   number;
};

type Tab = 'today' | 'weekly' | 'rehab' | 'workouts' | 'education';

const TOPIC_META: Record<string, { label: string; emoji: string; tone: string }> = {
  shoulder:    { label: 'Shoulder',     emoji: '🩹', tone: '#10b981' },
  foot:        { label: 'Foot · 2nd MTP', emoji: '🦶', tone: '#f59e0b' },
  jumps:       { label: 'Jumps',        emoji: '🏐', tone: '#3b82f6' },
  knees:       { label: 'Knees',        emoji: '🦵', tone: '#8b5cf6' },
  recovery:    { label: 'Recovery',     emoji: '💤', tone: '#06b6d4' },
  supplements: { label: 'Supplements',  emoji: '💊', tone: '#22c55e' },
  technique:   { label: 'Technique',    emoji: '🏐', tone: '#d4af37' },
  longevity:   { label: 'Longevity',    emoji: '🌳', tone: '#ec4899' },
};

const TOPIC_ORDER = ['shoulder', 'foot', 'jumps', 'knees', 'recovery', 'supplements', 'technique', 'longevity'];

// Session-scoped cache so tab-switching doesn't re-fetch.
let _todayCache: TodayResp | null = null;
let _weeklyCache: WeeklyResp | null = null;
let _eduCache: EducationResp | null = null;
let _videosCache: VideosResp | null = null;


export default function VolleyballPage() {
  const [params, setParams] = useSearchParams();
  const { setPageContext } = usePageContext();

  const fromAlert = params.get('from') === 'alert';
  const initialTopic = params.get('topic');

  // If the URL has ?topic=, jump straight to Education with that topic
  // active. Otherwise default to Today (the most-asked-for view).
  const [tab, setTab] = useState<Tab>(initialTopic ? 'education' : 'today');

  // Data state
  const [today, setToday]   = useState<TodayResp | null>(_todayCache);
  const [weekly, setWeekly] = useState<WeeklyResp | null>(_weeklyCache);
  const [edu, setEdu]       = useState<EducationResp | null>(_eduCache);
  const [videos, setVideos] = useState<VideosResp | null>(_videosCache);
  const [err, setErr]       = useState<string | null>(null);

  // Active education topic — bound to ?topic=. If absent, default to
  // 'shoulder' (the user's primary issue).
  const activeTopic = useMemo(() => {
    if (initialTopic && TOPIC_META[initialTopic]) return initialTopic;
    return 'shoulder';
  }, [initialTopic]);

  // Fetch on mount — four endpoints in parallel.
  useEffect(() => {
    let alive = true;
    const fetchAll = async () => {
      try {
        const [tRes, wRes, eRes, vRes] = await Promise.all([
          _todayCache   ? Promise.resolve(_todayCache)   : fetch(`${API}/vb/today`).then(r => r.json()),
          _weeklyCache  ? Promise.resolve(_weeklyCache)  : fetch(`${API}/vb/weekly`).then(r => r.json()),
          _eduCache     ? Promise.resolve(_eduCache)     : fetch(`${API}/vb/education`).then(r => r.json()),
          _videosCache  ? Promise.resolve(_videosCache)  : fetch(`${API}/vb/videos`).then(r => r.json()),
        ]);
        if (!alive) return;
        _todayCache = tRes;  _weeklyCache = wRes;  _eduCache = eRes;  _videosCache = vRes;
        setToday(tRes); setWeekly(wRes); setEdu(eRes); setVideos(vRes);
      } catch (e: any) {
        if (alive) setErr(String(e?.message || e));
      }
    };
    fetchAll();
    return () => { alive = false; };
  }, []);

  // Page context for ChatWidget — lets Claude know they're on the
  // volleyball page, which session is today, and which topic if any.
  useEffect(() => {
    setPageContext({
      page: 'volleyball',
      tab,
      session_today:   today?.session.name,
      active_topic:    tab === 'education' ? activeTopic : null,
      arrived_from:    fromAlert ? 'push_notification' : 'menu',
    });
    return () => setPageContext(null);
  }, [tab, today, activeTopic, fromAlert, setPageContext]);

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 920, margin: '0 auto' }}>
      {fromAlert && (
        <div style={{ marginBottom: '0.6rem', fontSize: '0.78rem' }}>
          <Link to="/notifications"
                style={{
                  display: 'inline-block', padding: '4px 10px',
                  background: 'rgba(212,175,55,0.08)',
                  border: '1px solid rgba(212,175,55,0.25)',
                  borderRadius: 4, color: '#d4af37',
                  textDecoration: 'none', fontFamily: 'inherit',
                }}>
            ← Back to alerts
          </Link>
          <span style={{ marginLeft: 8, color: '#6a6a72', fontSize: '0.72rem' }}>
            From a push notification. Full message kept in notification history.
          </span>
        </div>
      )}

      <header className="cm-pagehead" style={{ marginBottom: '0.9rem' }}>
        <div className="cm-pagehead__col">
          <div className="eyebrow">Volleyball · personal fitness</div>
          <h1 className="display cm-pagehead__title" style={{ margin: '0.2rem 0 0' }}>
            Volleyball
          </h1>
          <p className="lede">
            Daily workout plan tuned to right-shoulder rehab + right-finger plantar
            plate + supplement stack. Bands warmup, knee braces during plyos, Viktry
            insoles in every shoe. Pushes at 7 AM, 6 PM, 9:30 PM ET.
          </p>
        </div>
      </header>

      {/* Tab strip */}
      <div role="tablist" style={{
        display: 'flex', gap: '0.4rem', flexWrap: 'wrap',
        marginBottom: '1rem',
      }}>
        {(['today', 'weekly', 'rehab', 'workouts', 'education'] as Tab[]).map((t) => {
          const active = t === tab;
          const label = t === 'today' ? '📅 Today'
                      : t === 'weekly' ? '🗓️ Weekly plan'
                      : t === 'rehab' ? '🩹 Rehab protocols'
                      : t === 'workouts' ? '🎥 Workouts'
                      : '📖 Education';
          return (
            <button
              key={t}
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t)}
              style={{
                padding: '0.45rem 0.85rem',
                background: active ? 'rgba(212,175,55,0.14)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? 'rgba(212,175,55,0.42)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 999,
                color: active ? '#f3e8c8' : '#cfcfd4',
                fontFamily: 'inherit',
                fontWeight: active ? 700 : 500,
                fontSize: '0.84rem',
                cursor: 'pointer',
              }}
            >{label}</button>
          );
        })}
      </div>

      {err && (
        <div style={{
          padding: '0.5rem 0.7rem',
          background: 'rgba(239,68,68,0.06)',
          border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 4, color: '#fca5a5',
          fontSize: '0.78rem', marginBottom: '0.6rem',
        }}>{err}</div>
      )}

      {tab === 'today' && <TodayTab today={today} />}
      {tab === 'weekly' && <WeeklyTab weekly={weekly} />}
      {tab === 'rehab' && <RehabTab rehab={today?.rehab || []} />}
      {tab === 'workouts' && <WorkoutsTab videos={videos} />}
      {tab === 'education' && (
        <EducationTab
          edu={edu}
          activeTopic={activeTopic}
          onPick={(t) => {
            const next = new URLSearchParams(params);
            next.set('topic', t);
            setParams(next, { replace: true });
          }}
        />
      )}
    </div>
  );
}


function TodayTab({ today }: { today: TodayResp | null }) {
  if (!today) return <div style={{ color: '#9a9aa3' }}>loading…</div>;
  const s = today.session;
  return (
    <>
      <section style={{
        padding: '0.8rem 1rem',
        background: 'rgba(20,20,22,0.55)',
        border: '1px solid rgba(212,175,55,0.25)',
        borderLeft: '3px solid #d4af37',
        borderRadius: 8,
        marginBottom: '0.8rem',
      }}>
        <div className="eyebrow" style={{
          color: '#d4af37', letterSpacing: '0.08em',
          fontSize: '0.62rem', fontWeight: 700,
        }}>{today.date_et}</div>
        <h2 style={{ margin: '0.1rem 0 0.3rem', fontSize: '1.15rem',
                      fontFamily: '"Times New Roman", Georgia, serif',
                      fontStyle: 'italic' }}>{s.name}</h2>
        <div style={{ fontSize: '0.85rem', color: '#cfcfd4', lineHeight: 1.5 }}>{s.focus}</div>
        <div style={{ marginTop: 5, fontSize: '0.72rem', color: '#9a9aa3' }}>
          ⏱ {s.duration_min} min · {s.tags.join(' · ')}
        </div>
      </section>

      {/* Workout blocks */}
      {s.blocks.map((b, i) => (
        <section key={i} style={{
          padding: '0.7rem 0.9rem',
          background: 'rgba(20,20,22,0.5)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 6,
          marginBottom: '0.5rem',
        }}>
          <div style={{
            fontSize: '0.66rem', color: '#d4af37',
            letterSpacing: '0.08em', textTransform: 'uppercase',
            fontWeight: 700, marginBottom: 6,
          }}>{b.label}</div>
          <ul style={{ margin: 0, padding: '0 0 0 1.1rem',
                        fontSize: '0.82rem', lineHeight: 1.55,
                        color: '#cfcfd4' }}>
            {b.exercises.map((e, j) => <li key={j}>{e}</li>)}
          </ul>
        </section>
      ))}

      {/* Supplement schedule */}
      <section style={{ marginTop: '1rem' }}>
        <div className="eyebrow" style={{ marginBottom: '0.4rem' }}>💊 Supplement schedule</div>
        {today.supplements.map((s, i) => (
          <div key={i} style={{
            padding: '0.5rem 0.7rem',
            background: 'rgba(34,197,94,0.05)',
            border: '1px solid rgba(34,197,94,0.2)',
            borderLeft: '2px solid #22c55e',
            borderRadius: 4, marginBottom: '0.3rem',
          }}>
            <div style={{ fontSize: '0.86rem', fontWeight: 700 }}>
              {s.name} <span style={{ color: '#22c55e', fontSize: '0.74rem', fontWeight: 500 }}>· {s.time}</span>
            </div>
            <div style={{ fontSize: '0.74rem', color: '#cfcfd4', marginTop: 2 }}>
              with: {s.with}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#9a9aa3', marginTop: 2, lineHeight: 1.45 }}>
              {s.why}
            </div>
          </div>
        ))}
      </section>

      {/* Rehab protocols always visible on Today */}
      <section style={{ marginTop: '1rem' }}>
        <div className="eyebrow" style={{ marginBottom: '0.4rem' }}>🩹 Daily rehab — always-on</div>
        {today.rehab.map((r, i) => (
          <RehabCard key={i} rehab={r} compact />
        ))}
      </section>
    </>
  );
}


function WeeklyTab({ weekly }: { weekly: WeeklyResp | null }) {
  if (!weekly) return <div style={{ color: '#9a9aa3' }}>loading…</div>;
  return (
    <>
      {weekly.days.map((d) => (
        <section key={d.weekday} style={{
          padding: '0.7rem 0.9rem',
          background: 'rgba(20,20,22,0.5)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 6,
          marginBottom: '0.5rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontSize: '0.95rem', fontWeight: 700 }}>{d.name}</div>
            <div style={{ fontSize: '0.7rem', color: '#9a9aa3' }}>⏱ {d.duration_min} min</div>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#cfcfd4', marginTop: 3, lineHeight: 1.5 }}>{d.focus}</div>
          <div style={{ marginTop: 4, fontSize: '0.66rem', color: '#9a9aa3', letterSpacing: '0.04em' }}>
            {d.tags.join(' · ')}
          </div>
        </section>
      ))}
    </>
  );
}


function RehabTab({ rehab }: { rehab: Rehab[] }) {
  if (!rehab.length) return <div style={{ color: '#9a9aa3' }}>loading…</div>;
  return (
    <>
      <div style={{ fontSize: '0.78rem', color: '#9a9aa3', marginBottom: '0.7rem', lineHeight: 1.5 }}>
        Protocols to run daily / weekly for the right index finger plantar plate
        and right shoulder. Not medical advice — coordinate with your PT for the
        specifics.
      </div>
      {rehab.map((r, i) => <RehabCard key={i} rehab={r} />)}
    </>
  );
}


function RehabCard({ rehab, compact }: { rehab: Rehab; compact?: boolean }) {
  return (
    <section style={{
      padding: '0.7rem 0.9rem',
      background: 'rgba(239,68,68,0.04)',
      border: '1px solid rgba(239,68,68,0.18)',
      borderLeft: '3px solid #ef4444',
      borderRadius: 6,
      marginBottom: '0.5rem',
    }}>
      <div style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: 5 }}>
        {rehab.issue}
      </div>
      <div className="eyebrow" style={{ color: '#ef4444', fontSize: '0.62rem', marginTop: 6 }}>
        Always
      </div>
      <ul style={{ margin: '2px 0 0', padding: '0 0 0 1rem', fontSize: '0.78rem',
                    lineHeight: 1.55, color: '#cfcfd4' }}>
        {rehab.always.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
      {!compact && (
        <>
          <div className="eyebrow" style={{ color: '#ef4444', fontSize: '0.62rem', marginTop: 8 }}>
            Weekly
          </div>
          <ul style={{ margin: '2px 0 0', padding: '0 0 0 1rem', fontSize: '0.78rem',
                        lineHeight: 1.55, color: '#cfcfd4' }}>
            {rehab.weekly.map((x, i) => <li key={i}>{x}</li>)}
          </ul>

          {/* Inline video instructions — backend plan.py REHAB_PROTOCOLS
              populates the videos field; we render YouTube thumbnails +
              a relevance note per video. Clicking opens YouTube in a
              new tab (no embedded iframes so we don't auto-play with
              sound). */}
          {rehab.videos && rehab.videos.length > 0 && (
            <>
              <div className="eyebrow" style={{
                color: '#f59e0b', fontSize: '0.62rem', marginTop: 10,
              }}>
                🎥 Video instructions
              </div>
              <div style={{ marginTop: 4 }}>
                {rehab.videos.map((v, i) => (
                  <a
                    key={i}
                    href={`https://youtu.be/${v.id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '120px minmax(0, 1fr)',
                      gap: '0.6rem',
                      padding: '0.45rem 0.55rem',
                      background: 'rgba(20,20,22,0.5)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      borderRadius: 4,
                      marginBottom: '0.4rem',
                      textDecoration: 'none',
                      color: 'inherit',
                    }}
                  >
                    <img
                      src={`https://img.youtube.com/vi/${v.id}/hqdefault.jpg`}
                      alt={v.title}
                      loading="lazy"
                      style={{
                        width: '100%', aspectRatio: '16 / 9',
                        objectFit: 'cover', borderRadius: 3,
                        display: 'block',
                      }}
                    />
                    <div style={{ minWidth: 0 }}>
                      <div style={{
                        fontWeight: 700, fontSize: '0.82rem',
                        lineHeight: 1.3, marginBottom: 2,
                      }}>
                        {v.title}
                      </div>
                      <div style={{
                        fontSize: '0.66rem', color: '#9a9aa3', marginBottom: 4,
                      }}>
                        {v.channel} · ▶ YouTube
                      </div>
                      <div style={{
                        fontSize: '0.74rem', color: '#cfcfd4', lineHeight: 1.45,
                      }}>
                        {v.note}
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </>
          )}

          <div style={{ fontSize: '0.7rem', color: '#9a9aa3', marginTop: 6, lineHeight: 1.5,
                        fontStyle: 'italic' }}>
            ⓘ When to see a doctor: {rehab.see_doc}
          </div>
        </>
      )}
    </section>
  );
}


function WorkoutsTab({ videos }: { videos: VideosResp | null }) {
  // Hand-curated leg-workout videos from YouTube. Categories: plyometrics,
  // strength, single_leg, etc. Each card renders the YouTube thumbnail
  // (free, no API key needed) + title + channel + relevance note. Tapping
  // a card opens YouTube in a new tab — embedded iframes would auto-play
  // with sound which is rude when the user just wanted to browse.
  const [activeCat, setActiveCat] = useState<string>('plyometrics');

  if (!videos) return <div style={{ color: '#9a9aa3' }}>loading videos…</div>;

  const cats = Object.keys(videos.by_category);
  // Fall back to first available category if 'plyometrics' isn't present
  // (defensive — the curated list might not have every category populated).
  const cat = videos.by_category[activeCat] ? activeCat : (cats[0] || 'plyometrics');
  const list = videos.by_category[cat] || [];
  const meta = videos.category_meta[cat];

  return (
    <>
      <div style={{
        fontSize: '0.78rem', color: '#9a9aa3', marginBottom: '0.7rem', lineHeight: 1.5,
      }}>
        Curated YouTube videos for leg + jump training. Vetted for relevance
        to your profile — knee braces, single-leg work, supplement-friendly
        cadence. Tap a card to open on YouTube. Older videos in the list are
        still solid; mechanics don't age.
      </div>

      {/* Category tab strip */}
      <div role="tablist" style={{
        display: 'flex', gap: '0.3rem', flexWrap: 'wrap',
        marginBottom: '0.7rem',
      }}>
        {cats.map((c) => {
          const cmeta = videos.category_meta[c];
          const active = c === cat;
          return (
            <button
              key={c}
              role="tab"
              aria-selected={active}
              onClick={() => setActiveCat(c)}
              style={{
                padding: '0.4rem 0.7rem',
                background: active ? `${cmeta.tone}22` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? cmeta.tone : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 5,
                color: active ? cmeta.tone : '#cfcfd4',
                fontFamily: 'inherit',
                fontWeight: active ? 700 : 500,
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >{cmeta.emoji} {cmeta.label} <span style={{
              opacity: 0.6, fontSize: '0.86em', marginLeft: 4,
            }}>{videos.by_category[c]?.length || 0}</span></button>
          );
        })}
      </div>

      {/* Active category's videos — vertical list with thumbnails */}
      {list.map((v) => (
        <a
          key={v.id}
          href={v.url}
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'grid',
            gridTemplateColumns: '140px minmax(0, 1fr)',
            gap: '0.7rem',
            padding: '0.55rem 0.7rem',
            background: 'rgba(20,20,22,0.55)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderLeft: `3px solid ${meta?.tone || '#cfcfd4'}`,
            borderRadius: 6,
            marginBottom: '0.5rem',
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          {/* YouTube thumbnail — hqdefault is universally available for
              every published video (vs maxresdefault which may 404). */}
          <img
            src={v.thumbnail_url}
            alt={v.title}
            loading="lazy"
            style={{
              width: '100%', height: 'auto',
              borderRadius: 4,
              aspectRatio: '16 / 9',
              objectFit: 'cover',
              display: 'block',
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontWeight: 700, fontSize: '0.88rem',
              lineHeight: 1.3, marginBottom: 3,
            }}>
              {v.title}
            </div>
            <div style={{
              fontSize: '0.7rem', color: '#9a9aa3', marginBottom: 5,
            }}>
              {v.channel} · {v.year} · {v.duration} · ▶ YouTube
            </div>
            <div style={{
              fontSize: '0.78rem', color: '#cfcfd4',
              lineHeight: 1.5,
            }}>
              {v.relevance}
            </div>
          </div>
        </a>
      ))}

      {list.length === 0 && (
        <div style={{ color: '#9a9aa3', fontSize: '0.82rem' }}>
          No videos in this category yet.
        </div>
      )}

      <div style={{
        marginTop: '0.7rem', padding: '0.5rem 0.7rem',
        background: 'rgba(255,255,255,0.02)',
        border: '1px dashed rgba(255,255,255,0.08)',
        borderRadius: 4,
        fontSize: '0.7rem', color: '#9a9aa3', lineHeight: 1.5,
      }}>
        Want more or different videos? Edit{' '}
        <code style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.92em' }}>
          backend/volleyball/videos.py
        </code>{' '}
        — just paste a YouTube ID + title + category and the UI auto-renders.
      </div>
    </>
  );
}


function EducationTab({ edu, activeTopic, onPick }: {
  edu: EducationResp | null; activeTopic: string; onPick: (t: string) => void;
}) {
  if (!edu) return <div style={{ color: '#9a9aa3' }}>loading…</div>;
  const cards = edu.by_topic[activeTopic] || [];
  const meta = TOPIC_META[activeTopic];
  return (
    <>
      <div role="tablist" style={{
        display: 'flex', gap: '0.3rem', flexWrap: 'wrap',
        marginBottom: '0.7rem',
      }}>
        {TOPIC_ORDER.map((t) => {
          const tmeta = TOPIC_META[t];
          const active = t === activeTopic;
          return (
            <button
              key={t}
              role="tab"
              aria-selected={active}
              onClick={() => onPick(t)}
              style={{
                padding: '0.4rem 0.7rem',
                background: active ? `${tmeta.tone}22` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? tmeta.tone : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 5,
                color: active ? tmeta.tone : '#cfcfd4',
                fontFamily: 'inherit',
                fontWeight: active ? 700 : 500,
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >{tmeta.emoji} {tmeta.label}</button>
          );
        })}
      </div>
      {cards.map((c) => (
        <article key={c.id} style={{
          padding: '0.65rem 0.85rem',
          background: 'rgba(20,20,22,0.55)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderLeft: `3px solid ${meta?.tone || '#cfcfd4'}`,
          borderRadius: 6,
          marginBottom: '0.5rem',
        }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: 4, lineHeight: 1.3 }}>
            {c.title}
          </div>
          <div style={{ fontSize: '0.82rem', color: '#cfcfd4', lineHeight: 1.55 }}>
            {c.body}
          </div>
          {c.source && (
            <div style={{ marginTop: 5, fontSize: '0.7rem', color: '#6a6a72' }}>
              — {c.source}
            </div>
          )}
        </article>
      ))}
    </>
  );
}
