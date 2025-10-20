// ==================== Service Worker ====================

const CACHE_NAME = 'Kukaya-v1.0-' + new Date().getTime(); // versioned cache
const urlsToCache = [
  '/index.html',
  '/login.html',
  '/dashboard.html',
  '/offline.html',      // offline fallback
  '/css/style.css',
  '/js/api.js',
  '/js/auth.js',
  '/js/ui.js',
  '/manifest.json',
  '/favicon.ico',
];

// ==================== Install Event ====================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching app shell...');
      return cache.addAll(urlsToCache);
    })
  );
  self.skipWaiting(); // activate SW immediately
});

// ==================== Activate Event ====================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Removing old cache:', name);
            return caches.delete(name);
          })
      )
    )
  );
  self.clients.claim(); // take control immediately
});

// ==================== Fetch Event ====================
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request).then((cachedResponse) => {
        const fetchPromise = fetch(event.request)
          .then((networkResponse) => {
            // Don't cache opaque requests (cross-origin)
            if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          })
          .catch(() => {
            // Fallback to offline.html for navigation requests
            if (event.request.mode === 'navigate') {
              return caches.match('/offline.html');
            }
            return cachedResponse; // return cached if exists
          });

        return cachedResponse || fetchPromise;
      })
    )
  );
});

// ==================== Push Event (Optional) ====================
self.addEventListener('push', (event) => {
  const data = event.data?.json() || { title: 'Kukaya', body: 'New notification' };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/favicon.ico',
    })
  );
});

// ==================== Notification Click ====================
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      if (clients.openWindow) return clients.openWindow('/');
    })
  );
});
