/* 绂荤嚎缂撳瓨 鈥斺€?璁?App 瑁呭埌涓诲睆骞曞悗鏂綉涔熻兘鎵撳紑銆?   鍙湪 https 鎴?localhost 涓嬫墠浼氭敞鍐屾垚鍔燂紙娴忚鍣ㄨ姹傦級銆?
   鈿狅笍 鏀硅繃鍐呭鍚庡繀椤绘妸 CACHE 鐗堟湰鍙?+1锛屽惁鍒欒€佺紦瀛樹細涓€鐩寸敓鏁堬紝
      鐢ㄦ埛鐪嬪埌鐨勮繕鏄棫鐗堥〉闈紙杩欎釜鍧戠湡韪╄繃锛夈€?*/
const VER = 'v4';
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

/* 缃戠粶浼樺厛锛氭嬁寰楀埌灏辩敤鏈€鏂扮殑锛屽苟椤烘墜鏇存柊缂撳瓨锛涙嬁涓嶅埌鎵嶅洖缂撳瓨銆?   姣斻€岀紦瀛樹紭鍏堛€嶆參涓€鐐圭偣锛屼絾缁濅笉浼氳浣犵湅鍒拌繃鏈熼〉闈€?*/
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
  if (url.origin !== location.origin) return;      // 鍙鐞嗚嚜宸辩殑璧勬簮

  /* 椤甸潰鍜岃剼鏈竴寰嬬綉缁滀紭鍏?鈥斺€?淇濊瘉浣犵湅鍒扮殑鏄渶鏂扮増 */
  const isDoc = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html');
  const isCode = url.pathname.endsWith('.js');
  if (isDoc || isCode) {
    e.respondWith(networkFirst(req));
    return;
  }
  /* 鍏朵粬闈欐€佽祫婧愶細缂撳瓨浼樺厛锛堝揩锛夛紝浣嗕篃娌″嚑涓?*/
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

/* 鍏佽椤甸潰閫氳繃 SW 寮归€氱煡锛堥儴鍒嗙幆澧冧笅姣旂洿鎺?new Notification 鏇村彲闈狅級 */
self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'notify') {
    self.registration.showNotification(d.title || '鐕?路 鍑忚剛鎵撳崱', {
      body: d.body || '',
      tag: 'ran-fit',
      renotify: true,
      icon: d.icon,
      badge: d.icon,
      vibrate: [90, 50, 90],
    });
  }
  /* 椤甸潰瑕佹眰绔嬪埢妫€鏌ユ洿鏂?*/
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

