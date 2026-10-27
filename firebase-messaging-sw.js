// Firebase Messaging Service Worker
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-messaging-compat.js');

// Initialize the Firebase app in the service worker
firebase.initializeApp({
  apiKey: "AIzaSyCo9eYtPKHoqYLjHQGTgIAeorYZjXEVaqU",
  authDomain: "ebay-sniper-alerts.firebaseapp.com",
  projectId: "ebay-sniper-alerts",
  storageBucket: "ebay-sniper-alerts.firebasestorage.app",
  messagingSenderId: "1092042612715",
  appId: "1:1092042612715:web:e129e0fff61062849643ae",
  measurementId: "G-X2V0MSH122"
});

const messaging = firebase.messaging();

// Handle background push messages
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message: ', payload);
  
  const title = payload.notification?.title || payload.data?.title || '⚡ New eBay Snipe Deal!';
  const body = payload.notification?.body || payload.data?.body || 'A new profitable watch was just listed.';
  const linkUrl = payload.data?.url || payload.data?.link || payload.notification?.click_action || 'https://ebay-1e4.pages.dev/';
  const icon = payload.notification?.icon || payload.data?.image_url || 'https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1.png';

  const notificationOptions = {
    body: body,
    icon: icon,
    badge: icon,
    data: {
      url: linkUrl
    },
    tag: 'ebay-sniper-' + Date.now(),
    renotify: true,
    vibrate: [200, 100, 200, 100, 200]
  };

  self.registration.showNotification(title, notificationOptions);
});

// Handle notification click to open the eBay listing URL directly
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : 'https://ebay-1e4.pages.dev/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if (client.url === targetUrl && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
