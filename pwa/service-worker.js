// service-worker.js
const CACHE_NAME = 'Kukaya-v1.0';
const urlsToCache = [
  '/index.html',
  '/login.html',
  '/dashboard.html',
  '/css/style.css',
  '/js/api.js',
  '/js/auth.js',
  '/js/ui.js',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return (
        response ||
        fetch(event.request).catch(() =>
          caches.match('/offline.html') // optional offline fallback
        )
      );
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
});
