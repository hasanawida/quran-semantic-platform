/* عامل الخدمة — الموقع الثابت.

   قاعدتان تحكمان ما يُخزَّن:

   1. **البيانات مثبَّتة بالبناء.** كل ما تحت `data/v1/` وُلِّد وقت البناء
      وبصمته في `manifest.json`، فلا يمكن أن يكون المخزَّن أقدم من
      «الخادم». المخزن أولًا، والشبكة لـ`manifest.json` وحده — به يُعرف
      أن لقطةً جديدة نُشرت.
   2. **لا شيء يُكتب.** الموقع بلا مصادقة ولا كتابة، فحُذف فرع
      `/api/v1/` و`isAuthRequest` وفحص ترويسة `authorization`: شيفرة
      ميتة تُطمئن زورًا.

   القاعدة تُشتق من موضع الملف نفسه، فتعمل على موقع المشروع
   (`/quran-semantic-platform/`) وموقع المستخدم (`/`) بلا تهيئة. */

const SCOPE = new URL("./", self.location.href);
const BASE = SCOPE.pathname;

// بصمة البناء تصل في عنوان التسجيل: `sw.js?v=<build>`.
// إن لم تُمرَّر NEXT_PUBLIC_BUILD_ID في سير النشر بقيت "dev" فبقيت
// النسخة qsp-dev أبدًا ولم يُبطَل مخزن القشرة قط عبر النشرات — وهو
// العطب المصحَّح في 2026-07-25 بعينه. سير Pages يمرّرها من github.sha.
const BUILD = new URL(self.location.href).searchParams.get("v") || "dev";
const VERSION = `qsp-${BUILD}`;
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;

const SHELL_ASSETS = [
  "",
  "mushaf/",
  "methodology/",
  "privacy/",
  "terms/",
  "manifest.webmanifest",
  "icon.svg",
  "icon-192.png",
  "icon-512.png",
  "apple-touch-icon.png",
  // بيانات القشرة: بدونها لا يعمل شيء بلا اتصال (2,536 بايتًا مضغوطة)
  "data/v1/manifest.json",
  "data/v1/meta.json",
  "data/v1/surahs.json",
  "data/v1/normspec.json",
].map((path) => BASE + path);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(async (cache) => {
      // **لا `addAll`**: هي ذرّية، فأصل واحد مفقود يُفرغ المخزن كله
      // صامتًا. هنا كل أصل على حدة، والناقص يُسجَّل ولا يُبطل الباقي.
      const results = await Promise.allSettled(
        SHELL_ASSETS.map((url) =>
          cache.add(new Request(url, { cache: "reload" }))
        )
      );
      const missing = SHELL_ASSETS.filter(
        (_url, i) => results[i].status === "rejected"
      );
      if (missing.length) console.warn("[qsp] أصول قشرة لم تُخزَّن:", missing);
      await self.skipWaiting();
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("qsp-") && !key.startsWith(VERSION))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) cache.put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
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
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith(BASE)) return;

  // بيان اللقطة: الشبكة أولًا — به وحده يُعرف أن نشرةً جديدة صدرت
  if (url.pathname === `${BASE}data/v1/manifest.json`) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  // بقية البيانات: المخزن أولًا — مثبَّتة بالبناء وبصمتها في البيان
  if (url.pathname.startsWith(`${BASE}data/v1/`)) {
    event.respondWith(cacheFirst(request, DATA_CACHE));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (await cache.match(request)) || (await cache.match(BASE));
      })
    );
    return;
  }

  event.respondWith(staleWhileRevalidate(request));
});
