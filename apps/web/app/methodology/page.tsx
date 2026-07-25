"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMethodology } from "../lib/staticdata";

type Source = {
  key: string;
  role: string;
  name: string;
  url: string;
  variant: string;
  license: string;
  license_url?: string;
  why_chosen: string;
  method?: string;
  reference?: string;
  known_limits: string[];
  what_we_did: string;
};

type Candidate = {
  name: string;
  url: string;
  kind: string;
  license_status: "verified" | "unverified" | "incomplete";
  license_note: string;
  verdict: string;
  committee_note: string;
};

/** حالة التحقق من الرخصة — تُعرض ولا تُطوى في النص. */
const LICENSE_STATUS: Record<
  Candidate["license_status"],
  { label: string; tone: string }
> = {
  verified: { label: "نص الرخصة موجود", tone: "is-positive" },
  unverified: { label: "لا نص رخصة", tone: "is-negative" },
  incomplete: { label: "التحقق ناقص", tone: "is-caution" },
};

type Disagreement = {
  key: string;
  title: string;
  summary: string;
  references: string[];
  platform_position: string;
  evidence?: string;
};

type Payload = {
  reviewed_at: string;
  adopted_sources: Source[];
  second_witness_verdict: {
    audited_at: string;
    question: string;
    answer: string;
    consequence: string;
    why_not_lowered: string;
    path_forward: string[];
  };
  candidate_second_sources: Candidate[];
  machine_analyzer_warning: {
    claim: string;
    reference: string;
    consequence: string;
  };
  disagreements: Disagreement[];
  method: {
    layers: { title: string; detail: string }[];
    pipeline: { step: string; detail: string }[];
    red_lines: string[];
  };
  notice: string;
};

/** يُبرز ما بين نجمتين. بيان المصادر يشدّد على مواضع بعينها — التحفّظ
 *  على رخصة، ونفي وجود حقل — فكانت النجمات تظهر حرفيًا قبل هذا. */
function Rich({ value }: { value: string }) {
  return (
    <>
      {value.split(/\*\*(.+?)\*\*/g).map((part, index) =>
        index % 2 === 1 ? <strong key={index}>{part}</strong> : part,
      )}
    </>
  );
}

/** يحوّل «نص — https://…» إلى نص ورابط، ويترك ما لا رابط فيه كما هو. */
function RefLine({ value }: { value: string }) {
  const match = value.match(/^(.*?)\s*—?\s*(https?:\/\/\S+)$/);
  if (!match) return <>{value}</>;
  const [, label, url] = match;
  return (
    <>
      {label.trim()}{" "}
      <a href={url} target="_blank" rel="noreferrer noopener">
        {url}
      </a>
    </>
  );
}

export default function MethodologyPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMethodology()
      .then((payload) => setData(payload as Payload))
      .catch((err) => setError((err as Error).message));
  }, []);

  return (
    <main id="main" className="container">
      <header className="page-head">
        <h1>المنهج والمصادر ومواضع الخلاف</h1>
      </header>
      <p className="page-lead">
        من أين تأتي بيانات المنصة، وكيف تُعالَج، وأين يقع الخلاف العلمي
        وكيف تتعامل معه. ما نعرفه موثَّق، وما لا نعرفه أو لم نتحقق منه
        مذكور هنا صراحةً.
      </p>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <div className="status-box notice">
            <p>{data.notice}</p>
          </div>

          {/* ---- المصادر المعتمدة ---- */}
          <section className="section">
            <h2>المصادر المعتمدة</h2>
            {data.adopted_sources.map((source) => (
              <article key={source.key} className="surface source-card">
                <div className="word-card-head">
                  <span className="chip is-caution">{source.role}</span>
                  <h3>{source.name}</h3>
                </div>
                <dl className="fact-list">
                  <div>
                    <dt>الرابط</dt>
                    <dd>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {source.url}
                      </a>
                    </dd>
                  </div>
                  <div>
                    <dt>الإصدار المعتمد</dt>
                    <dd>{source.variant}</dd>
                  </div>
                  <div>
                    <dt>الرخصة</dt>
                    <dd>
                      {source.license}
                      {source.license_url && (
                        <>
                          {" — "}
                          <a
                            href={source.license_url}
                            target="_blank"
                            rel="noreferrer noopener"
                          >
                            المصدر
                          </a>
                        </>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>لماذا اختيرَ</dt>
                    <dd>{source.why_chosen}</dd>
                  </div>
                  {source.method && (
                    <div>
                      <dt>منهج المصدر</dt>
                      <dd>{source.method}</dd>
                    </div>
                  )}
                  {source.reference && (
                    <div>
                      <dt>مرجع منشور</dt>
                      <dd>
                        <RefLine value={source.reference} />
                      </dd>
                    </div>
                  )}
                </dl>

                <h4>حدوده المعلومة</h4>
                <ul className="plain-bullets">
                  {source.known_limits.map((limit, index) => (
                    <li key={index}>
                      <Rich value={limit} />
                    </li>
                  ))}
                </ul>

                <p className="decision-note">
                  <strong>ما فعلته المنصة:</strong>{" "}
                  <Rich value={source.what_we_did} />
                </p>
              </article>
            ))}
          </section>

          {/* ---- مواضع الخلاف ---- */}
          <section className="section">
            <h2>مواضع الخلاف ({data.disagreements.length})</h2>
            <p className="page-lead">
              الخلاف العلمي يُعرض ولا يُخفى. لكل موضع: ما هو الخلاف، وأين
              يُراجَع، وما موقف المنصة منه ولماذا.
            </p>
            <ul className="word-list">
              {data.disagreements.map((item) => (
                <li key={item.key} className="word-card">
                  <div className="word-card-head">
                    <h3>{item.title}</h3>
                  </div>
                  <p className="claim-statement">
                    <Rich value={item.summary} />
                  </p>
                  <p className="decision-note">
                    <strong>موقف المنصة:</strong>{" "}
                    <Rich value={item.platform_position} />
                  </p>
                  {item.evidence && (
                    <p className="unlinked-note">
                      <strong>الشاهد:</strong> {item.evidence}
                    </p>
                  )}
                  {item.references.length > 0 && (
                    <details>
                      <summary>المراجع ({item.references.length})</summary>
                      <ul className="evidence-list">
                        {item.references.map((reference, index) => (
                          <li key={index}>
                            <RefLine value={reference} />
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* ---- كيف تعمل المنصة ---- */}
          <section className="section">
            <h2>كيف تعمل المنصة</h2>

            <h3>أربع طبقات لا تختلط</h3>
            <ol className="layers">
              {data.method.layers.map((layer) => (
                <li key={layer.title}>
                  <strong>{layer.title}</strong>
                  <span>{layer.detail}</span>
                </li>
              ))}
            </ol>

            <h3>خط المعالجة</h3>
            <ol className="pipeline-list">
              {data.method.pipeline.map((step) => (
                <li key={step.step}>
                  <strong>{step.step}</strong>
                  <span>
                    <Rich value={step.detail} />
                  </span>
                </li>
              ))}
            </ol>

            <h3>خطوط حمراء</h3>
            <ul className="red-lines">
              {data.method.red_lines.map((line, index) => (
                <li key={index}>
                  <Rich value={line} />
                </li>
              ))}
            </ul>
          </section>

          {/* ---- الشاهد الثاني ---- */}
          <section className="section">
            <h2>الشاهد الثاني — قرار اللجنة</h2>
            <div className="status-box notice verdict-box">
              <p>
                <strong>السؤال:</strong> {data.second_witness_verdict.question}
              </p>
              <p>
                <strong>الجواب: {data.second_witness_verdict.answer}</strong>{" "}
                <Rich value={data.second_witness_verdict.consequence} />
              </p>
              <p>
                <Rich value={data.second_witness_verdict.why_not_lowered} />
              </p>
            </div>
            <h3>ما الطريق إلى شاهد ثانٍ</h3>
            <ul className="plain-bullets">
              {data.second_witness_verdict.path_forward.map((line) => (
                <li key={line}>
                  <Rich value={line} />
                </li>
              ))}
            </ul>
            <h3>المصادر التي فُحصت</h3>
            <div className="compare-scroll">
              <table className="segment-table">
                <thead>
                  <tr>
                    <th>المصدر</th>
                    <th>نوعه</th>
                    <th>الرخصة</th>
                    <th>الحكم</th>
                    <th>تعليل اللجنة</th>
                  </tr>
                </thead>
                <tbody>
                  {data.candidate_second_sources.map((candidate) => (
                    <tr key={candidate.name}>
                      <td data-label="المصدر">
                        {candidate.url ? (
                          <a
                            href={candidate.url}
                            target="_blank"
                            rel="noreferrer noopener"
                          >
                            {candidate.name}
                          </a>
                        ) : (
                          candidate.name
                        )}
                      </td>
                      <td data-label="نوعه">
                        <Rich value={candidate.kind} />
                      </td>
                      <td data-label="الرخصة">
                        <span
                          className={`chip ${
                            LICENSE_STATUS[candidate.license_status].tone
                          }`}
                        >
                          {LICENSE_STATUS[candidate.license_status].label}
                        </span>{" "}
                        <Rich value={candidate.license_note} />
                      </td>
                      <td data-label="الحكم">
                        <strong>{candidate.verdict}</strong>
                      </td>
                      <td data-label="تعليل اللجنة">
                        <Rich value={candidate.committee_note} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="status-box error">
              <p>
                <strong>تحذير موثق:</strong>{" "}
                {data.machine_analyzer_warning.claim}{" "}
                <RefLine value={data.machine_analyzer_warning.reference} />.{" "}
                {data.machine_analyzer_warning.consequence}
              </p>
            </div>
          </section>

          <p className="claim-meta">
            راجعت اللجنة هذا البيان في {data.reviewed_at}. البيانات الحية
            ومصادرها وبصماتها في <Link href="/provenance">بيان الأصول</Link>.
          </p>
        </>
      )}
    </main>
  );
}
