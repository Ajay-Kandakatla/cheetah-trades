# Bypassing bot protection on eBay + B&H

The hourly Playwright scraper at `backend/lifeboard/playwright_scraper.py`
runs three layered bypasses in this order. Each is optional — set up
whichever combination you want; the others are skipped silently.

| Layer | Status without setup | What it gives you |
|---|---|---|
| 1. **eBay Browse API** | off (needs creds in `.env`) | Clean JSON eBay results. Bypasses Akamai entirely (legitimate API). |
| 2. **playwright-stealth** | always on | Defeats most navigator-based fingerprinting. Free, zero-config. Already working. |
| 3. **Cookie injection** | off (needs cookie file) | Scraper runs as YOUR logged-in browser session. Highest fidelity, defeats hardest anti-bot. |
| 4. **B&H Playwright scrape** | always on | Already pulling 11 real 256GB Mac Studios per scan. No setup needed. |

---

## Layer 1 — eBay Browse API (recommended for eBay)

### Setup (5 min, one time)

1. Open https://developer.ebay.com/my/keys (sign in with your normal eBay account if asked)
2. Click **"Create a keyset"** under **Production**. Name it `cheetah-deal-scraper`.
3. Copy the **App ID (Client ID)** and **Cert ID (Client Secret)**.
4. Add to `backend/.env`:
   ```
   EBAY_APP_ID=YourAppId-cheetah-PRD-xxxxxxxx-xxxxxxxx
   EBAY_CERT_ID=PRD-xxxxxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```
5. Restart the api+cron containers:
   ```bash
   cd /Users/ajay/clinet-test/cheetah-market-app
   docker compose up -d --force-recreate api cron
   ```
6. Verify:
   ```bash
   docker compose exec -T cron python -m lifeboard.ebay_api 2>&1 | tail
   # Should print: "ebay api: N candidate items returned" and a JSON dump of deals
   ```

Free tier: 5,000 calls/day. We use ~24/day. No fees, no limits to worry about.

---

## Layer 3 — Cookie injection (works on ANY site you can log in to)

### When to use this

- eBay API setup is too much hassle and you want a quick eBay bypass
- You want B&H prices with your loyalty discount applied
- Any other anti-bot-protected site you have an account on

### Setup (3 min per site)

1. Install the **Cookie-Editor** browser extension:
   - Chrome: https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/
2. Visit `ebay.com` (or `bhphotovideo.com`) and **log in normally**.
3. Click the Cookie-Editor extension icon → **Export → JSON** (copies to clipboard).
4. Pipe the clipboard into the cron container:
   ```bash
   cd /Users/ajay/clinet-test/cheetah-market-app
   pbpaste | docker compose exec -T cron python -m lifeboard.cookies save ebay
   # or:    pbpaste | docker compose exec -T cron python -m lifeboard.cookies save bhphotovideo
   ```
5. Verify they landed:
   ```bash
   docker compose exec cron python -m lifeboard.cookies show ebay
   ```
6. Run a scan to see if the cookies got past the bot edge:
   ```bash
   docker compose exec -T cron python -m lifeboard.playwright_scraper scan 2>&1 | tail -10
   ```

### Caveats

- Cookies expire — eBay's session cookies last ~2 weeks, B&H's last ~1 month. Re-paste when scans start returning "Access Denied" again.
- Treat the cookie file as a credential. It lives at `/root/.cheetah/cookies/{site}_cookies.json` inside the cron container, on the `cheetah-scans` Docker volume. Don't share it.
- Some sites also gate on TLS/IP. Cookies help with session-state checks but not pure IP-reputation gates.

### Clear cookies

```bash
docker compose exec cron python -m lifeboard.cookies clear ebay
```

---

## What's running automatically

- **Hourly cron** at `0 * * * *` runs `python -m lifeboard.playwright_scraper scan`
- Scrapes B&H (always works), eBay (needs API or cookies), persists to `lifeboard_deals` Mongo collection
- Surfaces on `/morning` page → Mac Studio panel
- Push notifies via existing `notify_*` hooks when new deals land

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ebay: BLOCKED by Akamai (Access Denied)` | No API creds + no cookies | Set up Layer 1 or Layer 3 |
| `b&h: 0 candidates extracted` | B&H redesigned their HTML | Re-inspect `[class^="product_"]` selector |
| `mongo unavailable` | Mongo container is down | `docker compose up -d mongo` |
| Cookie file written but still blocked | Cookies expired | Re-export from browser, re-paste |
