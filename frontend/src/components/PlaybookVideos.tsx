/* 📚 Playbook learning / 🎬 Videos — the playbook film in the app (2026-11-27, playbookvid spec §3.6, WP fe-core).
 *
 * Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook
 * learning and also add it to the playbook tab too with videos".
 *
 * ONE component, two mounts (spec §3.7):
 *   - 🎬 Replays: <PlaybookVideos where="replays" /> — the board mounts it only after its own GET answered the owner, as
 *     the first child of all three returns (a stable child position, so this section stays mounted across session picks
 *     and 🏆 chip jumps). Closed by default; ONE GET each time it opens (`?playbook=1`); nothing while closed.
 *   - 🚩 📓 Playbook: <PlaybookVideosOwner where="playbook" /> — gated on /auth/me `is_primary_admin`; open by default;
 *     ONE GET on mount; renders nothing at all until at least one video is listed.
 *
 * Rows are text (served chapter number, title, subtitle, chips); ▶ mounts ONE video in the whole section, under the
 * tapped row. Never autoplay, never .play — the app never presses play. The size (📱 phone / 🖥 desktop) is STATE,
 * latched from the house phone breakpoint on the first render; after that only a tap on the switch changes it (turning
 * the phone never swaps the playing file). A switch keeps the position (restored on loadedmetadata, paused). No links
 * on this section (the 📓 sub pins every anchor as external). FE-typed: the two titles, PBV_FETCH_FAILED, the ▶ glyph and
 * three aria-labels; every other word is served. A study film: hand-picked teaching charts, UNMEASURED, not a signal. */
import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject, type SyntheticEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { useIsMobile } from '../lib/useIsMobile';
import { useCurrentUser } from '../hooks/useUser';
import {
  PBV_FETCH_FAILED, PBV_PATH, PBV_WHERE, pbvDefaultVariant, pbvFilms, pbvMarkers, pbvOpen, pbvOptions, pbvPick,
  pbvRowKey, pbvSrc, pbvText, pbvToggleParams, pbvVariants,
  type PbvChapter, type PbvFilm, type PbvFull, type PbvPayload, type PbvVariant, type PbvWhere,
} from '../lib/playbookVideos';
import '../styles/playbookVideos.css';

type Load = { phase: 'idle' } | { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: PbvPayload };

const STATES = new Set(['no_folder', 'empty', 'ready']);
const GONE = Symbol('gone');

function Line({ text, className, testId }: { text: unknown; className: string; testId?: string }) {
  const t = pbvText(text);
  return t ? <p className={className} data-testid={testId}>{t}</p> : null;
}

/* The chips of the variant that WILL play: its served length, quality and size. */
function Chips({ v }: { v: PbvVariant | null }) {
  const chips = v ? [v.length_text, v.quality_text, v.size_text].map(pbvText).filter((s) => s.length > 0) : [];
  if (!chips.length) return null;
  return (
    <span className="pbv-chips">
      {chips.map((c, i) => <span key={`c${i}-${c}`} className="pbv-chip">{c}</span>)}
    </span>
  );
}

function Row({ slug, row, isFull, want, playing, onPlay, vref, onMeta }: {
  slug: string; row: PbvChapter | PbvFull; isFull: boolean; want: string; playing: boolean; onPlay: () => void;
  vref: RefObject<HTMLVideoElement>; onMeta: (e: SyntheticEvent<HTMLVideoElement>) => void;
}) {
  const key = pbvText(row.key);
  const pick = pbvPick(row.variants, want);
  const src = pbvSrc(pick);
  const shown = playing && !!src;
  const nn = isFull ? '' : pbvText((row as PbvChapter).nn_text);
  const markers = isFull ? pbvMarkers((row as PbvFull).markers) : [];
  return (
    <div className={isFull ? 'pbv-row pbv-full' : 'pbv-row'} data-testid={`pbv-row-${slug}-${key}`}>
      <div className="pbv-head">
        {nn ? <span className="pbv-nn">{nn}</span> : null}
        <span className="pbv-title">{pbvText(row.title)}</span>
        {pbvText(row.subtitle) ? <span className="pbv-sub">{pbvText(row.subtitle)}</span> : null}
        <Chips v={pick} />
        {src ? (
          <button
            type="button" className="pbv-play" aria-label="play" aria-pressed={playing}
            data-testid={`pbv-play-${slug}-${key}`} onClick={onPlay}
          >▶</button>
        ) : null}
      </div>
      {shown ? (
        <div className="pbv-player">
          <video
            ref={vref} className="pbv-video" data-testid="pbv-video" controls preload="metadata" playsInline src={src}
            onLoadedMetadata={onMeta}
          />
          {markers.length ? (
            <div className="pbv-markers" role="group" aria-label="chapters" data-testid="pbv-markers">
              {markers.map((m, i) => (
                <button
                  key={`m${i}-${m.start_s}`} type="button" className="pbv-marker" data-testid={`pbv-marker-${i}`}
                  onClick={() => { if (vref.current) vref.current.currentTime = m.start_s; }}
                >{m.text}</button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** The section. The caller has proved the owner (🎬: the board's own 200; 📓: PlaybookVideosOwner). */
export function PlaybookVideos({ where }: { where: PbvWhere }) {
  const cfg = PBV_WHERE[where];
  const [params, setParams] = useSearchParams();
  const open = pbvOpen(params, cfg.defaultOpen);
  const [load, setLoad] = useState<Load>({ phase: 'idle' });
  const [gone, setGone] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);
  /* Latched: read once on the first render; a later viewport change never moves it — only a tap on the switch. */
  const isMobile = useIsMobile();
  const [want, setWant] = useState(() => pbvDefaultVariant(isMobile) as string);
  const vref = useRef<HTMLVideoElement>(null);
  const resumeAt = useRef<number | null>(null);

  /* 🎬: ONE GET each time the section opens, nothing while closed. 📓 (quiet): ONE GET on mount. No polling. The effect
   * reads `open` alone — another param changing (date, winners, reel, card, sub) fires no second GET. */
  const wantFetch = cfg.quiet || open;
  useEffect(() => {
    if (gone) return;
    if (!wantFetch) { setLoad({ phase: 'idle' }); return; }
    let alive = true;
    setLoad({ phase: 'loading' });
    fetch(`${API}${PBV_PATH}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => {
        if (r.status === 404) return GONE;
        return r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`));
      })
      .then((j) => {
        if (!alive) return;
        if (j === GONE) { setGone(true); return; }
        const ok = j && typeof j === 'object' && typeof j.state === 'string' && STATES.has(j.state);
        setLoad(ok ? { phase: 'loaded', p: j as PbvPayload } : { phase: 'failed' });
      })
      .catch(() => { if (alive) setLoad({ phase: 'failed' }); });
    return () => { alive = false; };
  }, [wantFetch]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Closing removes the video. */
  useEffect(() => { if (!open) { setPlaying(null); resumeAt.current = null; } }, [open]);

  const ready = load.phase === 'loaded' && load.p.state === 'ready';
  const films: PbvFilm[] = useMemo(() => (ready && load.phase === 'loaded' ? pbvFilms(load.p.films) : []), [ready, load]);
  const options = load.phase === 'loaded' ? pbvOptions(load.p.variant_options) : [];
  const rowVariants = useMemo(() => {
    const m = new Map<string, PbvVariant[]>();
    for (const f of films) {
      for (const c of f.chapters || []) m.set(pbvRowKey(f.slug, c.key), pbvVariants(c.variants));
      if (f.full) m.set(pbvRowKey(f.slug, f.full.key), pbvVariants(f.full.variants));
    }
    return m;
  }, [films]);

  if (gone) return null;
  if (cfg.quiet && !(ready && films.length > 0)) return null;

  const play = (k: string) => { resumeAt.current = null; setPlaying((cur) => (cur === k ? null : k)); };
  /* A tap on the switch: when a video is mounted and its file changes, keep the position (restored on loadedmetadata). */
  const pickSize = (k: string) => {
    if (k === want) return;
    const vs = playing ? rowVariants.get(playing) : undefined;
    const el = vref.current;
    if (el && vs && pbvSrc(pbvPick(vs, want)) !== pbvSrc(pbvPick(vs, k))) resumeAt.current = el.currentTime;
    else resumeAt.current = null;
    setWant(k);
  };
  const onMeta = (e: SyntheticEvent<HTMLVideoElement>) => {
    const t = resumeAt.current;
    if (t == null) return;
    resumeAt.current = null;
    try { e.currentTarget.currentTime = t; } catch { /* not seekable yet */ }
  };

  let body: ReactNode = null;
  if (open && load.phase === 'failed') {
    body = <p className="pbv-line" data-testid="pbv-failed">{PBV_FETCH_FAILED}</p>;
  } else if (open && load.phase === 'loaded' && !ready) {
    body = <Line text={load.p.text} className="pbv-line" testId="pbv-text" />;
  } else if (open && load.phase === 'loaded' && ready) {
    body = (
      <>
        <Line text={load.p.note} className="pbv-line pbv-muted" testId="pbv-note" />
        {options.length >= 2 ? (
          <div className="pbv-variants" role="group" aria-label="video size" data-testid="pbv-variants">
            {options.map((o) => (
              <button
                key={o.key} type="button" className="pbv-vchip" aria-pressed={want === o.key}
                data-testid={`pbv-variant-${o.key}`} onClick={() => pickSize(o.key)}
              >{o.label}</button>
            ))}
          </div>
        ) : null}
        {films.map((f) => {
          const head = [f.title, f.summary_text].map(pbvText).filter((s) => s.length > 0).join(' · ');
          return (
            <div key={f.slug} className="pbv-film" data-testid={`pbv-film-${f.slug}`}>
              {head ? <p className="pbv-film-head">{head}</p> : null}
              <Line text={f.description} className="pbv-line pbv-muted" />
              {(f.chapters || []).map((c, i) => {
                const k = pbvRowKey(f.slug, c.key);
                return (
                  <Row
                    key={`${k}-${i}`} slug={f.slug} row={c} isFull={false} want={want} playing={playing === k}
                    onPlay={() => play(k)} vref={vref} onMeta={onMeta}
                  />
                );
              })}
              {f.full ? (
                <Row
                  slug={f.slug} row={f.full} isFull want={want} playing={playing === pbvRowKey(f.slug, f.full.key)}
                  onPlay={() => play(pbvRowKey(f.slug, (f.full as PbvFull).key))} vref={vref} onMeta={onMeta}
                />
              ) : null}
            </div>
          );
        })}
      </>
    );
  }

  const state = !open ? 'closed' : load.phase === 'loaded' ? pbvText(load.p.state) : load.phase === 'failed' ? 'failed' : 'loading';
  return (
    <section className="pbv-section" data-testid="pbv-section" data-where={where} data-state={state}>
      <button
        type="button" className="pbv-toggle" data-testid="pbv-toggle" aria-expanded={open}
        onClick={() => setParams((prev) => pbvToggleParams(prev, !open, cfg.defaultOpen), { replace: true })}
      >
        {cfg.title}
      </button>
      {body}
    </section>
  );
}

/** The 📓 mount: renders nothing (and fetches nothing) unless /auth/me says the primary owner. */
export function PlaybookVideosOwner({ where }: { where: PbvWhere }) {
  const { user, loading } = useCurrentUser();
  if (loading || !user?.is_primary_admin) return null;
  return <PlaybookVideos where={where} />;
}
