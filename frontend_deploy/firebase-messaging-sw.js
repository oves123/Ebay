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
  
  if (payload.notification) {
    console.log('[firebase-messaging-sw.js] Handled automatically by Firebase SDK. Suppressing duplicate banner.');
    return;
  }

  // Fallback for data-only push messages:
  const title = payload.data?.title || '⚡ New eBay Snipe Deal!';
  const body = payload.data?.body || 'A new profitable watch was just listed.';
  const rawUrl = payload.data?.go || payload.data?.url || payload.data?.link || '';
  const itemId = payload.data?.item_id || payload.data?.id || (rawUrl.match(/\/(\d{9,14})/)?.[1]) || '';
  const directEbayUrl = itemId ? ('https://www.ebay.com/itm/' + itemId) : (rawUrl || 'https://www.ebay.com');
  const pwaRedirectUrl = `https://ebay-1e4.pages.dev/?go=${encodeURIComponent(directEbayUrl)}&item_id=${itemId}`;
  const icon = payload.data?.image_url || 'https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1.png';

  const notificationOptions = {
    body: body,
    icon: icon,
    badge: icon,
    image: icon,
    data: {
      url: directEbayUrl,
      link: pwaRedirectUrl,
      go: directEbayUrl,
      item_id: itemId,
      FCM_MSG: payload
    },
    tag: 'ebay-deal-' + (itemId || 'deal'),
    renotify: false,
    vibrate: [200, 100, 200, 100, 200]
  };

  self.registration.showNotification(title, notificationOptions);
});

// Handle notification click to open the exact eBay watch listing directly
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  let targetUrl = data.go ||
                  data.url ||
                  data.link ||
                  data.FCM_MSG?.fcmOptions?.link ||
                  data.FCM_MSG?.notification?.click_action ||
                  data.FCM_MSG?.data?.go ||
                  data.FCM_MSG?.data?.url ||
                  data.FCM_MSG?.data?.link ||
                  'https://www.ebay.com';

  // Extract clean eBay item ID
  let itemId = data.item_id ||
               (targetUrl.match(/\/itm\/(?:[^\/]+\/)?(\d{9,14})/)?.[1]) ||
               (targetUrl.match(/item_id=(\d{9,14})/)?.[1]) ||
               (targetUrl.match(/id=(\d{9,14})/)?.[1]);

  let directListingUrl = itemId ? ('https://www.ebay.com/itm/' + itemId) : targetUrl;
  let inScopeUrl = `https://ebay-1e4.pages.dev/?go=${encodeURIComponent(directListingUrl)}&item_id=${itemId || ''}`;

  console.log('[firebase-messaging-sw.js] Navigating directly to eBay listing:', directListingUrl);

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If a window is already open, navigate it to the in-scope redirect which immediately opens the eBay listing
      for (let client of windowClients) {
        if ('navigate' in client) {
          return client.navigate(inScopeUrl);
        }
      }
      // Otherwise open a new window pointing to the in-scope redirect
      if (clients.openWindow) {
        return clients.openWindow(inScopeUrl);
      }
    })
  );
});
