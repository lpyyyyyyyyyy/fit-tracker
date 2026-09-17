/* 本地预览服务：同时开 HTTP(8080) 和 HTTPS(8443)
   HTTPS 是手机能用「系统通知 / 装到主屏幕」的前提。
   证书是自签的（_cert.pem），手机第一次打开会弹一次「不安全 → 继续访问」，点掉就行。 */
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = __dirname;
const HTTP_PORT = Number(process.argv[2] || 8080);
const HTTPS_PORT = Number(process.argv[3] || 8443);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
};

function handler(req, res) {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/' || p === '') p = '/index.html';
  const file = path.join(ROOT, path.normalize(p).replace(/^([/\\])+/, ''));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end('forbidden'); return; }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('404 ' + p); return; }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
      'Service-Worker-Allowed': '/',
    });
    res.end(buf);
  });
}

const ips = [];
Object.values(os.networkInterfaces()).forEach(list =>
  (list || []).forEach(i => { if (i.family === 'IPv4' && !i.internal) ips.push(i.address); }));
/* 只保留真实局域网地址（过滤 Clash 的 28.x 虚拟网卡和 Hyper-V 的 172.24.x） */
const lan = ips.filter(ip =>
  /^192\.168\.|^10\./.test(ip) || (/^172\.(1[6-9]|2\d|3[01])\./.test(ip) && !ip.startsWith('172.24.')));

http.createServer(handler).listen(HTTP_PORT, '0.0.0.0', () => {
  console.log('✅ HTTP  已启动');
  console.log('   电脑：http://localhost:' + HTTP_PORT + '/');
  lan.forEach(ip => console.log('   手机：http://' + ip + ':' + HTTP_PORT + '/'));
});

const certPath = path.join(ROOT, '_cert.pem');
const keyPath = path.join(ROOT, '_key.pem');
if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
  https.createServer({ cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }, handler)
    .listen(HTTPS_PORT, '0.0.0.0', () => {
      console.log('\n🔒 HTTPS 已启动（系统通知 / 装到主屏幕 必须走这个）');
      lan.forEach(ip => console.log('   手机：https://' + ip + ':' + HTTPS_PORT + '/'));
      console.log('\n   ⚠️ 手机第一次打开会提示「不安全」，点「高级 → 继续前往」即可。');
    });
} else {
  console.log('\n⚠️ 没找到 _cert.pem / _key.pem，HTTPS 未启动。');
}

console.log('\n   按 Ctrl+C 停止');
