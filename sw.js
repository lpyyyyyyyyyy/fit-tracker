/* 离线缓存 —— 让 App 装到主屏幕后断网也能打开。
   只在 https 或 localhost 下才会注册成功（浏览器要求）。

   ⚠️ 改过内容后必须把 CACHE 版本号 +1，否则老缓存会一直生效，
      用户看到的还是旧版页面（这个坑真踩过）。 */
const VER = 'v3';
const CACHE = 'ran-fit-' + VER;
const ASSETS = ['./', './index.html', './manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(ASSETS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* 网络优先：拿得到就用最新的，并顺手更新缓存；拿不到才回缓存。
   比「缓存优先」慢一点点，但绝不会让你看到过期页面。 */
function networkFirst(req) {
  return fetch(req, { cache: 'no-store' })
    .then(r => {
      if (r && r.status === 200) {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(req, cp)).catch(() => {});
      }
      return r;
    })
    .catch(() => caches.match(req).then(hit => hit || caches.match('./index.html')));
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;      // 只处理自己的资源

  /* 页面和脚本一律网络优先 —— 保证你看到的是最新版 */
  const isDoc = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html');
  const isCode = url.pathname.endsWith('.js');
  if (isDoc || isCode) {
    e.respondWith(networkFirst(req));
    return;
  }
  /* 其他静态资源：缓存优先（快），但也没几个 */
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(r => {
      if (r && r.status === 200 && r.type === 'basic') {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(req, cp)).catch(() => {});
      }
      return r;
    }).catch(() => hit))
  );
});

/* 允许页面通过 SW 弹通知（部分环境下比直接 new Notification 更可靠） */
self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'notify') {
    self.registration.showNotification(d.title || '燃 · 减脂打卡', {
      body: d.body || '',
      tag: 'ran-fit',
      renotify: true,
      icon: d.icon,
      badge: d.icon,
      vibrate: [90, 50, 90],
    });
  }
  /* 页面要求立刻检查更新 */
  if (d.type === 'skipWaiting') self.skipWaiting();
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) if ('focus' in c) return c.focus();
      if (self.clients.openWindow) return self.clients.openWindow('./');
    })
  );
});
