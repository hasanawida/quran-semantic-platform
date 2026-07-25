"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("كلمة المرور يجب ألا تقل عن 8 محارف.");
      return;
    }
    setBusy(true);
    try {
      await register(email, name, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الحساب.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="container narrow">
      <section className="auth-card">
        <h1>حساب جديد</h1>
        <p className="lead-sm">
          يُنشأ الحساب بدور «باحث». الأدوار الأعلى (مراجع، مسؤول نص) يمنحها المدير.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="name">الاسم</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
          />
          <label htmlFor="email">البريد الإلكتروني</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
          <label htmlFor="password">كلمة المرور (8 محارف فأكثر)</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          {error && (
            <div className="status-box error" role="alert">
              <p>{error}</p>
            </div>
          )}
          {/* الإقرار عند نقطة الجمع نفسها — لا في تذييل بعيد. وأهمّ ما
              فيه أن أثر العمل العلمي في سجل التدقيق لا يُمحى، ويجب أن
              يُعلم ذلك **قبل** التسجيل لا بعده. */}
          <p className="auth-consent">
            بإنشاء الحساب توافق على{" "}
            <Link href="/terms">شروط الاستعمال</Link> و
            <Link href="/privacy">سياسة الخصوصية</Link>. ننبّهك أن أثر عملك
            العلمي في سجل التدقيق <strong>يبقى بعد حذف حسابك</strong>،
            مرتبطًا بمعرّف لا باسمك — لأن المنصة مبناها على الإسناد.
          </p>
          <button className="primary" disabled={busy}>
            {busy ? "جارٍ الإنشاء…" : "إنشاء الحساب"}
          </button>
        </form>
        <p className="auth-alt">
          لديك حساب؟ <Link href="/login">سجّل الدخول</Link>
        </p>
      </section>
    </main>
  );
}
