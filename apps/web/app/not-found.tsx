import Link from "next/link";

export const metadata = { title: "الصفحة غير موجودة" };

/** صفحة 404 عربية.
 *
 *  كان المشروع بلا `not-found.tsx` إطلاقًا، فيظهر 404 الافتراضي من Next
 *  **بالإنجليزية داخل قشرة `dir="rtl" lang="ar"`** — وهو أول ما يراه من
 *  يخطئ رابطًا. (رصده فحص تجربة الاستعمال في 2026-07-25.) */
export default function NotFound() {
  return (
    <main id="main" className="container narrow">
      <header className="page-head">
        <h1>الصفحة غير موجودة</h1>
      </header>
      <p className="page-lead">
        الرابط الذي طلبته لا يقابل صفحة في المنصة. لعلّه تغيّر، أو وقع في
        كتابته خطأ.
      </p>
      <ul className="plain-bullets">
        <li>
          <Link href="/mushaf">فهرست المصحف</Link> — السور والبحث في الآيات
        </li>
        <li>
          <Link href="/">البحث بالجذر</Link> — مواضع الجذر في المصحف
        </li>
        <li>
          <Link href="/methodology">المنهج والمصادر</Link> — من أين تأتي
          البيانات وكيف تُعالَج
        </li>
      </ul>
    </main>
  );
}
