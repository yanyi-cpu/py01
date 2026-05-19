// PWA Service Worker — 缓存静态资源 + 离线兜底
var CACHE_NAME = 'ai-chat-v1';

var PRECACHE = [
    '/',
    '/static/style.css',
    '/static/app.js',
    '/static/icon.svg'
];

// 安装：预缓存静态文件
self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(PRECACHE);
        }).then(function () {
            return self.skipWaiting();
        })
    );
});

// 激活：清理旧缓存
self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE_NAME; })
                    .map(function (k) { return caches.delete(k); })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

// 请求拦截：缓存优先（静态），网络优先（API）
self.addEventListener('fetch', function (e) {
    var url = new URL(e.request.url);

    // API 请求走网络，不缓存
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    // 静态资源：缓存优先
    e.respondWith(
        caches.match(e.request).then(function (cached) {
            return cached || fetch(e.request).then(function (resp) {
                if (resp.ok && e.request.method === 'GET') {
                    var clone = resp.clone();
                    caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(e.request, clone);
                    });
                }
                return resp;
            });
        })
    );
});
