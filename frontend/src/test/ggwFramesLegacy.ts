/* 👀 2026-11-27 (spec watch5m rev 2 §3.9, C5) — the one-line legacy seam for the Watch tests written before the 5-min
 * default. Legacy mode = every served frame on the board and in ⤢ (so ggwDenseMode is false: today's tile and the
 * 1 · 2 · 4 · 9 picks), average-volume line on. The readers return the lib's OWN "every served frame" token — no frame
 * list is typed here, so a frame the server adds later is drawn, never filtered. A legacy test file adds as its FIRST
 * line (the bare `vi.mock`, never an alias — an aliased call is not hoisted):
 *   vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
 * Never imported by non-test code; never a global setup (the ggCardWatchOff precedent). */
export async function ggwFramesLegacy(orig: () => Promise<unknown>) {
  const m = (await orig()) as Record<string, unknown>;
  const every = () => [m.GGW_FRAMES_EVERY as string];           // the lib's own token — no frame list typed here
  return { ...m, readGgwFrames: every, readGgwStretchFrames: every, readGgwVolAvg: () => true };
}
