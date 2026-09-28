/**
 * AGRO Field — Service Worker for offline-first operation.
 * Caches static assets and field page; queues POST/PUT requests when offline.
 */
const CACHE_NAME = 'agro-field-v1';
const URLS_TO_CACHE = [
    '/UNA.md/orasldev/agro-field',
    '/static/agro/offline-db.js',
    '/static/agro/barcode-scanner.js',
    '/static/agro/barcode-generator.js'
];

/* Install — pre-cache essential assets */
self.addEventListener('install', function(e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(URLS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

/* Activate — clean old caches */
self.addEventListener('activate', function(e) {
    e.waitUntil(
        caches.keys().then(function(names) {
            return Promise.all(
                names.filter(function(n) { return n !== CACHE_NAME; })
                     .map(function(n) { return caches.delete(n); })
            );
        })
    );
    self.clients.claim();
});

/* Fetch — cache-first for GET, network-first with queue fallback for mutations */
self.addEventListener('fetch', function(e) {
    var url = new URL(e.request.url);

    // Only intercept same-origin requests
    if (url.origin !== location.origin) return;

    if (e.request.method === 'GET') {
        // Cache-first for static assets, network-first for API
        if (url.pathname.startsWith('/api/')) {
            // Network-first for API GETs
            e.respondWith(
                fetch(e.request).then(function(resp) {
                    // Cache successful API responses
                    var clone = resp.clone();
                    caches.open(CACHE_NAME).then(function(cache) {
                        cache.put(e.request, clone);
                    });
                    return resp;
                }).catch(function() {
                    return caches.match(e.request).then(function(r) {
                        return r || new Response(JSON.stringify({
                            success: false, error: 'Offline', offline: true
                        }), { headers: { 'Content-Type': 'application/json' } });
                    });
                })
            );
        } else {
            // Cache-first for pages and static assets
            e.respondWith(
                caches.match(e.request).then(function(r) {
                    return r || fetch(e.request).then(function(resp) {
                        var clone = resp.clone();
                        caches.open(CACHE_NAME).then(function(cache) {
                            cache.put(e.request, clone);
                        });
                        return resp;
                    });
                })
            );
        }
    } else {
        // POST/PUT/DELETE — try network, queue if offline
        e.respondWith(
            fetch(e.request.clone()).catch(function() {
                // Clone and read body for queueing
                return e.request.clone().text().then(function(bodyText) {
                    var body = null;
                    try { body = JSON.parse(bodyText); } catch (_) { body = bodyText; }

                    // Notify client to queue this request
                    self.clients.matchAll().then(function(clients) {
                        clients.forEach(function(client) {
                            client.postMessage({
                                type: 'QUEUE_REQUEST',
                                url: e.request.url,
                                method: e.request.method,
                                body: body,
                                timestamp: Date.now()
                            });
                        });
                    });

                    return new Response(JSON.stringify({
                        success: true,
                        queued: true,
                        message: 'Сохранено офлайн, синхронизируется при подключении / Salvat offline, se va sincroniza la reconectare'
                    }), { headers: { 'Content-Type': 'application/json' } });
                });
            })
        );
    }
});
