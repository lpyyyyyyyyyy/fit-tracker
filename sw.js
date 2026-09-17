/* 缁傝崵鍤庣紓鎾崇摠 閳ユ柡鈧?鐠?App 鐟佸懎鍩屾稉璇茬潌楠炴洖鎮楅弬顓犵秹娑旂喕鍏橀幍鎾崇磻閵?   閸欘亜婀?https 閹?localhost 娑撳澧犳导姘暈閸愬本鍨氶崝鐕傜礄濞村繗顫嶉崳銊洣濮瑰偊绱氶妴?
   閳跨媴绗?閺€纭呯箖閸愬懎顔愰崥搴＄箑妞ょ粯濡?CACHE 閻楀牊婀伴崣?+1閿涘苯鎯侀崚娆掆偓浣虹处鐎涙ü绱版稉鈧惄瀵告晸閺佸牞绱?      閻劍鍩涢惇瀣煂閻ㄥ嫯绻曢弰顖涙＋閻楀牓銆夐棃顫礄鏉╂瑤閲滈崸鎴犳埂闊晞绻冮敍澶堚偓?*/
const VER = 'v15';
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

/* 缂冩垹绮舵导妯哄帥閿涙碍瀣佸妤€鍩岀亸杈╂暏閺堚偓閺傛壆娈戦敍灞借嫙妞ょ儤澧滈弴瀛樻煀缂傛挸鐡ㄩ敍娑欏瑏娑撳秴鍩岄幍宥呮礀缂傛挸鐡ㄩ妴?   濮ｆ柣鈧瞼绱︾€涙ü绱崗鍫涒偓宥嗗弮娑撯偓閻愬湱鍋ｉ敍灞肩稻缂佹繀绗夋导姘愁唨娴ｇ姷婀呴崚鎷岀箖閺堢喖銆夐棃顫偓?*/
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
  if (url.origin !== location.origin) return;      // 閸欘亜顦╅悶鍡氬殰瀹歌京娈戠挧鍕爱

  /* 妞ょ敻娼伴崪宀冨壖閺堫兛绔村瀣秹缂佹粈绱崗?閳ユ柡鈧?娣囨繆鐦夋担鐘垫箙閸掓壆娈戦弰顖涙付閺傛壆澧?*/
  const isDoc = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html');
  const isCode = url.pathname.endsWith('.js');
  if (isDoc || isCode) {
    e.respondWith(networkFirst(req));
    return;
  }
  /* 閸忔湹绮棃娆愨偓浣界カ濠ф劧绱扮紓鎾崇摠娴兼ê鍘涢敍鍫濇彥閿涘绱濇担鍡曠瘍濞屸€冲殤娑?*/
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

/* 閸忎浇顔忔い鐢告桨闁俺绻?SW 瀵綊鈧氨鐓￠敍鍫ュ劥閸掑棛骞嗘晶鍐х瑓濮ｆ梻娲块幒?new Notification 閺囨潙褰查棃鐙呯礆 */
self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'notify') {
    self.registration.showNotification(d.title || '閻?璺?閸戝繗鍓涢幍鎾冲幢', {
      body: d.body || '',
      tag: 'ran-fit',
      renotify: true,
      icon: d.icon,
      badge: d.icon,
      vibrate: [90, 50, 90],
    });
  }
  /* 妞ょ敻娼扮憰浣圭湴缁斿鍩㈠Λ鈧弻銉︽纯閺?*/
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

