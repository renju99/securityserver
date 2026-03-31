const CACHE_NAME = 'cleaner-v2-v2';
const OFFLINE_QUEUE_KEY = 'cleaner_offline_queue';

// Assets to cache for offline shell
const SHELL_ASSETS = [
    '/',
    '/cleaner',
    '/index.html',
];

// Install: cache app shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Caching app shell');
            return cache.addAll(SHELL_ASSETS).catch((e) => {
                console.warn('[SW] Failed to cache some shell assets:', e);
            });
        })
    );
    self.skipWaiting();
});

// Activate: clean old caches, then force all tabs to reload so they get the new app
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim()).then(() =>
            self.clients.matchAll().then((clientList) =>
                Promise.all(clientList.map((client) => client.navigate(client.url)))
            )
        )
    );
});

// Fetch: Network-first for API, cache-first for static assets
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // API calls: network first, queue if offline
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request.clone()).catch(() => {
                // If it's a mutating request (POST), we can't cache it — it will be queued by the app
                return new Response(JSON.stringify({ error: 'offline', offline: true }), {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return;
    }

    // Static assets: cache first, network fallback
    event.respondWith(
        caches.match(request).then((cached) => {
            return cached || fetch(request).then((response) => {
                // Cache successful GET responses for static assets
                if (request.method === 'GET' && response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
                }
                return response;
            }).catch(() => {
                // Offline fallback: return cached index.html for navigation requests
                if (request.mode === 'navigate') {
                    return caches.match('/index.html');
                }
                return new Response('Offline', { status: 503 });
            });
        })
    );
});

// Background sync for queued offline actions
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-offline-queue') {
        event.waitUntil(syncQueue());
    }
});

async function syncQueue() {
    // The sync is handled by the app itself on 'online' event
    // This event fires on Android when connectivity returns
    const clients = await self.clients.matchAll();
    clients.forEach(client => client.postMessage({ type: 'SYNC_REQUESTED' }));
}

// Push notifications (for schedule reminders - future feature)
self.addEventListener('push', (event) => {
    if (!event.data) return;
    const data = event.data.json();
    event.waitUntil(
        self.registration.showNotification(data.title || 'Cleaning Reminder', {
            body: data.body || 'Time to clean!',
            icon: '/icons/icon-192.png',
            badge: '/icons/icon-192.png',
            tag: 'cleaning-reminder',
            data: data.url || '/cleaner'
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data || '/cleaner')
    );
});
