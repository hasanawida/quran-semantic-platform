import type { NextConfig } from "next";

// وضع التصدير الثابت — يُفعَّل من سير النشر وحده (QSP_STATIC=1).
// لا تُغيَّر القيم الافتراضية: Dockerfile ينسخ .next/standalone،
// وci.yml يبني بلا متغيرات فيتوقع .next لا out/.
const STATIC = process.env.QSP_STATIC === "1";

// مسار القاعدة على GitHub Pages:
//   موقع مشروع  → "/quran-semantic-platform"  (نطاق عامل الخدمة محصور)
//   موقع مستخدم → ""                          (hasanawida.github.io)
// يُمرَّر أيضًا بـNEXT_PUBLIC_BASE_PATH ليقرأه manifest.ts وlayout.tsx،
// فـNext يبدّل <Link> و_next/* تلقائيًا ولا يمسّ النصوص الحرفية.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

// مجلد بناء منفصل عند الحاجة: بناء الإنتاج على .next المشغول بخادم
// التطوير يُفسده فتُخدم حزمة عميل قديمة صامتة — عطب سبق وقوعه هنا.
const DIST = process.env.QSP_DIST;

const nextConfig: NextConfig = {
  output: STATIC ? "export" : "standalone",
  ...(DIST ? { distDir: DIST } : {}),
  ...(STATIC && BASE_PATH
    ? { basePath: BASE_PATH, assetPrefix: BASE_PATH }
    : {}),
  // مجلد لكل مسار (mushaf/2/index.html) — يوافق ما تخدمه Pages بلا إعادة كتابة
  trailingSlash: STATIC,
  // إخفاء الصفحات التي تحتاج كتابة أو مصادقة: في وضع التصدير لا يطابق
  // page.node.tsx نمط page.<ext> فينعدم المسار من البناء أصلًا، ولا تُشحن
  // شيفرته إلى المتصفح. وخارج التصدير تعمل الصفحات كما هي.
  pageExtensions: STATIC
    ? ["tsx", "ts"]
    : ["node.tsx", "node.ts", "tsx", "ts"],
};

export default nextConfig;
