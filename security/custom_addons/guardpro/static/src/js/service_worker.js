/* eslint-env serviceworker */
/* eslint-disable no-restricted-globals */
/**
 * GuardLink PWA Service Worker
 * Handles offline caching, data synchronization, and conflict resolution
 */

const CACHE_NAME = 'guardpro-cache-v2';
const OFFLINE_QUEUE_NAME = 'guardpro-offline-queue';
const DATA_CACHE_NAME = 'guardpro-data-cache-v2';

// Static assets to cache on install
const STATIC_ASSETS = [
    '/guardpro/pwa/',
    '/guardpro/pwa/shifts',
    '/guardpro/pwa/tasks',
    '/guardpro/pwa/incidents',
    '/guardpro/pwa/settings',
    '/guardpro/static/src/css/mobile_dashboard.css',
    '/guardpro/static/src/css/tour_scanner.css',
    '/guardpro/static/src/js/gps_tracker.js',
    '/guardpro/static/src/js/mobile_navigation.js',
    '/guardpro/static/src/js/tour_scanner.js',
    '/guardpro/static/lib/jsQR.js',
    '/guardpro/static/src/img/icon-192x192.png',
    '/guardpro/static/src/img/icon-512x512.png',
];

// API routes that may be cached when offline (GET). Never cache
// notification/pending endpoints — stale "alert" payloads re-show
// forever and feel stuck after the server has already cleared them.
const CACHEABLE_API_ROUTES = [
    '/guardpro/api/guard/profile',
    '/guardpro/api/shifts/today',
    '/guardpro/api/tours/active',
    '/guardpro/api/checkpoints',
];

// API routes that should be queued when offline (POST/PUT requests)
const QUEUEABLE_API_ROUTES = [
    '/guardpro/api/incidents/create',
    '/guardpro/api/checkpoints/scan',
    '/guardpro/api/attendance/checkin',
    '/guardpro/api/attendance/checkout',
    '/guardpro/api/tours/checkpoint',
];

/**
 * Install event - cache static assets
 */
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[ServiceWorker] Caching static assets');
            return cache.addAll(STATIC_ASSETS.map(url => new Request(url, {
                credentials: 'same-origin'
            })));
        }).catch((error) => {
            console.error('[ServiceWorker] Cache installation failed:', error);
        })
    );
    self.skipWaiting();
});

/**
 * Activate event - clean up old caches
 */
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== DATA_CACHE_NAME) {
                        console.log('[ServiceWorker] Removing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

/**
 * Fetch event - handle network requests with offline support
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests for caching (they'll be queued if offline)
    if (request.method !== 'GET') {
        event.respondWith(handleNonGetRequest(request));
        return;
    }
    
    // Handle API requests
    if (url.pathname.startsWith('/guardpro/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Handle static assets and pages
    event.respondWith(handleStaticRequest(request));
});

/**
 * Handle GET requests for static content
 */
async function handleStaticRequest(request) {
    try {
        // Network first, fall back to cache
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        // Network failed, try cache
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return offline page for navigation requests
        if (request.mode === 'navigate') {
            const offlineCache = await caches.open(CACHE_NAME);
            const offlinePage = await offlineCache.match('/guardpro/pwa/');
            if (offlinePage) {
                return offlinePage;
            }
        }
        
        throw error;
    }
}

/**
 * Handle GET requests for API endpoints
 */
async function handleApiRequest(request) {
    const url = new URL(request.url);
    const isCacheable = CACHEABLE_API_ROUTES.some(route => url.pathname.includes(route));
    
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        // Cache successful API responses
        if (networkResponse.ok && isCacheable) {
            const cache = await caches.open(DATA_CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        // Network failed, try cache for cacheable routes
        if (isCacheable) {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                console.log('[ServiceWorker] Serving API from cache:', url.pathname);
                return cachedResponse;
            }
        }
        
        // Return error response
        return new Response(JSON.stringify({
            error: 'offline',
            message: 'You are offline. Data will sync when connection is restored.'
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * Handle POST/PUT/DELETE requests - queue when offline
 */
async function handleNonGetRequest(request) {
    const url = new URL(request.url);
    const isQueueable = QUEUEABLE_API_ROUTES.some(route => url.pathname.includes(route));
    
    try {
        // Try network first
        return await fetch(request);
    } catch (error) {
        // Network failed, queue if queueable
        if (isQueueable) {
            console.log('[ServiceWorker] Queueing offline request:', url.pathname);
            await queueRequest(request);
            
            // Return success response (data is queued)
            return new Response(JSON.stringify({
                success: true,
                queued: true,
                message: 'Data saved offline. Will sync when online.'
            }), {
                status: 202,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        
        // Not queueable, return error
        return new Response(JSON.stringify({
            error: 'offline',
            message: 'This action requires an internet connection.'
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * Queue a request for later synchronization
 */
async function queueRequest(request) {
    const db = await openDatabase();
    const tx = db.transaction(['offline_queue'], 'readwrite');
    const store = tx.objectStore('offline_queue');
    
    // Clone and serialize request
    const clonedRequest = request.clone();
    const body = await clonedRequest.text();
    
    const queueItem = {
        url: request.url,
        method: request.method,
        headers: Array.from(request.headers.entries()),
        body: body,
        timestamp: Date.now(),
        attempts: 0
    };
    
    await store.add(queueItem);
    await tx.complete;
    
    // Register background sync if available
    if ('sync' in self.registration) {
        await self.registration.sync.register('guardpro-sync');
    }
}

/**
 * Open IndexedDB database
 */
function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('GuardLinkOfflineDB', 1);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            
            // Create object stores
            if (!db.objectStoreNames.contains('offline_queue')) {
                const queueStore = db.createObjectStore('offline_queue', {
                    keyPath: 'id',
                    autoIncrement: true
                });
                queueStore.createIndex('timestamp', 'timestamp', { unique: false });
                queueStore.createIndex('url', 'url', { unique: false });
            }
            
            if (!db.objectStoreNames.contains('offline_data')) {
                const dataStore = db.createObjectStore('offline_data', {
                    keyPath: 'id',
                    autoIncrement: true
                });
                dataStore.createIndex('type', 'type', { unique: false });
                dataStore.createIndex('timestamp', 'timestamp', { unique: false });
            }
            
            if (!db.objectStoreNames.contains('sync_conflicts')) {
                const conflictStore = db.createObjectStore('sync_conflicts', {
                    keyPath: 'id',
                    autoIncrement: true
                });
                conflictStore.createIndex('resolved', 'resolved', { unique: false });
            }
        };
    });
}

/**
 * Background sync event - process queued requests
 */
self.addEventListener('sync', (event) => {
    if (event.tag === 'guardpro-sync') {
        console.log('[ServiceWorker] Background sync triggered');
        event.waitUntil(processSyncQueue());
    }
});

/**
 * Process queued requests
 */
async function processSyncQueue() {
    const db = await openDatabase();
    const tx = db.transaction(['offline_queue'], 'readonly');
    const store = tx.objectStore('offline_queue');
    const queue = await store.getAll();
    
    console.log(`[ServiceWorker] Processing ${queue.length} queued requests`);
    
    for (const item of queue) {
        try {
            // Reconstruct request
            const request = new Request(item.url, {
                method: item.method,
                headers: new Headers(item.headers),
                body: item.body,
                credentials: 'same-origin'
            });
            
            // Try to send
            const response = await fetch(request);
            
            if (response.ok) {
                // Success - remove from queue
                const deleteTx = db.transaction(['offline_queue'], 'readwrite');
                await deleteTx.objectStore('offline_queue').delete(item.id);
                console.log('[ServiceWorker] Successfully synced:', item.url);
            } else {
                // Server error - increment attempts
                item.attempts++;
                if (item.attempts >= 5) {
                    // Too many attempts - move to conflicts
                    await handleSyncConflict(db, item, 'max_attempts');
                } else {
                    // Update attempts
                    const updateTx = db.transaction(['offline_queue'], 'readwrite');
                    await updateTx.objectStore('offline_queue').put(item);
                }
            }
        } catch (error) {
            console.error('[ServiceWorker] Sync failed for:', item.url, error);
            // Keep in queue for next sync attempt
        }
    }
    
    // Notify clients about sync completion
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_COMPLETE',
            queueSize: queue.length
        });
    });
}

/**
 * Handle sync conflicts
 */
async function handleSyncConflict(db, item, reason) {
    const tx = db.transaction(['sync_conflicts'], 'readwrite');
    const store = tx.objectStore('sync_conflicts');
    
    await store.add({
        originalItem: item,
        reason: reason,
        timestamp: Date.now(),
        resolved: false
    });
    
    // Remove from queue
    const deleteTx = db.transaction(['offline_queue'], 'readwrite');
    await deleteTx.objectStore('offline_queue').delete(item.id);
    
    // Notify client
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_CONFLICT',
            conflict: {
                id: item.id,
                url: item.url,
                reason: reason
            }
        });
    });
}

/**
 * Message handler for client communication
 */
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map(cacheName => caches.delete(cacheName))
                );
            })
        );
    }
    
    if (event.data && event.data.type === 'GET_QUEUE_SIZE') {
        event.waitUntil(
            openDatabase().then(async (db) => {
                const tx = db.transaction(['offline_queue'], 'readonly');
                const queue = await tx.objectStore('offline_queue').getAll();
                
                event.ports[0].postMessage({
                    queueSize: queue.length
                });
            })
        );
    }
});

console.log('[ServiceWorker] Loaded successfully');

