"use client";

import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type MorphologySource = {
  code: string;
  name: string;
  url: string | null;
  version: string | null;
  license: string | null;
  file_sha256: string | null;
  status: string;
  enabled: boolean;
};

type Provenance = {
  text_version: {
    version_code: string;
    title: string;
    riwayah: string;
    script_type: string;
    counting_system: string;
    source_name: string;
    source_reference: string | null;
    sha256: string;
    status: string;
    is_validated: boolean;
    double_approved: boolean;
  };
  counts: Record<string, number>;
  occurrences_by_derivation: Record<string, number>;
  morphology_sources: MorphologySource[];
  notice: string;
};

const COUNT_LABELS: Record<string, string> = {
  surahs: "السور",
  ayahs: "الآيات",
  roots: "الجذور",
  root_occurrences: "مواضع الجذور",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  imported: "مستورد — غير معتمد",
  machine_generated: "آلي فقط",
  under_review: "قيد المراجعة",
  approved: "معتمد",
  published: "منشور",
  disputed: "مختلف فيه",
  rejected: "مرفوض",
  deprecated: "متقادم",
};

export default function ProvenancePage() {
  const [data, setData] = useState<Provenance | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/export/provenance`)
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok || !payload?.data) {
          setError(payload?.error?.message ?? "تعذّر جلب بيان الأصول.");
          return;
        }
        setData(payload.data);
      })
      .catch(() => setError("تعذّر الاتصال بالخدمة الخلفية."));
  }, []);

  return (
    <main id="main" className="container">
      <header className="analysis-header">
        <h1>بيان الأصول</h1>
      </header>
      <p className="page-lead">
        من أين جاءت كل بيانات المنصة، ببصماتها ورخصها وحالتها العلمية. هذه
        الصفحة مفتوحة للعموم عمدًا: ما لا يمكن التحقق منه لا يصلح للاستشهاد.
      </p>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <section className="provenance-block">
            <h2>إصدار النص القرآني</h2>
            <dl className="fact-list">
              <div>
                <dt>الإصدار</dt>
                <dd>
                  {data.text_version.title}{" "}
                  <code>{data.text_version.version_code}</code>
                </dd>
              </div>
              <div>
                <dt>الرواية والرسم والعد</dt>
                <dd>
                  {data.text_version.riwayah} — {data.text_version.script_type} —{" "}
                  {data.text_version.counting_system}
                </dd>
              </div>
              <div>
                <dt>المصدر</dt>
                <dd>
                  {data.text_version.source_name}
                  {data.text_version.source_reference && (
                    <>
                      {" "}
                      <a
                        href={data.text_version.source_reference}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {data.text_version.source_reference}
                      </a>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>بصمة الإصدار</dt>
                <dd>
                  <code dir="ltr" className="hash">
                    {data.text_version.sha256}
                  </code>
                </dd>
              </div>
              <div>
                <dt>حالة المراجعة</dt>
                <dd>
                  <span className="review-tag">
                    {STATUS_LABELS[data.text_version.status] ??
                      data.text_version.status}
                  </span>{" "}
                  {data.text_version.is_validated
                    ? "اجتاز التحقق البنيوي"
                    : "لم يجتز التحقق البنيوي بعد"}
                  {" — "}
                  {data.text_version.double_approved
                    ? "اعتمده مراجعان مستقلان"
                    : "لم يكتمل الاعتماد المزدوج"}
                </dd>
              </div>
            </dl>
          </section>

          <section className="provenance-block">
            <h2>الأعداد</h2>
            <ul className="stat-row">
              {Object.entries(data.counts).map(([key, value]) => (
                <li key={key}>
                  <span className="stat-value">{value.toLocaleString("ar")}</span>
                  <span className="stat-label">{COUNT_LABELS[key] ?? key}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="provenance-block">
            <h2>كيف اشتُقت مواضع الجذور</h2>
            <table className="segment-table">
              <thead>
                <tr>
                  <th>طريقة الاشتقاق</th>
                  <th>عدد المواضع</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.occurrences_by_derivation).map(
                  ([label, value]) => (
                    <tr key={label}>
                      <td>{label}</td>
                      <td>{value.toLocaleString("ar")}</td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </section>

          <section className="provenance-block">
            <h2>مصادر التحليل الصرفي</h2>
            {data.morphology_sources.length === 0 && (
              <p className="unlinked-note">لم يُستورد أي مصدر صرفي بعد.</p>
            )}
            {data.morphology_sources.map((source) => (
              <dl className="fact-list" key={source.code}>
                <div>
                  <dt>المصدر</dt>
                  <dd>
                    {source.name} <code>{source.code}</code>
                    {!source.enabled && " (معطَّل)"}
                  </dd>
                </div>
                {source.url && (
                  <div>
                    <dt>الرابط</dt>
                    <dd>
                      <a href={source.url} target="_blank" rel="noreferrer noopener">
                        {source.url}
                      </a>
                    </dd>
                  </div>
                )}
                <div>
                  <dt>الرخصة</dt>
                  <dd>{source.license}</dd>
                </div>
                <div>
                  <dt>بصمة الملف المصدري</dt>
                  <dd>
                    <code dir="ltr" className="hash">
                      {source.file_sha256}
                    </code>
                  </dd>
                </div>
              </dl>
            ))}
          </section>

          <div className="status-box notice">
            <p>{data.notice}</p>
          </div>
        </>
      )}
    </main>
  );
}
