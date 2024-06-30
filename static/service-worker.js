
self.addEventListener('install', function(event) {
    self.skipWaiting();
});

self.addEventListener('fetch', function(event) {
    event.respondWith(fetch(event.request).then(function(response) {
        return response;
    }).catch(function() {
        return caches.match(event.request).then(function(response) {
            return response || caches.match('/offline.html');
        });
    }));
});