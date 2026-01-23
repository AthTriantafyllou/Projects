self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", () => {
  self.clients.claim();
});

/* 🔔 PUSH HANDLING (ADD THIS) */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data.json();
  } catch {}

  const title = data.title || "Streaks";
  const options = {
    body: data.body || "Don’t miss today!",
    icon: "/streaks/icons/icon-192.png",
    badge: "/streaks/icons/icon-192.png",
    data: {
      url: data.url || "/streaks/pages/home.html"
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  event.waitUntil(
    clients.openWindow(
      event.notification.data.url
    )
  );
});
