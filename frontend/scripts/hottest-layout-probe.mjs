#!/usr/bin/env node
/* 🔥 Hottest — the real-browser check that no column is cut (2026-09-28).
 *
 * Ajay 2026-09-28: "Can you fix the horizontal columns hiding". jsdom loads no
 * CSS and lays nothing out, so no Vitest can prove the fix. This script can:
 * it renders a snapshot of the REAL component (written by
 * HottestSectors.layout.test.tsx or the real-payload test under
 * HS_LAYOUT_SNAPSHOT=<file>) with ALL of the app's stylesheets, in the order
 * main.tsx imports them, inside the same `.app > main.main > .cm-page` chain
 * the page uses, in headless Chrome at 1440 / 1280 / 1024 / 768 / 390 px.
 *
 * Each width is a same-origin `srcdoc` iframe — a true viewport, media
 * queries included (headless Chrome's own window floor is 500px, so 390 needs
 * the iframe). For each width it asserts:
 *   - scrolled fully right, the LAST header's right edge is inside the scroll
 *     box and inside the viewport — every column is reachable;
 *   - the page itself is not wider than the viewport (nothing cut by html's
 *     overflow-x: hidden);
 *   - the first Sector / Name cell holds at the box's left edge while scrolled
 *     (sticky);
 *   - the scroll wrapper is no wider than its `.hs` parent's content box;
 *   - every full-width row's pinned text stays inside the visible box, both
 *     unscrolled (starting at its cell's content edge) and fully scrolled.
 * `--hs-box-w` is written on the box here exactly as useHScrollCue writes it
 * in the app (the snapshot carries jsdom's 0px).
 *
 * Usage: node scripts/hottest-layout-probe.mjs <snapshot.html>
 * Prints a table; exits 1 on any failure. CHROME=<path> overrides the binary;
 * HS_PROBE_EXTRA_CSS='<rules>' appends CSS after the app's (mutation checks).
 * WebKit is NOT checked — there is no WebKit engine on this Mac. */
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WIDTHS = [1440, 1280, 1024, 768, 390];
const CHROME = process.env.CHROME
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const snapPath = process.argv[2];
if (!snapPath) {
  console.error('usage: node scripts/hottest-layout-probe.mjs <snapshot.html>');
  process.exit(2);
}
const snapshot = readFileSync(snapPath, 'utf8');

/* The app's stylesheets, in main.tsx's import order — parsed, not listed, so a
 * sheet added to main.tsx is probed without editing this file. */
const main = readFileSync(join(ROOT, 'src/main.tsx'), 'utf8');
const sheets = [...main.matchAll(/^import\s+'(\.\/[^']+\.css)';/gm)].map((m) => m[1]);
if (!sheets.length) {
  console.error('no stylesheet imports found in src/main.tsx');
  process.exit(2);
}
const css = sheets.map((s) => `/* ${s} */\n${readFileSync(join(ROOT, 'src', s), 'utf8')}`).join('\n');
/* HS_PROBE_EXTRA_CSS appends rules AFTER the app's sheets — the mutation
 * check: undo the fix here and every narrow width must FAIL. */
const extra = process.env.HS_PROBE_EXTRA_CSS || '';

const child = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>${css}\n${extra}</style></head><body>
<div class="app"><main class="main"><div class="cm-page">${snapshot}</div></main></div>
</body></html>`;
const attr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;');

/* Runs inside the PARENT page, once per iframe load. */
function probe(frame, width) {
  const out = { width, ok: true, fails: [] };
  const fail = (m) => { out.ok = false; out.fails.push(m); };
  try {
    const doc = frame.contentDocument;
    const win = frame.contentWindow;
    const sc = doc.querySelector('.hs-scroll');
    const wrap = doc.querySelector('.hs-scrollwrap');
    const hs = wrap && wrap.parentElement;
    if (!sc || !wrap || !hs) { fail('missing .hs > .hs-scrollwrap > .hs-scroll'); return out; }
    sc.style.setProperty('--hs-box-w', `${sc.clientWidth}px`);
    void sc.offsetWidth;
    const R = (e) => e.getBoundingClientRect();
    const scR = R(sc);
    const visL = scR.left + sc.clientLeft;
    const visR = visL + sc.clientWidth;
    const hsCs = win.getComputedStyle(hs);
    const hsContent = hs.clientWidth - parseFloat(hsCs.paddingLeft) - parseFloat(hsCs.paddingRight);
    out.box = sc.clientWidth;
    out.content = sc.scrollWidth;
    out.scrolls = sc.scrollWidth > sc.clientWidth + 1;
    out.wrap = Math.round(R(wrap).width);
    out.hsContent = Math.round(hsContent);
    if (R(wrap).width > hsContent + 1) fail(`wrapper ${Math.round(R(wrap).width)} wider than .hs content ${Math.round(hsContent)}`);
    const pageW = doc.documentElement.scrollWidth;
    out.page = pageW;
    if (pageW > win.innerWidth) fail(`page ${pageW} wider than viewport ${win.innerWidth} — html would cut it`);
    const pins = [...doc.querySelectorAll('.hs-rowpin')];
    out.pins = pins.length;
    for (const p of pins) {
      const td = p.closest('td');
      const tcs = win.getComputedStyle(td);
      const tdContentL = R(td).left + parseFloat(tcs.borderLeftWidth) + parseFloat(tcs.paddingLeft);
      const r = R(p);
      if (Math.abs(r.left - tdContentL) > 1) fail(`pin "${p.textContent.trim().slice(0, 24)}" starts at ${Math.round(r.left)}, cell content at ${Math.round(tdContentL)} (unscrolled)`);
      if (r.right > visR + 1) fail(`pin "${p.textContent.trim().slice(0, 24)}" ends at ${Math.round(r.right)} past box ${Math.round(visR)} (unscrolled)`);
    }
    sc.scrollLeft = sc.scrollWidth;
    void sc.offsetWidth;
    const ths = [...doc.querySelectorAll('thead th')];
    const last = ths[ths.length - 1];
    out.cols = ths.length;
    out.lastHeader = (last.textContent || '').trim();
    const lr = R(last);
    out.reachable = lr.right <= visR + 1 && lr.right <= win.innerWidth + 1;
    if (!out.reachable) fail(`last header "${out.lastHeader}" ends at ${Math.round(lr.right)}, box ${Math.round(visR)}, viewport ${win.innerWidth}`);
    const sym = doc.querySelector('tbody td.hs-sym');
    out.stickyDx = sym ? Math.round(R(sym).left - visL) : null;
    if (!sym || Math.abs(R(sym).left - visL) > 1) fail(`Sector / Name cell left ${sym ? Math.round(R(sym).left) : '—'} vs box left ${Math.round(visL)} when scrolled`);
    for (const p of pins) {
      const r = R(p);
      if (r.right > visR + 1) fail(`pin "${p.textContent.trim().slice(0, 24)}" ends at ${Math.round(r.right)} past box ${Math.round(visR)} (scrolled)`);
      if (r.left < visL - 1) fail(`pin "${p.textContent.trim().slice(0, 24)}" starts at ${Math.round(r.left)} left of box ${Math.round(visL)} (scrolled)`);
    }
  } catch (e) {
    fail(`probe threw: ${e && e.message}`);
  }
  return out;
}

const frames = WIDTHS.map((w) => `<iframe width="${w}" height="900" style="border:0;display:block"
  srcdoc="${attr(child)}" onload="window.__done(this, ${w})"></iframe>`).join('\n');
const parent = `<!doctype html><html><head><meta charset="utf-8"><script>
${probe.toString()}
window.__res = [];
window.__done = (f, w) => {
  window.__res.push(probe(f, w));
  document.getElementById('out').textContent = JSON.stringify(window.__res);
};
</script></head><body><pre id="out">[]</pre>
${frames}
</body></html>`;

const dir = mkdtempSync(join(tmpdir(), 'hs-probe-'));
const page = join(dir, 'probe.html');
writeFileSync(page, parent, 'utf8');
let dom;
try {
  dom = execFileSync(CHROME, [
    '--headless=new', '--disable-gpu', '--hide-scrollbars=false',
    '--window-size=1600,1000', '--virtual-time-budget=5000',
    '--dump-dom', `file://${page}`,
  ], { encoding: 'utf8', timeout: 120000, maxBuffer: 256 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
} catch (e) {
  console.error(`headless Chrome failed: ${e.message}`);
  process.exit(2);
}
const m = /<pre id="out">([\s\S]*?)<\/pre>/.exec(dom);
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
const res = m ? JSON.parse(unesc(m[1])) : [];
res.sort((a, b) => WIDTHS.indexOf(a.width) - WIDTHS.indexOf(b.width));

console.log(`stylesheets (main.tsx order): ${sheets.join(', ')}`);
console.log('| viewport | box / content | scrolls | wrap ≤ .hs | page | last header reachable | sticky Δpx | pins | result |');
console.log('|---|---|---|---|---|---|---|---|---|');
for (const r of res) {
  console.log(`| ${r.width} | ${r.box} / ${r.content} | ${r.scrolls ? 'yes' : 'no'} | ${r.wrap} ≤ ${r.hsContent} | ${r.page} | ${r.reachable ? 'yes' : 'NO'} (${r.lastHeader}) | ${r.stickyDx} | ${r.pins} | ${r.ok ? 'PASS' : 'FAIL'} |`);
  for (const f of r.fails || []) console.log(`    ✗ ${f}`);
}
const missing = WIDTHS.filter((w) => !res.some((r) => r.width === w));
if (missing.length) console.log(`    ✗ no result for ${missing.join(', ')} px`);
const bad = res.filter((r) => !r.ok).length + missing.length;
if (bad) { console.error(`\n${bad} width(s) FAILED`); process.exit(1); }
console.log(`\nall ${res.length} widths passed`);
