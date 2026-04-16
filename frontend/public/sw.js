const CACHE_VERSION = "v1";
const CACHE_PREFIX = "nutrition-planner-";
const APP_SHELL_CACHE = `nutrition-planner-app-shell-${CACHE_VERSION}`;
const STATIC_RUNTIME_CACHE = `nutrition-planner-static-${CACHE_VERSION}`;

const APP_SHELL_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/pwa-192.png",
  "/icons/pwa-512.png",
  "/icons/pwa-maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(APP_SHELL_CACHE)
      .then((cache) => cache.addAll(APP_SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames
          .filter(
            (cacheName) =>
              cacheName.startsWith(CACHE_PREFIX) &&
              cacheName !== APP_SHELL_CACHE &&
              cacheName !== STATIC_RUNTIME_CACHE,
          )
          .map((cacheName) => caches.delete(cacheName)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(handleNavigationRequest(request));
    return;
  }

  if (url.origin !== self.location.origin) {
    return;
  }

  const shouldHandleStaticAsset =
    request.destination === "style" ||
    request.destination === "script" ||
    request.destination === "worker" ||
    request.destination === "font" ||
    request.destination === "image" ||
    url.pathname.startsWith("/assets/");

  if (shouldHandleStaticAsset) {
    event.respondWith(staleWhileRevalidateStatic(request));
  }
});

async function handleNavigationRequest(request) {
  try {
    const networkResponse = await fetch(request);
    const appShellCache = await caches.open(APP_SHELL_CACHE);
    appShellCache.put(request, networkResponse.clone());
    return networkResponse;
  } catch {
    const cachedRoute = await caches.match(request);
    if (cachedRoute) {
      return cachedRoute;
    }

    const cachedIndex = await caches.match("/index.html");
    if (cachedIndex) {
      return cachedIndex;
    }

    return new Response("Offline", {
      status: 503,
      statusText: "Offline",
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

async function staleWhileRevalidateStatic(request) {
  const staticCache = await caches.open(STATIC_RUNTIME_CACHE);
  const cached = await staticCache.match(request);

  const networkPromise = fetch(request)
    .then((response) => {
      if (response.ok) {
        staticCache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => undefined);

  if (cached) {
    return cached;
  }

  const networkResponse = await networkPromise;
  if (networkResponse) {
    return networkResponse;
  }

  return new Response("Offline", {
    status: 503,
    statusText: "Offline",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
