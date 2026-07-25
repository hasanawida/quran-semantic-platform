/* عامل الخدمة — تشغيل المنصة على الهاتف بلا اتصال دائم.

   قاعدتان تحكمان ما يُخزَّن:

   1. **لا يُخزَّن ما يُكتب.** الطلبات غير GET وكل ما يتعلق بالمصادقة
      لا تمر على المخزن إطلاقًا، فلا تُعاد استجابة صلاحية قديمة.
   2. **الشبكة أولًا للبيانات.** النص والتحليل يُطلبان من الخادم أولًا،
      والمخزن احتياط عند انقطاع الاتصال. الواجهة تُظهر شارة «بلا اتصال»
      حتى لا يُظن المعروض هو الأحدث.
*/

// يُحدَّث مع كل نشر (يُحقن وقت البناء عبر BUILD_ID عند توفره)
const VERSION = "qsp-" + (self.__QSP_BUILD__ || "v1");
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;

const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/icon.svg",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !key.startsWith(VERSION))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isAuthRequest(url) {
  return url.pathname.includes("/auth/") || url.pathname.includes("/admin/");
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // المصادقة والإدارة: لا تخزين ولا اعتراض
  if (isAuthRequest(url)) return;

  // أي طلب يحمل تفويضًا ردُّه خاص بحامل الرمز: لا يوضع في مخزن مشترك
  // على القرص يبقى بعد الخروج ويُعرض لمستخدم آخر على الجهاز نفسه.
  if (request.headers.get("authorization")) return;

  // تنقّل بين الصفحات: الشبكة أولًا، وقشرة التطبيق احتياطًا
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (await cache.match(request)) || (await cache.match("/"));
      })
    );
    return;
  }

  // بيانات المنصة (نص، جذور، تحليل، بيان أصول)
  if (url.pathname.includes("/api/v1/")) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  // أصول ثابتة من نفس الأصل
  if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
