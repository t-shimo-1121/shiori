/* 旅行のしおり集：本棚と全冊を端末に保存し、電波がなくても開けるようにする
   開くたびにネットの最新版を取りに行き、つながらない時だけ保存した版を出す */
var CACHE = 'site-__VER__';
var PAGES = __PAGES__;
var SHELL = ['./', './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png'];
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    /* 1冊でも取れなくても他は保存する */
    return Promise.all(SHELL.concat(PAGES).map(function (u) { return c.add(new Request(u, { cache: 'no-cache' })).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('site-') === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  /* 端末やブラウザに残った古い版を使わず、毎回 GitHub に新しい版があるか確かめる（変わっていなければ通信は小さく済む） */
  e.respondWith(fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' }).then(function (r) {
    if (r.ok) { var c = r.clone(); caches.open(CACHE).then(function (ca) { ca.put(req, c); }); }
    return r;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (r) { return r || caches.match('./'); });
  }));
});
