import type { MetadataRoute } from "next";

// basePath لا يُطبَّق على المنيفست تلقائيًا — كل مسار هنا حرفي.
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";

// المنيفست مسار (route) لا صفحة، وفي وضع التصدير يلزمه تصريح صريح بأنه
// ثابت — وإلا أُسقط البناء كله: «force-static not configured».
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم",
    short_name: "الاستقراء الدلالي",
    description:
      "منصة بحثية موثقة لدراسة جذور ألفاظ القرآن الكريم واستقراء استعمالاتها، بنص موثق ببصمة وتحليل منسوب لمصادره.",
    start_url: `${BASE}/`,
    scope: `${BASE}/`,
    display: "standalone",
    orientation: "portrait-primary",
    dir: "rtl",
    lang: "ar",
    categories: ["education", "books", "reference"],
    // ألوان الهوية المعتمدة (2026-08-01) — تطابق رموز globals.css
    background_color: "#f7f5ef",
    theme_color: "#0d5c46",
    icons: [
      { src: `${BASE}/icon.svg`, sizes: "any", type: "image/svg+xml" },
      { src: `${BASE}/icon-192.png`, sizes: "192x192", type: "image/png" },
      { src: `${BASE}/icon-512.png`, sizes: "512x512", type: "image/png" },
      {
        src: `${BASE}/icon-maskable-512.png`,
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: "البحث بالجذر", short_name: "بحث", url: `${BASE}/` },
      { name: "فهرست المصحف", short_name: "المصحف", url: `${BASE}/mushaf` },
      { name: "بيان الأصول", short_name: "الأصول", url: `${BASE}/provenance` },
      // اختصار /claims يُسقط في الموقع الثابت: المسار غير موجود
      ...(STATIC
        ? []
        : [{ name: "الادعاءات البحثية", short_name: "الادعاءات", url: `${BASE}/claims` }]),
    ],
  };
}
