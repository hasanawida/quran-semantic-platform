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
      navigator.serviceWorker.register("/sw.js").catch(() => {
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
