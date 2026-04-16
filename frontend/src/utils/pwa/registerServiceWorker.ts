const SW_URL = "/sw.js";

let hasReloadedAfterUpdate = false;

function isLocalPwaDebugHost(): boolean {
  return window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
}

function pwaDebugLog(message: string, details?: unknown): void {
  if (!isLocalPwaDebugHost()) return;

  if (details === undefined) {
    console.info(`[PWA] ${message}`);
    return;
  }

  console.info(`[PWA] ${message}`, details);
}

function activateUpdatedWorker(registration: ServiceWorkerRegistration): void {
  if (registration.waiting) {
    registration.waiting.postMessage({ type: "SKIP_WAITING" });
  }
}

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) {
    pwaDebugLog("Service worker disabled: non-production mode.");
    return;
  }

  if (!("serviceWorker" in navigator)) {
    pwaDebugLog("Service worker unsupported in current browser.");
    return;
  }

  window.addEventListener("beforeinstallprompt", () => {
    pwaDebugLog("beforeinstallprompt fired. Install action should be available in browser UI.");
  });

  window.addEventListener("appinstalled", () => {
    pwaDebugLog("Application installed.");
  });

  window.addEventListener("load", () => {
    void (async () => {
      try {
        const registration = await navigator.serviceWorker.register(SW_URL);
        pwaDebugLog("Service worker registered.", { scope: registration.scope });

        if (registration.waiting) {
          activateUpdatedWorker(registration);
          pwaDebugLog("Waiting service worker detected. skipWaiting requested.");
        }

        registration.addEventListener("updatefound", () => {
          pwaDebugLog("Service worker update detected.");
          const installingWorker = registration.installing;
          if (!installingWorker) return;

          installingWorker.addEventListener("statechange", () => {
            pwaDebugLog("Service worker state changed.", { state: installingWorker.state });
            if (installingWorker.state === "installed" && navigator.serviceWorker.controller) {
              activateUpdatedWorker(registration);
            }
          });
        });

        navigator.serviceWorker.addEventListener("controllerchange", () => {
          if (hasReloadedAfterUpdate) return;
          hasReloadedAfterUpdate = true;
          pwaDebugLog("Service worker controller changed. Reloading page once.");
          window.location.reload();
        });
      } catch (error) {
        pwaDebugLog("Service worker registration failed.", error);
      }
    })();
  });
}
