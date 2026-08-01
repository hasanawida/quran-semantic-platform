import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Amiri, Noto_Naskh_Arabic, Noto_Sans_Arabic } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
import FirstVisitNotice from "./components/FirstVisitNotice";
import Header from "./components/Header";
import { AuthProvider } from "./lib/auth";

const quranFont = Amiri({
  subsets: ["arabic"],
  weight: ["400", "700"],
  variable: "--font-quran",
  display: "swap",
});

const bodyFont = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

const uiFont = Noto_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ui",
  display: "swap",
});

const SITE_DESCRIPTION =
  "منصة بحثية موثقة لدراسة جذور ألفاظ القرآن الكريم: نص موثق ببصمة، تحليل منسوب لمصادره، مراجعة مستقلة، وتقارير قابلة للتتبع.";

// قياس الاستعمال: يُفعَّل بضبط NEXT_PUBLIC_UMAMI_ID وقت البناء وحده.
// بلا معرّف لا يُشحن نصٌّ خارجي البتة — وهذا هو الوضع الافتراضي.
const UMAMI_ID = process.env.NEXT_PUBLIC_UMAMI_ID;
const UMAMI_HOST =
  process.env.NEXT_PUBLIC_UMAMI_HOST ?? "https://cloud.umami.is";

export const metadata: Metadata = {
  title: {
    default: "منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم",
    template: "%s — منصة الاستقراء الدلالي",
  },
  description: SITE_DESCRIPTION,
  applicationName: "منصة الاستقراء الدلالي",
  appleWebApp: {
    capable: true,
    title: "الاستقراء الدلالي",
    statusBarStyle: "default",
  },
  formatDetection: { telephone: false, date: false, address: false },
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    locale: "ar_AR",
    siteName: "منصة الاستقراء الدلالي",
    title: "منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم",
    description: SITE_DESCRIPTION,
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // ألوان الهوية المعتمدة — تطابق --color-bg في globals.css
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f5ef" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1210" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${quranFont.variable} ${bodyFont.variable} ${uiFont.variable}`}
    >
      <body>
        {/* قياس الاستعمال — معطَّل ما لم يُضبط المعرّف وقت البناء.
            مصرَّحٌ به كاملًا في /privacy: يُرسل مسار الصفحة (ومنه
            السورة والآية والجذر المبحوث)، ومدة الزيارة، والمُحيل،
            والدولة والجهاز. بلا كوكيز وبلا تخزين IP لدى الخدمة.
            وتعطيله يكفي فيه حذف المتغيّر من سير النشر — لا تعديل شيفرة. */}
        {UMAMI_ID && (
          <script
            defer
            src={UMAMI_HOST + "/script.js"}
            data-website-id={UMAMI_ID}
          />
        )}
        {/* اختيار الوضع المحفوظ يطبق قبل الرسم — فلا ومضة لون خاطئ */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              'try{var t=localStorage.getItem("qsp-theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}',
          }}
        />
        <a href="#main" className="skip-link">
          الانتقال إلى المحتوى
        </a>
        {/* بيان الحال الكامل في الزيارة الاولى، والوسم الدائم شارة
            الترويسة بتفصيلها — الوسم فريضة والضجيج ليس منها */}
        <FirstVisitNotice />
        <AuthProvider>
          <AppShell />
          <Header />
          {children}
        </AuthProvider>
        <footer className="site-footer">
          <div className="container">
            {/* جملة واحدة بدل فقرتي منهج تتكرران في كل صفحة —
                والتفصيل في صفحة المنهج المربوطة تحتها مباشرة */}
            <p>
              النص القرآني من إصدار موثق لا يولَّد آليًا، وكل نتيجة آلية
              تُوسم وتُفصل عن المعتمد.
            </p>
            <nav className="footer-links" aria-label="روابط المنصة">
              <Link href="/methodology">المنهج والمصادر</Link>
              <Link href="/provenance">بيان الأصول</Link>
              <Link href="/lexicon-sources">مصادر المعاجم</Link>
              <Link href="/install">تثبيت التطبيق</Link>
              <Link href="/privacy">سياسة الخصوصية</Link>
              <Link href="/terms">شروط الاستعمال</Link>
            </nav>
            <p className="footer-credit">
              تطوير{" "}
              <a
                href="https://github.com/hasanawida"
                target="_blank"
                rel="noreferrer noopener"
              >
                حسن عويضة
              </a>{" "}
              · شيفرة مفتوحة تحت{" "}
              <a
                href="https://github.com/hasanawida/quran-semantic-platform"
                target="_blank"
                rel="noreferrer noopener"
              >
                AGPL-3.0
              </a>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
