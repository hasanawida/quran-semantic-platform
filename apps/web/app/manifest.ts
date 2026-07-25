import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم",
    short_name: "الاستقراء الدلالي",
    description:
      "منصة بحثية موثقة لدراسة جذور ألفاظ القرآن الكريم واستقراء استعمالاتها، بنص موثق ببصمة وتحليل منسوب لمصادره.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    dir: "rtl",
    lang: "ar",
    categories: ["education", "books", "reference"],
    background_color: "#faf9f5",
    theme_color: "#1d5c42",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: "البحث بالجذر", short_name: "بحث", url: "/" },
      { name: "بيان الأصول", short_name: "الأصول", url: "/provenance" },
      { name: "الادعاءات البحثية", short_name: "الادعاءات", url: "/claims" },
    ],
  };
}
