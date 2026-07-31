"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/**
 * بيان الحال الكامل — في الزيارة الاولى وحدها.
 *
 * الوسم الدائم تحمله شارة «نسخة تجريبية» في الترويسة بتفصيلها المنبثق،
 * فلا يعود الشريط الكامل يعتلي كل صفحة في كل زيارة (مراجعة التصميم
 * 2026-08-01). الشفافية باقية بلا نقص: البيان الكامل يظهر لكل زائر جديد
 * حتى يغلقه بنفسه، والشارة حاضرة دائما.
 */
export default function FirstVisitNotice() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!window.localStorage.getItem("qsp-beta-ack")) setShow(true);
  }, []);

  if (!show) return null;
  return (
    <div className="beta-bar" role="note">
      نسخة بحثية <strong>تجريبية غير معتمدة</strong> — النص من مصدر موثق
      ببصمته، ولم يجتز بعدُ مراجعة المنصة المزدوجة. لا تُبنى عليها فتوى
      ولا تفسير دون أهل الاختصاص.{" "}
      <Link href="/methodology">التفاصيل</Link>
      <button
        type="button"
        className="ghost small beta-dismiss"
        onClick={() => {
          window.localStorage.setItem("qsp-beta-ack", "1");
          setShow(false);
        }}
      >
        فهمت
      </button>
    </div>
  );
}
