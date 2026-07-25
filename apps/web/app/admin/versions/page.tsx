"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, request } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Version = {
  id: string;
  version_code: string;
  title: string;
  riwayah: string;
  script_type: string;
  counting_system: string;
  status: string;
  is_active: boolean;
  is_validated: boolean;
  approved_by_first: string | null;
  approved_by_second: string | null;
  activation_reason: string | null;
};

const STATUS_LABELS: Record<string, string> = {
  imported: "مستورد",
  under_review: "قيد المراجعة",
  approved: "معتمد",
  published: "منشور",
  disputed: "مختلف فيه",
  rejected: "مرفوض",
  deprecated: "متقادم",
};

const MANAGE = ["text_officer", "tech_admin"];
const APPROVE = [
  "text_officer",
  "tech_admin",
  "quality_manager",
  "linguistic_reviewer",
  "sharia_reviewer",
];

function StatusBadge({ v }: { v: Version }) {
  return (
    <span className={`vbadge status-${v.status}`}>
      {STATUS_LABELS[v.status] ?? v.status}
    </span>
  );
}

export default function VersionsPage() {
  const { user, loading, hasRole } = useAuth();
  const [versions, setVersions] = useState<Version[]>([]);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [fetching, setFetching] = useState(true);

  const load = useCallback(async () => {
    setFetching(true);
    try {
      const data = await request<Version[]>("/admin/quran-versions", { auth: true });
      setVersions(data);
    } catch (err) {
      setMsg({
        kind: "err",
        text: err instanceof ApiError ? err.message : "تعذّر جلب الإصدارات.",
      });
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && user) load();
  }, [loading, user, load]);

  async function act(path: string, body?: unknown, okText?: string) {
    setMsg(null);
    try {
      await request(path, { method: "POST", body, auth: true });
      setMsg({ kind: "ok", text: okText ?? "تم بنجاح." });
      await load();
    } catch (err) {
      setMsg({
        kind: "err",
        text: err instanceof ApiError ? err.message : "فشل الإجراء.",
      });
    }
  }

  async function importDemo() {
    const suffix = Math.random().toString(36).slice(2, 7);
    await act(
      "/admin/quran-versions/import",
      {
        version_code: `demo-${suffix}`,
        title: "نسخة تجريبية للمراجعة",
        riwayah: "حفص",
        script_type: "عثماني",
        counting_system: "كوفي",
        source_name: "إدخال تجريبي",
        ayahs: [
          { surah: 1, ayah: 1, text: "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ" },
          { surah: 1, ayah: 2, text: "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ" },
        ],
      },
      "تم استيراد نسخة تجريبية."
    );
  }

  if (loading) return <main className="container"><p>جارٍ التحميل…</p></main>;

  if (!user) {
    return (
      <main id="main" className="container narrow">
        <div className="status-box notice">
          <p>
            هذه الصفحة تتطلب تسجيل الدخول بدور إداري. <a href="/login">سجّل الدخول</a>.
          </p>
        </div>
      </main>
    );
  }

  if (!hasRole(...APPROVE)) {
    return (
      <main id="main" className="container narrow">
        <div className="status-box notice">
          <p>حسابك ({user.display_name}) لا يملك صلاحية إدارة الإصدارات.</p>
        </div>
      </main>
    );
  }

  const canManage = hasRole(...MANAGE);
  const canApprove = hasRole(...APPROVE);

  return (
    <main id="main" className="container">
      <section className="admin-head">
        <h1>إدارة إصدارات النص</h1>
        <p className="lead-sm">
          سير المراجعة: استيراد ← تحقق بنيوي ← اعتماد مراجعَين مستقلَّين ← تفعيل.
          لا يعتمد مراجع عمله، ويلزم مراجعان مختلفان، وإصدار نشط واحد فقط.
        </p>
        {canManage && (
          <button className="primary" onClick={importDemo}>
            + استيراد نسخة تجريبية
          </button>
        )}
      </section>

      {msg && (
        <div className={`status-box ${msg.kind === "ok" ? "success" : "error"}`} role="status">
          <p>{msg.text}</p>
        </div>
      )}

      {fetching ? (
        <p>جارٍ جلب الإصدارات…</p>
      ) : (
        <div className="version-list">
          {versions.map((v) => (
            <article key={v.id} className={`version-card ${v.is_active ? "active" : ""}`}>
              <div className="version-top">
                <div>
                  <h2>{v.title}</h2>
                  <p className="version-code">{v.version_code} · {v.riwayah} · {v.script_type}</p>
                </div>
                <div className="version-badges">
                  <StatusBadge v={v} />
                  {v.is_active && <span className="vbadge active-badge">نشط</span>}
                  {v.is_validated && <span className="vbadge ok-badge">محقّق</span>}
                </div>
              </div>

              <div className="review-track">
                <span className={v.is_validated ? "step done" : "step"}>تحقق</span>
                <span className={v.approved_by_first ? "step done" : "step"}>اعتماد ١</span>
                <span className={v.approved_by_second ? "step done" : "step"}>اعتماد ٢</span>
                <span className={v.is_active ? "step done" : "step"}>تفعيل</span>
              </div>

              <div className="version-actions">
                {canManage && !v.is_validated && (
                  <button
                    className="ghost"
                    onClick={() =>
                      act(
                        `/admin/quran-versions/${v.id}/validate`,
                        { require_full: false },
                        "تم التحقق البنيوي."
                      )
                    }
                  >
                    تحقّق بنيوي
                  </button>
                )}
                {canApprove && v.is_validated && v.status === "imported" && (
                  <button
                    className="ghost"
                    onClick={() =>
                      act(
                        `/admin/quran-versions/${v.id}/approve`,
                        undefined,
                        "سُجِّل اعتمادك."
                      )
                    }
                  >
                    اعتمد (بصفتي {user.display_name})
                  </button>
                )}
                {canManage && v.status === "approved" && !v.is_active && (
                  <button
                    className="primary"
                    onClick={() => {
                      const reason = window.prompt("سبب التفعيل:");
                      if (reason && reason.trim())
                        act(
                          `/admin/quran-versions/${v.id}/activate`,
                          { reason },
                          "تم تفعيل الإصدار (وأُلغي تفعيل غيره)."
                        );
                    }}
                  >
                    فعّل
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
