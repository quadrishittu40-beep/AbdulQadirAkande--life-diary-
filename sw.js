/* Offline support for My Life Diary. Entries live in the browser's own storage, so only the app files are cached here. */
var CACHE = 'life-diary-v4';
var FILES = [
  './',
  'index.html',
  'manifest.webmanifest',
  'assets/photo.jpg',
  'assets/backgrounds/bg1.jpg',
  'assets/backgrounds/bg2.jpg',
  'assets/backgrounds/bg3.jpg',
  'assets/backgrounds/bg4.jpg'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.all(FILES.map(function (u) { return c.add(u).catch(function () {}); }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  if (req.mode === 'navigate') {
    /* Page loads: try the network first so updates arrive, fall back to the saved copy offline. */
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put('index.html', copy); });
        return res;
      }).catch(function () { return caches.match('index.html').then(function (r) { return r || caches.match('./'); }); })
    );
    return;
  }
  e.respondWith(
    caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        if (res && res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
        return res;
      });
    })
  );
});
