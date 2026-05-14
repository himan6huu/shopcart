const CACHE = 'shopcart-v1';
const STATIC = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  'https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap'
];

// Install: cache static assets
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network first, fallback to cache
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // Always go network-first for HTML pages and API calls
  if (e.request.headers.get('accept')?.includes('text/html') ||
      url.pathname.startsWith('/cart') ||
      url.pathname.startsWith('/coupon') ||
      url.pathname.startsWith('/wishlist')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match('/'))
    );
    return;
  }

  // Cache-first for static assets (CSS, JS, fonts, images)
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        if (res.ok && (url.pathname.startsWith('/static') || url.hostname.includes('fonts.g'))) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
