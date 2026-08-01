"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

// الموقع الثابت لا يحوي صفحات المصادقة والكتابة: ملفاتها
// `page.node.tsx` فتنعدم من البناء. فرابطٌ إليها يعطي 404.
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";

import { useAuth } from "../lib/auth";

/** علامة المنصة المعتمدة (2026-08-01): نجمة ثمانية بإطار ذهبي، في
 *  وسطها مصحف مفتوح تخرج من أسفله جذور متفرعة — الجذر وما تفرع عنه.
 *  رسمٌ متجه لا صورة: الاسم يبقى نصًّا صحيح الإملاء يقرؤه قارئ الشاشة،
 *  والرسم لا يبهت عند التكبير. والأصل الكامل في app/icon.svg. */
function RootMark() {
  return (
    <svg width="34" height="34" viewBox="0 0 512 512" aria-hidden="true">
      <defs>
        <linearGradient id="hdGold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F0D68A" />
          <stop offset="0.5" stopColor="#D9B872" />
          <stop offset="1" stopColor="#B48A3C" />
        </linearGradient>
      </defs>
      <rect x="106" y="106" width="300" height="300" rx="10" fill="#0D5C46" />
      <rect
        x="106"
        y="106"
        width="300"
        height="300"
        rx="10"
        fill="#0D5C46"
        transform="rotate(45 256 256)"
      />
      <rect
        x="106"
        y="106"
        width="300"
        height="300"
        rx="10"
        fill="none"
        stroke="url(#hdGold)"
        strokeWidth="13"
      />
      <rect
        x="106"
        y="106"
        width="300"
        height="300"
        rx="10"
        fill="none"
        stroke="url(#hdGold)"
        strokeWidth="13"
        transform="rotate(45 256 256)"
      />
      {/* المصحف المفتوح — الإحداثيات نفسها التي في app/icon.svg */}
      <path
        d="M256 188 C232 172 206 166 176 166 L176 248 C206 248 232 254 256 270
           C280 254 306 248 336 248 L336 166 C306 166 280 172 256 188 Z"
        fill="#F7F5EF"
        stroke="url(#hdGold)"
        strokeWidth="10"
        strokeLinejoin="round"
      />
      <path d="M256 188 V270" stroke="#B48A3C" strokeWidth="6" />
      {/* الجذور: أصلٌ واحد تتفرع منه ستة فروع */}
      <g fill="none" stroke="url(#hdGold)" strokeWidth="10" strokeLinecap="round">
        <path d="M256 270 V300" />
        <path d="M256 300 C256 318 206 322 176 344" />
        <path d="M256 300 C256 318 306 322 336 344" />
        <path d="M256 300 C256 324 214 344 198 376" />
        <path d="M256 300 C256 324 298 344 314 376" />
        <path d="M256 300 V386" />
      </g>
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
