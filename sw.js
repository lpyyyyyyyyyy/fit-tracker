/* 离线缓存 —— 让 App 装到主屏幕后即使断网也能打开。
   只在 https 或 localhost 下才会注册成功（浏览器要求）。 */
const CACHE = 'ran-fit-v1';
const ASSETS = ['./', './index.html', './manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;   // 只处理自己的资源

  /* 页面导航：先网络（拿最新），失败再回缓存 */
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then(r => { caches.open(CACHE).then(c => c.put('./index.html', r.clone())); return r; })
        .catch(() => caches.match('./index.html').then(r => r || caches.match('./')))
    );
    return;
  }
  /* 其他资源：先缓存，再网络 */
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(r => {
      if (r && r.status === 200 && r.type === 'basic') {
        caches.open(CACHE).then(c => c.put(req, r.clone()));
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
