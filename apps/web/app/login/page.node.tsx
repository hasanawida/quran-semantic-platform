"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

const DEMO_ACCOUNTS = [
  { email: "admin@qsp.example", label: "مدير تقني + مسؤول نص" },
  { email: "reviewer1@qsp.example", label: "مراجع (مدير جودة)" },
  { email: "reviewer2@qsp.example", label: "مراجع لغوي" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تسجيل الدخول.");
    } finally {
      setBusy(false);
    }
  }

  function fillDemo(demoEmail: string) {
    setEmail(demoEmail);
    setPassword("demopass123");
  }

  return (
    <main id="main" className="container narrow">
      <section className="auth-card">
        <h1>تسجيل الدخول</h1>
        <form onSubmit={submit}>
          <label htmlFor="email">البريد الإلكتروني</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
          <label htmlFor="password">كلمة المرور</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          {error && (
            <div className="status-box error" role="alert">
              <p>{error}</p>
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "جارٍ الدخول…" : "دخول"}
          </button>
        </form>
        <p className="auth-alt">
          لا تملك حسابًا؟ <Link href="/register">سجّل الآن</Link>
        </p>

        <div className="demo-box">
          <p className="demo-title">حسابات تجريبية (بيئة التطوير)</p>
          <p className="demo-note">كلمة المرور للجميع: <code>demopass123</code></p>
          <div className="demo-list">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.email}
                type="button"
                className="ghost small"
                onClick={() => fillDemo(a.email)}
              >
                {a.email} — {a.label}
              </button>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
