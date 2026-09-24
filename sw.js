// Reading牛津阅读 · 音频 Service Worker
// 只缓存 reading_audio 下的 mp3：已拉过的音频存本地，跨会话/隔天打开直接秒出。
// 其余请求（页面、脚本、gate.js）一律走网络，保证内容更新即时生效。
const CACHE = 'edge-reading-audio-v1';
const AUDIO_RE = /\/reading_audio\/.*\.mp3(\?.*)?$/i;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (!AUDIO_RE.test(url.pathname)) return;   // 只拦截音频
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(req);
    if (hit) return hit;                       // 命中缓存 → 瞬间返回
    try {
      const res = await fetch(req);
      if (res && res.ok && (res.type === 'basic' || res.type === 'cors' || res.type === 'default')) {
        cache.put(req, res.clone()).catch(() => {});
      }
      return res;
    } catch (err) {
      return hit || Response.error();
    }
  })());
});
