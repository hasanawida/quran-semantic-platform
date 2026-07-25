"use client";

import { useEffect, useState } from "react";

/** يسجّل عامل الخدمة ويُظهر شارة صريحة عند انقطاع الاتصال.
 *
 *  الشارة ليست زينة: حين ينقطع الاتصال قد تُخدَم بيانات من مخزن الجهاز،
 *  فيجب أن يعرف الباحث أن ما يراه ليس بالضرورة أحدث ما على الخادم. */
export default function AppShell() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);

    if (
      process.env.NODE_ENV === "production" &&
      "serviceWorker" in navigator
    ) {
      // بصمة البناء في العنوان — بها وحدها يُبطَل المخزن عند نشر جديد.
      //
      // كان عامل الخدمة يقرأ `self.__QSP_BUILD__` وهو **غير معرَّف في
      // المستودع كله**، فتبقى النسخة "qsp-v1" أبدًا ولا يُمسح مخزن
      // القشرة قط. والأثر ليس بطء تحديث فحسب: صفحةٌ مخزَّنة قد تُظهر
      // حالة مراجعة إصدارٍ أُبطل. (رصده فحص التصميم في 2026-07-25.)
      const build = process.env.NEXT_PUBLIC_BUILD_ID || "dev";
      // basePath لا يُطبَّق على هذا المسار: نصٌّ حرفي لا <Link>.
      const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
      navigator.serviceWorker
        .register(`${base}/sw.js?v=${encodeURIComponent(build)}`, {
          scope: `${base}/`,
        })
        .catch(() => {
          /* التسجيل ليس شرطًا لعمل الموقع */
        });
    }

    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;

  return (
    <div className="offline-bar" role="status">
      لا يوجد اتصال — قد تكون البيانات المعروضة من مخزن الجهاز وليست أحدث ما
      على الخادم.
    </div>
  );
}
