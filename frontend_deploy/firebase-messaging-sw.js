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
  
  // DEDUPLICATION FIX: If payload.notification exists, the Firebase SDK / browser
  // handles displaying the notification automatically. Calling self.registration.showNotification()
  // creates a duplicate banner on mobile and desktop!
  if (payload.notification) {
    console.log('[firebase-messaging-sw.js] Handled automatically by Firebase SDK. Suppressing duplicate banner.');
    return;
  }

  // Fallback for data-only push messages:
  const title = payload.data?.title || '⚡ New eBay Snipe Deal!';
  const body = payload.data?.body || 'A new profitable watch was just listed.';
  const linkUrl = payload.data?.url || payload.data?.link || 'https://ebay-1e4.pages.dev/';
  const icon = payload.data?.image_url || 'https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1.png';
  const itemId = payload.data?.item_id || payload.data?.id || (linkUrl.match(/\/(\d{9,14})/)?.[1]) || 'deal';

  const notificationOptions = {
    body: body,
    icon: icon,
    badge: icon,
    image: icon,
    data: {
      url: linkUrl,
      link: linkUrl,
      FCM_MSG: payload
    },
    tag: 'ebay-deal-' + itemId,
    renotify: false,
    vibrate: [200, 100, 200, 100, 200]
  };

  self.registration.showNotification(title, notificationOptions);
});

// Handle notification click to open the eBay listing in the native eBay App on iOS and Android
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  let targetUrl = data.launcher_url ||
                  data.link ||
                  data.url ||
                  data.FCM_MSG?.fcmOptions?.link ||
                  data.FCM_MSG?.notification?.click_action ||
                  data.FCM_MSG?.data?.launcher_url ||
                  data.FCM_MSG?.data?.link ||
                  data.FCM_MSG?.data?.url ||
                  'https://ebay-1e4.pages.dev/';

  // Extract clean eBay item ID
  let itemId = data.item_id ||
               data.id ||
               data.FCM_MSG?.data?.item_id ||
               (targetUrl.match(/\/itm\/(?:[^\/]+\/)?(\d{9,14})/)?.[1]) ||
               (targetUrl.match(/id=(\d{9,14})/)?.[1]);

  let launchUrl = targetUrl;
  if (itemId && !targetUrl.includes('open.html')) {
    launchUrl = `https://ebay-1e4.pages.dev/open.html?id=${itemId}&url=${encodeURIComponent(targetUrl)}`;
  }

  console.log('[firebase-messaging-sw.js] Notification clicked! Launching:', launchUrl);

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If a window is already open on our domain, navigate it
      for (let client of windowClients) {
        if ('focus' in client && 'navigate' in client && client.url.includes('ebay-1e4.pages.dev')) {
          client.navigate(launchUrl);
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(launchUrl);
      }
    })
  );
});
