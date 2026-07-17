const STATIC_PREFIX = '/assets/'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil((async () => {
  for (const name of await caches.keys()) {
    if (name !== 'family-learning-static-v2') await caches.delete(name)
  }
  await self.clients.claim()
})()))

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  // Private API, media, and imported files are deliberately never cached.
  if (event.request.method !== 'GET' || !url.pathname.startsWith(STATIC_PREFIX)) return
  event.respondWith(caches.open('family-learning-static-v2').then(async (cache) => {
    const response = await fetch(event.request)
    if (response.ok) cache.put(event.request, response.clone())
    return response
  }).catch(async () => (await caches.open('family-learning-static-v2')).match(event.request)))
})
