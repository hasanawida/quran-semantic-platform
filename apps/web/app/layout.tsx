import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Amiri, Noto_Naskh_Arabic, Noto_Sans_Arabic } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf9f5" },
    { media: "(prefers-color-scheme: dark)", color: "#101713" },
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
        <a href="#main" className="skip-link">
          الانتقال إلى المحتوى
        </a>
        {/* شارة الحال — تظهر فوق كل صفحة. طلبتها مراجعة خارجية:
            زائرٌ يرى مصحفًا وتحليلًا يفترض الاعتماد ما لم يُقَل له غيره. */}
        <div className="beta-bar" role="note">
          نسخة بحثية <strong>تجريبية غير معتمدة</strong> — النص من مصدر
          موثق ببصمته، ولم يجتز بعدُ مراجعة المنصة المزدوجة. لا تُبنى
          عليها فتوى ولا تفسير دون أهل الاختصاص.
        </div>
        <AuthProvider>
          <AppShell />
          <Header />
          {children}
        </AuthProvider>
        <footer className="site-footer">
          <div className="container">
            <p>
              النص القرآني لا يولَّد آليًا، ويُعرض من إصدار موثق ومراجع فقط.
            </p>
            <p>جميع النتائج الآلية تُوسم وتُفصل عن المعتمد.</p>
            <nav className="footer-links" aria-label="روابط المنصة">
              <Link href="/methodology">المنهج والمصادر</Link>
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
