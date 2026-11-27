// App shell cache so the app opens instantly on a slow CSC connection. API calls always go to the network:
// answers and consent are never cached on the device.
const SHELL = "bkb-shell-v1";
const FILES = ["/", "/web/fill.js", "/web/portal.html", "/web/slip.html", "/web/portal-map.json", "/web/icon-192.png"];
self.addEventListener("install", (e) => e.waitUntil(caches.open(SHELL).then((c) => c.addAll(FILES))));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/") || e.request.method !== "GET") return;
  // Network first, cache as a fallback, so a new version is picked up whenever the network works.
  e.respondWith(fetch(e.request).then((r) => {
    const copy = r.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); return r;
  }).catch(() => caches.match(e.request)));
});
