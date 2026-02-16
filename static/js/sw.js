// SkillsFlow Service Worker for WBL Offline Support
// Version 1.0.0

const CACHE_NAME = 'skillsflow-wbl-v1';
const OFFLINE_URL = '/offline/';

// Assets to cache for offline use
const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/js/main.js',
    '/offline/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Service Worker: Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Deleting old cache', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        // For POST requests (like attendance submission), handle specially
        if (event.request.method === 'POST' && event.request.url.includes('/attendance/')) {
            event.respondWith(handleAttendanceSubmission(event.request));
            return;
        }
        return;
    }
    
    // Handle navigation requests
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }
    
    // Network first strategy for API calls
    if (event.request.url.includes('/api/') || event.request.url.includes('/portals/')) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // Clone and cache successful responses
                    if (response.ok) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(() => caches.match(event.request))
        );
        return;
    }
    
    // Cache first strategy for static assets
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request).then((response) => {
                    // Cache new static assets
                    if (response.ok) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                });
            })
    );
});

// Handle offline attendance submission
async function handleAttendanceSubmission(request) {
    try {
        // Try to submit online first
        const response = await fetch(request.clone());
        return response;
    } catch (error) {
        // If offline, store in IndexedDB for later sync
        const formData = await request.clone().formData();
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });
        
        await storeOfflineAttendance(data);
        
        // Return a synthetic response
        return new Response(JSON.stringify({
            success: true,
            offline: true,
            message: 'Attendance saved offline. Will sync when online.'
        }), {
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Store attendance data in IndexedDB
async function storeOfflineAttendance(data) {
    const db = await openDatabase();
    const tx = db.transaction('pendingAttendance', 'readwrite');
    const store = tx.objectStore('pendingAttendance');
    
    await store.add({
        ...data,
        timestamp: Date.now(),
        synced: false
    });
}

// Open IndexedDB
function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('SkillsFlowWBL', 1);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            
            // Create object stores
            if (!db.objectStoreNames.contains('pendingAttendance')) {
                db.createObjectStore('pendingAttendance', { keyPath: 'id', autoIncrement: true });
            }
            
            if (!db.objectStoreNames.contains('cachedData')) {
                db.createObjectStore('cachedData', { keyPath: 'key' });
            }
        };
    });
}

// Background sync for pending attendance
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-attendance') {
        event.waitUntil(syncPendingAttendance());
    }
});

// Sync pending attendance records
async function syncPendingAttendance() {
    const db = await openDatabase();
    const tx = db.transaction('pendingAttendance', 'readwrite');
    const store = tx.objectStore('pendingAttendance');
    
    const records = await store.getAll();
    
    for (const record of records) {
        if (!record.synced) {
            try {
                const response = await fetch('/portals/mentor/attendance/submit/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(record)
                });
                
                if (response.ok) {
                    // Mark as synced or delete
                    await store.delete(record.id);
                }
            } catch (error) {
                console.log('Sync failed for record:', record.id);
            }
        }
    }
}

// Listen for messages from the page
self.addEventListener('message', (event) => {
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'SYNC_NOW') {
        syncPendingAttendance();
    }
});
