// Pounce — native macOS app for the Pounce swing-trading dashboard.
//
// Architecture
// ------------
// Native AppKit shell hosts a WKWebView pointing at the production URL,
// reusing the entire React frontend with no duplication. Push notifications
// arrive over a Server-Sent Events (SSE) connection to /push/mac-stream
// (auth shared with the WebView via cookie sync) and fire as native macOS
// notifications via UNUserNotificationCenter.
//
// We deliberately don't use Web Push inside the WKWebView because that
// requires the com.apple.developer.aps-environment entitlement, which
// requires a paid Apple Developer Program account. The probe at
// macos/proto/Pounce.swift confirms Notification.requestPermission() returns
// "denied" silently without it. The SSE + local-notifications path needs no
// entitlements and produces an identical UX.
//
// Lifecycle
// ---------
// • Auto-registers as a Login Item on first launch (SMAppService.mainApp).
// • Window close hides the window but keeps the app running so the SSE
//   connection stays open. Quit (⌘Q) fully exits.
// • Notifications click → focus app, navigate WebView to payload.url.

import Cocoa
import WebKit
import UserNotifications
import ServiceManagement

let kProdURL  = "https://ajays-macbook-pro.tailb3dc79.ts.net/"
let kStreamPath = "/api/push/mac-stream"   // through nginx → backend SSE
let kRegisterPath = "/api/push/mac-register"
let kLogTag    = "pounce"

// ---------------------------------------------------------------------------
// Logging — file-based plus stderr so `Console.app` and `tail -F ~/Library/
// Logs/Pounce/pounce.log` both work.
// ---------------------------------------------------------------------------
final class Logger {
    static let shared = Logger()
    private let url: URL
    private let fmt = ISO8601DateFormatter()

    init() {
        let dir = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Logs/Pounce", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        self.url = dir.appendingPathComponent("pounce.log")
        if !FileManager.default.fileExists(atPath: url.path) {
            try? "".write(to: url, atomically: true, encoding: .utf8)
        }
    }

    func log(_ tag: String, _ msg: String) {
        let line = "\(fmt.string(from: Date())) [\(tag)] \(msg)\n"
        FileHandle.standardError.write(line.data(using: .utf8) ?? Data())
        if let h = try? FileHandle(forWritingTo: url) {
            h.seekToEndOfFile()
            h.write(line.data(using: .utf8) ?? Data())
            try? h.close()
        }
    }
}

// ---------------------------------------------------------------------------
// DeviceID — stable uuid persisted to ~/Library/Application Support/Pounce/.
// Used by /push/mac-register so backend can identify each install.
// ---------------------------------------------------------------------------
enum DeviceID {
    static func get() -> String {
        let supportDir = FileManager.default.urls(for: .applicationSupportDirectory,
                                                   in: .userDomainMask)[0]
            .appendingPathComponent("Pounce", isDirectory: true)
        try? FileManager.default.createDirectory(at: supportDir, withIntermediateDirectories: true)
        let file = supportDir.appendingPathComponent("device_id")
        if let data = try? Data(contentsOf: file),
           let s = String(data: data, encoding: .utf8) {
            let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty { return trimmed }
        }
        let id = UUID().uuidString.lowercased()
        try? id.write(to: file, atomically: true, encoding: .utf8)
        return id
    }

    static func deviceLabel() -> String {
        let host = Host.current().localizedName ?? "Mac"
        return "\(host)"
    }
}

// ---------------------------------------------------------------------------
// CookieBridge — mirror cookies set in WKWebView (after Google OAuth) into
// the URLSession cookie store so the SSE connection authenticates correctly.
// ---------------------------------------------------------------------------
final class CookieBridge: NSObject, WKHTTPCookieStoreObserver {
    let store: WKHTTPCookieStore
    var onChange: (() -> Void)?

    init(store: WKHTTPCookieStore) {
        self.store = store
        super.init()
        store.add(self)
        sync()
    }

    func cookiesDidChange(in cookieStore: WKHTTPCookieStore) {
        sync()
    }

    func sync() {
        store.getAllCookies { cookies in
            for c in cookies {
                HTTPCookieStorage.shared.setCookie(c)
            }
            DispatchQueue.main.async { [weak self] in
                self?.onChange?()
            }
        }
    }
}

// ---------------------------------------------------------------------------
// SSEListener — opens GET /push/mac-stream and dispatches `alert` events.
// Reconnects with exponential backoff. Safe to start before login (it'll
// keep getting 401/302 redirects until the user signs in, then succeed).
// ---------------------------------------------------------------------------
final class SSEListener {
    let baseURL: URL
    let deviceID: String
    let session: URLSession
    private var task: Task<Void, Never>?
    private var stopped = false
    var onAlert: ((NotificationPayload) -> Void)?
    var onConnect: (() -> Void)?

    init(baseURL: URL, deviceID: String) {
        self.baseURL = baseURL
        self.deviceID = deviceID
        // Long timeout — SSE keeps the connection open indefinitely with
        // server-side heartbeats every 15s.
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 0           // no per-request timeout
        cfg.timeoutIntervalForResource = 0          // no overall timeout
        cfg.httpCookieStorage = HTTPCookieStorage.shared
        cfg.httpShouldSetCookies = true
        cfg.httpCookieAcceptPolicy = .always
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        cfg.httpAdditionalHeaders = [
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        ]
        self.session = URLSession(configuration: cfg)
    }

    func start() {
        stopped = false
        task = Task { await self.runLoop() }
    }

    func stop() {
        stopped = true
        task?.cancel()
    }

    private func runLoop() async {
        var backoff: TimeInterval = 1.0
        while !stopped && !Task.isCancelled {
            do {
                try await connectOnce()
                backoff = 1.0
            } catch is CancellationError {
                break
            } catch {
                Logger.shared.log("sse", "error: \(error.localizedDescription); reconnect in \(Int(backoff))s")
            }
            // Cap backoff at 30s; reset on every successful connect.
            try? await Task.sleep(nanoseconds: UInt64(backoff * 1_000_000_000))
            backoff = min(backoff * 1.7, 30.0)
        }
    }

    private func connectOnce() async throws {
        var comps = URLComponents(url: baseURL.appendingPathComponent(kStreamPath),
                                   resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "device_id", value: deviceID)]
        guard let url = comps.url else { return }

        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        Logger.shared.log("sse", "connecting \(url)")
        let (bytes, response) = try await session.bytes(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw NSError(domain: "Pounce", code: -1, userInfo: [NSLocalizedDescriptionKey: "bad response"])
        }
        if http.statusCode != 200 {
            throw NSError(domain: "Pounce", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode)"])
        }
        Logger.shared.log("sse", "connected (200)")
        await MainActor.run { self.onConnect?() }

        var event = "message"
        var data = ""
        for try await line in bytes.lines {
            if Task.isCancelled { return }
            if line.isEmpty {
                if !data.isEmpty {
                    handle(event: event, data: data)
                }
                event = "message"
                data = ""
                continue
            }
            if line.hasPrefix(":") { continue }   // heartbeat / comment
            if line.hasPrefix("event:") {
                event = String(line.dropFirst("event:".count))
                    .trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                let chunk = String(line.dropFirst("data:".count))
                    .trimmingCharacters(in: .whitespaces)
                data = data.isEmpty ? chunk : data + "\n" + chunk
            }
        }
    }

    private func handle(event: String, data: String) {
        guard event == "alert" else {
            Logger.shared.log("sse", "evt=\(event) (skip)")
            return
        }
        guard let raw = data.data(using: .utf8),
              let any = try? JSONSerialization.jsonObject(with: raw) as? [String: Any] else {
            Logger.shared.log("sse", "alert: bad JSON")
            return
        }
        let p = NotificationPayload(dict: any)
        Logger.shared.log("sse", "alert: kind=\(p.kind) tag=\(p.tag) url=\(p.url)")
        DispatchQueue.main.async { [weak self] in self?.onAlert?(p) }
    }
}

// ---------------------------------------------------------------------------
// NotificationPayload — typed view of the JSON we receive from the backend.
// Mirrors the fields the existing service worker uses (sw.js).
// ---------------------------------------------------------------------------
struct NotificationPayload {
    let title: String
    let body: String
    let tag: String
    let url: String
    let kind: String
    let ticker: String?

    init(dict: [String: Any]) {
        self.title = (dict["title"] as? String) ?? "Pounce"
        self.body = (dict["body"] as? String) ?? ""
        self.tag = (dict["tag"] as? String) ?? "pounce"
        self.url = (dict["url"] as? String) ?? "/"
        self.kind = (dict["kind"] as? String) ?? "generic"
        self.ticker = dict["ticker"] as? String
    }
}

// ---------------------------------------------------------------------------
// NotificationDispatcher — wraps UNUserNotificationCenter. Click handler
// posts back to the AppDelegate so it can navigate the WebView.
// ---------------------------------------------------------------------------
final class NotificationDispatcher: NSObject, UNUserNotificationCenterDelegate {
    var onClick: ((String) -> Void)?     // url string from payload

    func bootstrap() {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            Logger.shared.log("noti", "authorization granted=\(granted) err=\(error?.localizedDescription ?? "-")")
        }
    }

    func dispatch(_ p: NotificationPayload) {
        let c = UNMutableNotificationContent()
        c.title = p.title
        c.body  = p.body
        c.sound = .default
        c.userInfo = ["url": p.url, "kind": p.kind]
        c.threadIdentifier = p.tag
        let req = UNNotificationRequest(identifier: "\(p.tag)-\(UUID().uuidString)",
                                        content: c, trigger: nil)
        UNUserNotificationCenter.current().add(req) { err in
            if let err = err {
                Logger.shared.log("noti", "add err: \(err.localizedDescription)")
            }
        }
    }

    // Show banners even when the app is foreground.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler:
                                  @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .list])
    }

    // Click → navigate WebView.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler:
                                  @escaping () -> Void) {
        let url = (response.notification.request.content.userInfo["url"] as? String) ?? "/"
        DispatchQueue.main.async { [weak self] in self?.onClick?(url) }
        completionHandler()
    }
}

// ---------------------------------------------------------------------------
// LoginItem — auto-launch on user login. macOS 13+ uses SMAppService.
// First registration may show a System Settings prompt. Idempotent.
// ---------------------------------------------------------------------------
enum LoginItem {
    static func ensureRegistered() {
        if #available(macOS 13.0, *) {
            let svc = SMAppService.mainApp
            do {
                if svc.status != .enabled {
                    try svc.register()
                    Logger.shared.log("login", "registered as login item (status=\(svc.status.rawValue))")
                } else {
                    Logger.shared.log("login", "already a login item")
                }
            } catch {
                Logger.shared.log("login", "register failed: \(error.localizedDescription)")
            }
        }
    }

    static func unregister() {
        if #available(macOS 13.0, *) {
            try? SMAppService.mainApp.unregister()
        }
    }
}

// ---------------------------------------------------------------------------
// AppDelegate — composition root.
// ---------------------------------------------------------------------------
final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var listener: SSEListener!
    var dispatcher = NotificationDispatcher()
    var cookieBridge: CookieBridge!
    var statusItem: NSStatusItem?

    let deviceID = DeviceID.get()

    func applicationDidFinishLaunching(_ notification: Notification) {
        Logger.shared.log("app", "launch device_id=\(deviceID) prod=\(kProdURL)")
        buildMainMenu()
        buildWindow()
        bootstrapWebView()
        dispatcher.onClick = { [weak self] url in self?.navigate(to: url) }
        dispatcher.bootstrap()
        startSSE()
        LoginItem.ensureRegistered()
    }

    // --- Menu ----------------------------------------------------------------
    func buildMainMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(title: "About Pounce",
                                   action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
                                   keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Hide Pounce",
                                   action: #selector(NSApplication.hide(_:)),
                                   keyEquivalent: "h"))
        let hideOthers = NSMenuItem(title: "Hide Others",
                                     action: #selector(NSApplication.hideOtherApplications(_:)),
                                     keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(NSMenuItem(title: "Show All",
                                   action: #selector(NSApplication.unhideAllApplications(_:)),
                                   keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Quit Pounce",
                                   action: #selector(NSApplication.terminate(_:)),
                                   keyEquivalent: "q"))
        appItem.submenu = appMenu

        // Edit menu so ⌘C/⌘V/⌘X work in the WebView.
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(NSMenuItem(title: "Undo",  action: Selector(("undo:")),  keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "Redo",  action: Selector(("redo:")),  keyEquivalent: "Z"))
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(NSMenuItem(title: "Cut",   action: #selector(NSText.cut(_:)),   keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "Copy",  action: #selector(NSText.copy(_:)),  keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v"))
        editMenu.addItem(NSMenuItem(title: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"))
        editItem.submenu = editMenu

        // View menu — Reload binding.
        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let viewMenu = NSMenu(title: "View")
        viewMenu.addItem(NSMenuItem(title: "Reload", action: #selector(reload), keyEquivalent: "r"))
        viewItem.submenu = viewMenu

        NSApp.mainMenu = main
    }

    // --- Window --------------------------------------------------------------
    func buildWindow() {
        let frame = NSRect(x: 80, y: 80, width: 1280, height: 880)
        window = NSWindow(contentRect: frame,
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered,
                          defer: false)
        window.title = "Pounce"
        window.delegate = self
        window.setFrameAutosaveName("PounceMainWindow")
    }

    // --- WebView -------------------------------------------------------------
    func bootstrapWebView() {
        let cfg = WKWebViewConfiguration()
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true
        if #available(macOS 13.3, *) {
            cfg.preferences.isElementFullscreenEnabled = true
        }
        webView = WKWebView(frame: window.contentView!.bounds, configuration: cfg)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }
        window.contentView?.addSubview(webView)

        // Sync cookies from WKWebView → URLSession so SSE inherits the
        // oauth2-proxy session after Google login.
        cookieBridge = CookieBridge(store: cfg.websiteDataStore.httpCookieStore)
        cookieBridge.onChange = { [weak self] in self?.listener?.start() }

        if let url = URL(string: kProdURL) {
            webView.load(URLRequest(url: url))
        }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    // --- SSE -----------------------------------------------------------------
    func startSSE() {
        guard let base = URL(string: kProdURL) else { return }
        listener = SSEListener(baseURL: base, deviceID: deviceID)
        listener.onAlert = { [weak self] p in self?.dispatcher.dispatch(p) }
        listener.onConnect = { Logger.shared.log("sse", "stream live") }
        listener.start()
    }

    // --- Navigation ----------------------------------------------------------
    func navigate(to path: String) {
        // ``path`` is whatever the backend supplied in payload.url — typically a
        // route like /sepa/AAPL or an absolute URL. Resolve relative paths
        // against the prod base.
        let target: URL? = {
            if let u = URL(string: path), u.scheme != nil { return u }
            return URL(string: path, relativeTo: URL(string: kProdURL))?.absoluteURL
        }()
        guard let url = target else { return }
        Logger.shared.log("nav", "from notification → \(url)")
        if !window.isVisible {
            window.makeKeyAndOrderFront(nil)
        }
        NSApp.activate(ignoringOtherApps: true)
        webView.load(URLRequest(url: url))
    }

    @objc func reload() { webView.reload() }

    // --- WKNavigationDelegate -----------------------------------------------
    // The Pounce backend (oauth2-proxy) issues 302s to http:// URLs even
    // though the site is HTTPS-only. Tailscale Funnel doesn't listen on
    // port 80, so the http hop fails. Upgrade in-flight here.
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
                Logger.shared.log("nav", "upgrade http→https \(host)\(url.path)")
                decisionHandler(.cancel)
                DispatchQueue.main.async { webView.load(URLRequest(url: upgraded)) }
                return
            }
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        if navigationAction.targetFrame == nil, let url = navigationAction.request.url {
            webView.load(URLRequest(url: url))
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Logger.shared.log("nav", "didFinish \(webView.url?.absoluteString ?? "?")")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        Logger.shared.log("nav", "didFailProvisional \(error.localizedDescription)")
    }

    // --- Window-close = hide, NOT quit. ------------------------------------
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        sender.orderOut(nil)
        return false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    // Re-clicking the dock icon brings the window back.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window.makeKeyAndOrderFront(nil) }
        return true
    }
}

// ---------------------------------------------------------------------------
// Entry point.
// ---------------------------------------------------------------------------
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
