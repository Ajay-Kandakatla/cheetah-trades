/* LukEntryTape — the 🕰️ tape for ONE 🥇 Luk's 🏁 row (2026-11-01, luk spec §3.9 / §3.13).
 *
 * Fetches GET /chart-maps/luk/entry-tape?id=… (LUK_TAPE_PATH — never a 🚩 route) and hands the served payload to
 * <GgEntryTape id data> — the same drawing as 🚩's tape (one engine; a preset payload skips GgEntryTape's own fetch,
 * so no 🚩 route is ever asked). Every word, number and line on it is SERVED; this file types only the glyphs for
 * loading and for a failed read. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { LUK_TAPE_PATH, type LukTapePayload } from '../lib/luk';
import { GgEntryTape } from './GgEntryTape';

export function LukEntryTape({ id }: { id: string }) {
  const [data, setData] = useState<LukTapePayload | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let live = true;
    setData(null); setErr(false);
    fetch(`${API}${LUK_TAPE_PATH}?id=${encodeURIComponent(id)}`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((j) => { if (live) setData(j as LukTapePayload); })
      .catch(() => { if (live) setErr(true); });
    return () => { live = false; };
  }, [id]);
  if (err) return <div className="luk-tape" data-testid="luk-tape"><span className="luk-muted">—</span></div>;
  if (!data) return <div className="luk-tape" data-testid="luk-tape"><span className="luk-muted">…</span></div>;
  return <div className="luk-tape" data-testid="luk-tape"><GgEntryTape id={id} data={data} /></div>;
}

export default LukEntryTape;
