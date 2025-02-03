self.addEventListener('install', function(event) {
  console.log('Service Worker installing.');
  // Optionally, cache assets here for offline use.
});

self.addEventListener('fetch', function(event) {
  // For now, simply allow normal network requests
}); 