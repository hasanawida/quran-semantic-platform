"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getLexicon, type Lexicon } from "../lib/staticdata";

/** ترتيب الكتب بوفاة المؤلف — زمنيٌّ لا تفضيليّ (ADR-013). */
const OPENITI_ORDER = ["sihah_jawhari", "maqayis", "mufradat", "lisan"] as const;

/**
 * صفحة مصادر المعاجم — البيت الذي انتقلت إليه سِجِلّات الإسناد.
 *
 * كانت قوائم «اقرأ المادة عند» وما فُحص من المصادر وبياناتُ الطبعات
 * تُعرض داخل ركن المادة المعجمية في كل صفحة، فتُثقل القراءة وتشتت
 * القارئ (قرار المالك 2026-08-01). هنا مكانها: من أراد الإسناد وجده
 * كاملًا، ومن جاء يقرأ لم يُزاحَم.
 */
export default function LexiconSourcesPage() {
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getLexicon()
      .then(setLexicon)
      .catch(() => setError(true));
  }, []);

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>مصادر المعاجم</span>
      </nav>

      <header className="analysis-header">
        <h1>مصادر المعاجم وإسنادها</h1>
        <p className="root-stats">
          من أين جاء كل حرفٍ معجمي في المنصة — الكتاب والطبعة والمصدر
          الرقمي والبصمة، وما فُحص فلم يُقبل وسببُه.
        </p>
      </header>

      {error && (
        <div className="status-box error" role="alert">
          <p>تعذّر تحميل سجل المصادر.</p>
        </div>
      )}

      {lexicon && (
        <>
          {/* ---- الطبقة الموثقة: مختار الصحاح ١٩٢٠ ---- */}
          {lexicon.sihah && (
            <section aria-labelledby="src-sihah">
              <h2 id="src-sihah">الطبقة المراجَعة — {lexicon.sihah.work}</h2>
              <p>
                {lexicon.sihah.author} · {lexicon.sihah.edition} · ملكية عامة
                نصًّا وترقيمًا ·{" "}
                <a
                  href={lexicon.sihah.scan}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  المصوَّرة
                </a>
              </p>
              <p className="notice-inline">
                {lexicon.sihah.pages.transcribed} صفحة منسوخة نسخًا بصريًّا،
                راجع المالكُ {lexicon.sihah.pages.reviewed} منها — والباقي
                منشور بوسم «قيد المراجعة» بقرار المالك (2026-07-30)، ويُصحَّح
                فور مراجعته. {lexicon.sihah.statement}
              </p>
            </section>
          )}

          {/* ---- متون الكتب الأربعة (§٢٠) ---- */}
          {lexicon.openiti && (
            <section aria-labelledby="src-openiti">
              <h2 id="src-openiti">
                المتون الكلاسيكية — {lexicon.openiti.roots_covered} من{" "}
                {lexicon.openiti.roots_total} جذرًا
              </h2>
              <p className="notice-inline">{lexicon.openiti.statement}</p>
              <ul className="lex-refs">
                {OPENITI_ORDER.filter((b) => lexicon.openiti!.books[b]).map(
                  (b) => {
                    const book = lexicon.openiti!.books[b];
                    return (
                      <li key={b}>
                        <a
                          href={book.source_url}
                          target="_blank"
                          rel="noreferrer noopener"
                        >
                          {book.title}
                        </a>
                        <span className="ref-author">
                          {book.author} (ت{book.author_died_hijri}هـ)
                        </span>
                        <span className="lex-licence">
                          نصُّ طبعة {book.editor} · {book.publisher}
                          {book.edition ? ` · ${book.edition}` : ""}
                        </span>
                        <span className="muted">
                          {book.entries_matched} مادة مطابقة لجذور المصحف ·{" "}
                          {book.apparatus} · بصمة الملف:{" "}
                          <code dir="ltr">{book.sha256.slice(0, 16)}…</code>
                        </span>
                      </li>
                    );
                  }
                )}
              </ul>
              <p className="notice-inline">{lexicon.openiti.decision}</p>
            </section>
          )}

          {/* ---- الإحالة بدل النقل: أفضل الطبعات المسمّاة ---- */}
          <section aria-labelledby="src-refs">
            <h2 id="src-refs">
              اقرأ المادة عند — {lexicon.references.length} معاجم
            </h2>
            <ul className="lex-refs">
              {lexicon.references.map((ref) => (
                <li key={ref.work}>
                  <a href={ref.url} target="_blank" rel="noreferrer noopener">
                    {ref.work}
                  </a>
                  <span className="ref-author">
                    {ref.author} (ت{ref.died})
                  </span>
                  <span className="lex-licence">{ref.edition}</span>
                  <span className="muted">{ref.why}</span>
                </li>
              ))}
            </ul>
            <p className="notice-inline">{lexicon.references_note}</p>
          </section>

          {/* ---- ما فُحص فلم يُقبل — النقص المعلَن ---- */}
          <section aria-labelledby="src-audit">
            <h2 id="src-audit">
              ما فُحص من المصادر الرقمية — {lexicon.sources.length}
            </h2>
            <ul className="lex-sources">
              {lexicon.sources.map((source) => (
                <li key={source.name} data-status={source.status}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {source.name}
                  </a>
                  <span className="lex-licence">{source.licence}</span>
                  <span className="muted">{source.note}</span>
                </li>
              ))}
            </ul>
            <p className="notice-inline">{lexicon.reason}</p>
            <p className="notice-inline">
              التفصيل بالأدلّة في{" "}
              <a
                href="https://github.com/hasanawida/quran-semantic-platform/blob/main/docs/audits/LEXICON_SOURCING.md"
                target="_blank"
                rel="noreferrer noopener"
              >
                سجلّ فحص المعاجم
              </a>
              ، وقرار المتون الكلاسيكية في{" "}
              <a
                href="https://github.com/hasanawida/quran-semantic-platform/blob/main/docs/audits/OPENITI_MATN_DECISION.md"
                target="_blank"
                rel="noreferrer noopener"
              >
                وثيقته
              </a>
              ، وطلباتُ الإذن في{" "}
              <a
                href="https://github.com/hasanawida/quran-semantic-platform/blob/main/docs/permissions/REQUESTS.md"
                target="_blank"
                rel="noreferrer noopener"
              >
                سجلّ الاستئذان
              </a>
              .
            </p>
          </section>
        </>
      )}
    </main>
  );
}
