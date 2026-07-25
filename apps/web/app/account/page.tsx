"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, request } from "../lib/api";
import { ROLE_LABELS, useAuth } from "../lib/auth";

type Session = {
  chain_id: string;
  created_at: string;
  expires_at: string;
  user_agent: string | null;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString("ar", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

export default function AccountPage() {
  const { user, loading, logout } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      setSessions(await request<Session[]>("/auth/sessions", { auth: true }));
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر جلب الجلسات.");
    }
  }, [user]);

  useEffect(() => {
    load();
  }, [load]);

  async function revokeAll() {
    if (!window.confirm("إنهاء كل الجلسات؟ ستحتاج إلى تسجيل الدخول من جديد.")) {
      return;
    }
    setBusy(true);
    try {
      await request("/auth/sessions/revoke-all", { method: "POST", auth: true });
      logout();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنهاء الجلسات.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main id="main" className="container" />;

  if (!user) {
    return (
      <main id="main" className="container">
        <div className="status-box notice">
          <p>هذه الصفحة تحتاج تسجيل الدخول.</p>
        </div>
      </main>
    );
  }

  return (
    <main id="main" className="container narrow">
      <header className="page-head">
        <h1>حسابي</h1>
      </header>

      <dl className="fact-list">
        <div>
          <dt>الاسم</dt>
          <dd>{user.display_name}</dd>
        </div>
        <div>
          <dt>البريد</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt>الأدوار</dt>
          <dd>{user.roles.map((r) => ROLE_LABELS[r] ?? r).join("، ")}</dd>
        </div>
      </dl>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      <section className="section">
        <h2>الجلسات المفتوحة ({sessions.length})</h2>
        <p className="page-lead">
          كل جلسة جهاز أو متصفح سجّلت الدخول منه. رمز التجديد يُستعمل مرة
          واحدة ويُستبدل تلقائيًا؛ وإن استُعمل رمز مُبطل عُدّ ذلك مؤشر سرقة
          وأُنهيت الجلسة كلها احتياطًا.
        </p>

        {sessions.length === 0 ? (
          <p className="unlinked-note">لا جلسات مسجَّلة.</p>
        ) : (
          <ul className="word-list">
            {sessions.map((item) => (
              <li key={item.chain_id} className="word-card">
                <p className="claim-meta">
                  فُتحت {formatDate(item.created_at)} · تنتهي{" "}
                  {formatDate(item.expires_at)}
                </p>
                <p className="features-cell">
                  <code dir="ltr">{item.user_agent ?? "جهاز غير معروف"}</code>
                </p>
              </li>
            ))}
          </ul>
        )}

        <div className="row-actions">
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={revokeAll}
          >
            إنهاء كل الجلسات
          </button>
        </div>
      </section>
    </main>
  );
}
