/**
 * Service Worker for GuardLink Training Offline Support
 * Handles caching of training content and assets for offline access
 */

const CACHE_NAME = 'guardpro-training-cache-v1';
const STATIC_CACHE_NAME = 'guardpro-static-v1';

// Assets to cache immediately
const STATIC_ASSETS = [
    '/',
    '/web/static/lib/bootstrap/css/bootstrap.css',
    '/web/static/lib/fontawesome/css/font-awesome.css',
    '/web/static/src/css/web.assets_frontend.css',
    '/guardpro/static/src/css/mobile.css'
];

// Install event - cache static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;

    // Skip external requests
    if (!event.request.url.includes(self.location.origin)) return;

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version if available
                if (response) {
                    return response;
                }

                // Otherwise, fetch from network
                return fetch(event.request).then(networkResponse => {
                    // Cache training-related requests
                    if (event.request.url.includes('/guardpro/api/training/') ||
                        event.request.url.includes('/slides/')) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(event.request, responseClone));
                    }

                    return networkResponse;
                }).catch(() => {
                    // Return offline fallback for training pages
                    if (event.request.url.includes('/mobile/training')) {
                        return caches.match('/mobile/training');
                    }

                    // Return offline page for other requests
                    return new Response(
                        '<h1>Offline</h1><p>This content is not available offline.</p>',
                        {
                            headers: { 'Content-Type': 'text/html' }
                        }
                    );
                });
            })
    );
});

// Message event - handle cache updates from main thread
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'CACHE_SLIDE') {
        const { slideId, slideData } = event.data;
        caches.open(CACHE_NAME)
            .then(cache => {
                const response = new Response(JSON.stringify(slideData), {
                    headers: { 'Content-Type': 'application/json' }
                });
                return cache.put(`/guardpro/api/training/slide/${slideId}`, response);
            });
    }
});



