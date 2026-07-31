"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

// الموقع الثابت لا يحوي صفحات المصادقة والكتابة: ملفاتها
// `page.node.tsx` فتنعدم من البناء. فرابطٌ إليها يعطي 404.
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";

import { useAuth } from "../lib/auth";

/** علامة المنصة: صفحة مصحف مجردة تتفرع منها ثلاثة فروع من اصل واحد —
 *  الجذر ومشتقاته. رسم خطي هادئ يصلح ايقونة، لا زخرفة. */
function RootMark() {
  return (
    <svg
      width="30"
      height="30"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 3h11a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H5z" />
      <path d="M5 3v18" />
      {/* الاصل الواحد وفروعه الثلاثة */}
      <path d="M12 17v-4" />
      <path d="M12 13c0-2.2-2.4-2.6-2.4-4.6" />
      <path d="M12 13c0-2.2 2.4-2.6 2.4-4.6" />
      <path d="M12 13V7.5" />
      <circle cx="9.6" cy="7.6" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="12" cy="6.7" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="14.4" cy="7.6" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

const MANAGE_ROLES = [
  "text_officer",
  "tech_admin",
  "quality_manager",
  "linguistic_reviewer",
  "sharia_reviewer",
];

/** مسارات القراءة الخمسة — تظهر في الترويسة وفي شريط الهاتف السفلي */
const NAV = [
  { href: "/", label: "البحث بالجذر" },
  { href: "/word", label: "بحث الكلمة" },
  { href: "/mushaf", label: "المصحف" },
  { href: "/compare", label: "مقارنة الجذور" },
  { href: "/morphology", label: "البحث الصرفي" },
];

type ThemeChoice = "auto" | "light" | "dark";
const THEME_LABELS: Record<ThemeChoice, string> = {
  auto: "تلقائي",
  light: "فاتح",
  dark: "داكن",
};

export default function Header() {
  const { user, loading, logout, hasRole } = useAuth();
  const pathname = usePathname();
  const [theme, setTheme] = useState<ThemeChoice>("auto");

  // الاختيار محفوظ في الجهاز، ويطبق قبل الرسم بسكربت layout — هنا فقط
  // نقرا الحال لنعرض التسمية الصحيحة على الزر
  useEffect(() => {
    const saved = window.localStorage.getItem("qsp-theme");
    if (saved === "light" || saved === "dark") setTheme(saved);
  }, []);

  function cycleTheme() {
    const next: ThemeChoice =
      theme === "auto" ? "dark" : theme === "dark" ? "light" : "auto";
    setTheme(next);
    if (next === "auto") {
      window.localStorage.removeItem("qsp-theme");
      delete document.documentElement.dataset.theme;
    } else {
      window.localStorage.setItem("qsp-theme", next);
      document.documentElement.dataset.theme = next;
    }
  }

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="site-header">
      <nav className="container" aria-label="التنقل الرئيسي">
        <Link href="/" className="brand">
          <RootMark />
          <span className="brand-text">
            <span className="brand-name">الاستقراء الدلالي</span>
            <span className="brand-sub">جذور ألفاظ القرآن الكريم</span>
          </span>
        </Link>

        {/* شارة الحال بدل الشريط الكامل: الوسم حاضر في كل صفحة، وتفصيله
            خلف نقرة — فلا يسيطر الانذار على هوية الموقع (قرار المالك) */}
        <details className="beta-badge">
          <summary>نسخة تجريبية ⓘ</summary>
          <div className="beta-pop">
            <p>
              نسخة بحثية غير معتمدة: النص القرآني من مصدر موثق ببصمته،
              والتحليل والمعاجم مستوردة موسومة بحالها، ولم يجتز شيء منها
              مراجعة المنصة المزدوجة بعد. لا تُبنى عليها فتوى ولا تفسير
              دون أهل الاختصاص.
            </p>
            <p>
              <Link href="/methodology">المنهج</Link> ·{" "}
              <Link href="/provenance">بيان الأصول</Link>
            </p>
          </div>
        </details>

        <div className="nav-actions">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="nav-link"
              aria-current={isActive(item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
          {!STATIC && (
            <Link href="/claims" className="nav-link">
              الادعاءات
            </Link>
          )}
          {!STATIC && user && (
            <Link href="/review" className="nav-link">
              صندوق المراجعة
            </Link>
          )}
          {!STATIC && hasRole(...MANAGE_ROLES) && (
            <Link href="/admin/versions" className="nav-link">
              إصدارات النص
            </Link>
          )}
          <button
            type="button"
            className="ghost small theme-toggle"
            onClick={cycleTheme}
            title="الوضع: تلقائي ← داكن ← فاتح"
          >
            الوضع: {THEME_LABELS[theme]}
          </button>
          {/* في الموقع الثابت لا صفحة دخول أصلًا، وuser فارغ دائمًا —
              فبلا هذا الشرط يظهر زرّ «دخول» ويعطي 404. */}
          {STATIC ? null : loading ? null : user ? (
            <div className="user-chip">
              <span className="user-name">{user.display_name}</span>
              <Link href="/account" className="nav-link">
                حسابي
              </Link>
              <button type="button" className="ghost small" onClick={logout}>
                خروج
              </button>
            </div>
          ) : (
            <Link href="/login" className="nav-link primary-link">
              دخول
            </Link>
          )}
        </div>
      </nav>

      {/* شريط الهاتف السفلي: اهم المسارات بابهام واحد بلا تمرير افقي */}
      <nav className="bottom-nav" aria-label="التنقل السفلي">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive(item.href) ? "page" : undefined}
          >
            {item.label.replace("البحث بالجذر", "الجذور").replace("بحث الكلمة", "الكلمات").replace("مقارنة الجذور", "مقارنة").replace("البحث الصرفي", "الصرف")}
          </Link>
        ))}
      </nav>
    </header>
  );
}
