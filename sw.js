// Keeps the game on the phone so it opens even with no internet (after the first visit).
// The game files check for updates first; the big engine files from the CDN are kept once downloaded.
// Saves are never cached - they always go straight to the game box.
const CACHE = "gio-game-v2";
const FILES = ["./", "./index.html", "./game.py", "./manifest.json", "./icon.svg"];

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)));
});
self.addEventListener("activate", e => e.waitUntil(   // drop copies from older versions
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())));

const keep = (req, res) => {
  if (res && (res.ok || res.type === "opaque")) {
    const copy = res.clone();
    caches.open(CACHE).then(c => c.put(req, copy));
  }
  return res;
};

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.endsWith("/save")) return;   // never cache her save
  if (url.origin === location.origin) {         // game files: newest if online, saved copy if not
    e.respondWith(fetch(req, {cache: "no-store"}).then(r => keep(req, r)).catch(() => caches.match(req, {ignoreSearch: true})));
  } else if (url.hostname === "cdn.jsdelivr.net") {   // engine + fonts: download once, then keep
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => keep(req, r))));
  }
});
