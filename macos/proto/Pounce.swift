// Pounce Web Push prototype — Option 1 capability probe.
//
// Loads the production Pounce URL inside a WKWebView, then runs a
// JavaScript probe that exercises every Web Push API the existing
// frontend depends on (Notification, ServiceWorker, PushManager,
// pushManager.subscribe). Each step is reported back to native via
// WKScriptMessageHandler and written to ~/Desktop/pounce-probe.log
// plus stdout, so you can confirm what works and what fails on this
// macOS / WebKit version.
//
// Build via build-and-run.sh.

import Cocoa
import WebKit

let kProdURL = "https://ajays-macbook-pro.tailb3dc79.ts.net/"

// ---------------------------------------------------------------------------
// Probe log — append to file + echo to stdout. Truncated on each launch so
// the log only contains data from the most recent run.
// ---------------------------------------------------------------------------
final class ProbeLog {
    static let shared = ProbeLog()
    private let url: URL
    private let fmt: ISO8601DateFormatter

    init() {
        let desktop = FileManager.default.urls(for: .desktopDirectory, in: .userDomainMask)[0]
        self.url = desktop.appendingPathComponent("pounce-probe.log")
        self.fmt = ISO8601DateFormatter()
        try? "".write(to: url, atomically: true, encoding: .utf8)
    }

    func write(_ tag: String, _ msg: String) {
        let line = "\(fmt.string(from: Date())) [\(tag)] \(msg)\n"
        print(line, terminator: "")
        if let data = line.data(using: .utf8) {
            if let h = try? FileHandle(forWritingTo: url) {
                h.seekToEndOfFile()
                h.write(data)
                try? h.close()
            } else {
                try? data.write(to: url)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Probe JS — injected into every page. Auto-runs after window 'load' and is
// also exposed as window.__pounceRunProbe() so the native toolbar button can
// kick it off again after Google OAuth completes.
// ---------------------------------------------------------------------------
let probeJS = """
(function () {
  if (window.__pounceProbeInstalled) return;
  window.__pounceProbeInstalled = true;

  const post = (msg) => {
    try { window.webkit.messageHandlers.pounce.postMessage(String(msg)); } catch (e) {}
    try { console.log('[pounce-probe]', msg); } catch (e) {}
  };

  window.__pounceRunProbe = async function () {
    post('--- probe start ---');
    post('href: ' + location.href);
    post('userAgent: ' + navigator.userAgent);
    post('serviceWorker_in_navigator: ' + ('serviceWorker' in navigator));
    post('PushManager_in_window: ' + ('PushManager' in window));
    post('Notification_in_window: ' + ('Notification' in window));
    if (typeof Notification !== 'undefined') {
      post('Notification.permission_initial: ' + Notification.permission);
      try {
        const perm = await Notification.requestPermission();
        post('Notification.requestPermission_result: ' + perm);
      } catch (e) {
        post('Notification.requestPermission_threw: ' + (e && e.message ? e.message : String(e)));
      }
    }

    if (!('serviceWorker' in navigator)) {
      post('ABORT: serviceWorker API not present');
      post('--- probe end ---');
      return;
    }

    let reg = null;
    try {
      reg = await navigator.serviceWorker.register('/sw.js');
      post('sw_registered_scope: ' + reg.scope);
    } catch (e) {
      post('sw_register_failed: ' + (e && e.message ? e.message : String(e)));
      post('--- probe end ---');
      return;
    }

    try { await navigator.serviceWorker.ready; post('sw_ready: yes'); }
    catch (e) { post('sw_ready_failed: ' + (e && e.message ? e.message : String(e))); }

    if (!reg.pushManager) {
      post('ABORT: registration has no pushManager');
      post('--- probe end ---');
      return;
    }
    post('pushManager_present: yes');

    try {
      const existing = await reg.pushManager.getSubscription();
      post('existing_subscription: ' + (existing ? existing.endpoint : 'null'));
    } catch (e) {
      post('getSubscription_threw: ' + (e && e.message ? e.message : String(e)));
    }

    let key = null;
    try {
      const r = await fetch('/push/public-key', { credentials: 'include' });
      post('public_key_status: ' + r.status);
      const j = await r.json();
      key = j.public_key;
      post('public_key_present: ' + (key ? 'yes' : 'no'));
    } catch (e) {
      post('public_key_fetch_failed: ' + (e && e.message ? e.message : String(e)));
    }

    if (!key) {
      post('ABORT: no VAPID key (probably not logged in yet — log in via Google then click "Run Probe")');
      post('--- probe end ---');
      return;
    }

    const padding = '='.repeat((4 - (key.length % 4)) % 4);
    const b64 = (key + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(b64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);

    try {
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: arr,
      });
      post('SUBSCRIBE_SUCCESS endpoint: ' + sub.endpoint);
      post('SUBSCRIBE_SUCCESS keys.p256dh_present: ' + !!(sub.toJSON().keys && sub.toJSON().keys.p256dh));
    } catch (e) {
      post('SUBSCRIBE_FAILED name=' + (e && e.name) + ' msg=' + (e && e.message ? e.message : String(e)));
    }

    post('--- probe end ---');
  };

  window.addEventListener('load', () => {
    setTimeout(() => { try { window.__pounceRunProbe(); } catch (e) {} }, 1500);
  });
})();
"""

// ---------------------------------------------------------------------------
// App delegate — wires up window, web view, probe handler, toolbar buttons.
// ---------------------------------------------------------------------------
final class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var statusLabel: NSTextField!

    func applicationDidFinishLaunching(_ notification: Notification) {
        ProbeLog.shared.write("app", "launched, prod URL: \(kProdURL)")

        // --- Window ----------------------------------------------------------
        let frame = NSRect(x: 80, y: 80, width: 1280, height: 880)
        window = NSWindow(
            contentRect: frame,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Pounce — WebPush probe"
        window.delegate = self

        // --- Toolbar with two buttons ----------------------------------------
        let toolbarHost = NSView(frame: NSRect(x: 0, y: 0, width: frame.width, height: 36))
        toolbarHost.autoresizingMask = [.width]

        let runBtn = NSButton(title: "Run probe", target: self, action: #selector(runProbe))
        runBtn.frame = NSRect(x: 8, y: 4, width: 100, height: 28)
        runBtn.bezelStyle = .rounded
        toolbarHost.addSubview(runBtn)

        let openLogBtn = NSButton(title: "Open log", target: self, action: #selector(openLog))
        openLogBtn.frame = NSRect(x: 116, y: 4, width: 100, height: 28)
        openLogBtn.bezelStyle = .rounded
        toolbarHost.addSubview(openLogBtn)

        let reloadBtn = NSButton(title: "Reload", target: self, action: #selector(reload))
        reloadBtn.frame = NSRect(x: 224, y: 4, width: 80, height: 28)
        reloadBtn.bezelStyle = .rounded
        toolbarHost.addSubview(reloadBtn)

        statusLabel = NSTextField(labelWithString: "loading…")
        statusLabel.frame = NSRect(x: 320, y: 8, width: frame.width - 328, height: 20)
        statusLabel.autoresizingMask = [.width]
        statusLabel.textColor = .secondaryLabelColor
        toolbarHost.addSubview(statusLabel)

        // --- Web view --------------------------------------------------------
        let cfg = WKWebViewConfiguration()
        let userContent = WKUserContentController()
        userContent.add(self, name: "pounce")
        userContent.addUserScript(WKUserScript(
            source: probeJS,
            injectionTime: .atDocumentEnd,
            forMainFrameOnly: false
        ))
        cfg.userContentController = userContent
        if #available(macOS 13.3, *) {
            cfg.preferences.isElementFullscreenEnabled = true
        }
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true

        let webFrame = NSRect(x: 0, y: 0, width: frame.width, height: frame.height - 36)
        webView = WKWebView(frame: webFrame, configuration: cfg)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.customUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 Pounce-Proto/1.0"
        // Allow Safari → Develop menu to attach the Web Inspector to this view.
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }

        // --- Container -------------------------------------------------------
        let container = NSView(frame: frame)
        container.autoresizingMask = [.width, .height]
        let webHost = NSView(frame: webFrame)
        webHost.autoresizingMask = [.width, .height]
        webHost.addSubview(webView)
        toolbarHost.frame = NSRect(x: 0, y: frame.height - 36, width: frame.width, height: 36)
        container.addSubview(webHost)
        container.addSubview(toolbarHost)
        window.contentView = container

        webView.load(URLRequest(url: URL(string: kProdURL)!))
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    // --- Toolbar actions -----------------------------------------------------
    @objc func runProbe() {
        ProbeLog.shared.write("ui", "Run probe button tapped")
        webView.evaluateJavaScript("typeof window.__pounceRunProbe === 'function' ? window.__pounceRunProbe() : 'probe-not-installed'") { result, err in
            if let err = err {
                ProbeLog.shared.write("ui", "evalJS err: \(err.localizedDescription)")
            }
        }
    }

    @objc func openLog() {
        let url = FileManager.default.urls(for: .desktopDirectory, in: .userDomainMask)[0].appendingPathComponent("pounce-probe.log")
        NSWorkspace.shared.open(url)
    }

    @objc func reload() {
        webView.reload()
    }

    // --- WKScriptMessageHandler ---------------------------------------------
    func userContentController(_ userContentController: WKUserContentController,
                                didReceive message: WKScriptMessage) {
        if let body = message.body as? String {
            ProbeLog.shared.write("probe", body)
            DispatchQueue.main.async { [weak self] in
                self?.statusLabel.stringValue = body
            }
        }
    }

    // --- WKNavigationDelegate -----------------------------------------------
    // The Pounce backend (oauth2-proxy) issues 302s to http:// URLs even though
    // the site is HTTPS-only. Tailscale Funnel doesn't listen on port 80, so
    // the http hop fails with "Could not connect". Upgrade in-flight here as a
    // workaround until oauth2-proxy is configured with REVERSE_PROXY=true.
    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url,
           url.scheme == "http",
           let host = url.host,
           host.hasSuffix(".ts.net") {
            var comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
            comps?.scheme = "https"
            if let upgraded = comps?.url {
                ProbeLog.shared.write("nav", "upgraded http→https: \(host)\(url.path)")
                decisionHandler(.cancel)
                DispatchQueue.main.async { webView.load(URLRequest(url: upgraded)) }
                return
            }
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let urlStr = webView.url?.absoluteString ?? "?"
        ProbeLog.shared.write("nav", "didFinish: \(urlStr)")
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        ProbeLog.shared.write("nav", "didFail: \(error.localizedDescription)")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        ProbeLog.shared.write("nav", "didFailProvisional: \(error.localizedDescription)")
    }

    // Allow Google OAuth pop-up windows to open in the same web view.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if navigationAction.targetFrame == nil, let url = navigationAction.request.url {
            webView.load(URLRequest(url: url))
        }
        return nil
    }

    // --- NSWindowDelegate ----------------------------------------------------
    func windowWillClose(_ notification: Notification) {
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
