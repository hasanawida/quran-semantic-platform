"use client";

import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Evidence = {
  stance: "supports" | "opposes" | "context";
  locator: string;
  quoted_text: string | null;
  paraphrase: string | null;
  source: {
    code: string;
    title: string;
    author: string;
    edition: string;
    is_verified: boolean;
  };
};

type Claim = {
  id: string;
  statement: string;
  claim_type: string;
  subject: Record<string, string | number>;
  status: string;
  confidence: string;
  author: { display_name: string };
  resolution_note: string | null;
  evidence: Evidence[];
  supporting_count: number;
  opposing_count: number;
};

type Payload = {
  approved: { total: number; items: Claim[] };
  disputed: { total: number; items: Claim[] };
  notice: string;
};

const STANCE_LABELS: Record<Evidence["stance"], string> = {
  supports: "مؤيد",
  opposes: "معارض",
  context: "سياق",
};

const STATUS_LABELS: Record<string, string> = {
  approved: "معتمد",
  disputed: "مختلف فيه",
};

function subjectLabel(subject: Record<string, string | number>): string {
  if (subject.root) return `الجذر ${subject.root}`;
  if (subject.lemma) return `الأصل ${subject.lemma}`;
  if (subject.surah) {
    const base = `${subject.surah}:${subject.ayah}`;
    return subject.word_number ? `${base} الكلمة ${subject.word_number}` : base;
  }
  return "—";
}

function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <li className="word-card">
      <div className="word-card-head">
        <span className="claim-subject">{subjectLabel(claim.subject)}</span>
        <span
          className={`agreement-tag ${
            claim.status === "disputed" ? "agreement-conflict" : "agreement-agreement"
          }`}
        >
          {STATUS_LABELS[claim.status] ?? claim.status}
        </span>
      </div>
      <p className="claim-statement">{claim.statement}</p>
      <p className="claim-meta">
        الباحث: {claim.author.display_name} — أدلة مؤيدة{" "}
        {claim.supporting_count} ومعارضة {claim.opposing_count}
      </p>
      {claim.resolution_note && (
        <p className="decision-note">
          <strong>سبب الخلاف:</strong> {claim.resolution_note}
        </p>
      )}
      <details>
        <summary>الأدلة ({claim.evidence.length})</summary>
        <ul className="evidence-list">
          {claim.evidence.map((item, index) => (
            <li key={index}>
              <span
                className={`stance-tag stance-${item.stance}`}
              >
                {STANCE_LABELS[item.stance]}
              </span>{" "}
              {item.source.author}، <em>{item.source.title}</em>،{" "}
              {item.source.edition} — {item.locator}
              {item.quoted_text && <blockquote>{item.quoted_text}</blockquote>}
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

export default function ClaimsPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/claims`)
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok || !payload?.data) {
          setError(payload?.error?.message ?? "تعذّر جلب الادعاءات.");
          return;
        }
        setData(payload.data);
      })
      .catch(() => setError("تعذّر الاتصال بالخدمة الخلفية."));
  }, []);

  return (
    <main id="main" className="container">
      <header className="analysis-header">
        <h1>الادعاءات البحثية</h1>
      </header>
      <p className="page-lead">
        دعاوى الباحثين الموثقة بأدلتها. لا تُعرض هنا مسودة ولا ما هو قيد
        المراجعة: المسودة ليست نتيجة. والمختلف فيه يُعرض بخلافه لا يُخفى.
      </p>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <section className="provenance-block">
            <h2>معتمدة ({data.approved.total})</h2>
            {data.approved.items.length === 0 ? (
              <p className="unlinked-note">لا توجد ادعاءات معتمدة بعد.</p>
            ) : (
              <ul className="word-list">
                {data.approved.items.map((claim) => (
                  <ClaimCard key={claim.id} claim={claim} />
                ))}
              </ul>
            )}
          </section>

          <section className="provenance-block">
            <h2>مختلف فيها ({data.disputed.total})</h2>
            {data.disputed.items.length === 0 ? (
              <p className="unlinked-note">لا توجد ادعاءات مختلف فيها.</p>
            ) : (
              <ul className="word-list">
                {data.disputed.items.map((claim) => (
                  <ClaimCard key={claim.id} claim={claim} />
                ))}
              </ul>
            )}
          </section>

          <div className="status-box notice">
            <p>{data.notice}</p>
          </div>
        </>
      )}
    </main>
  );
}
