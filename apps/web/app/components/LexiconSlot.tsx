"use client";

import { useEffect, useState } from "react";

import {
  getLexicon,
  sihahEntry,
  type Lexicon,
  type SihahEntry,
} from "../lib/staticdata";

/**
 * المادة المعجمية: **موضعٌ مفتوحٌ ومتنٌ غير مُدخَل**.
 *
 * **لماذا مكوّنٌ مشترك:** كان هذا القسم في صفحة الكلمة وحدها، وصفحةُ
 * الجذر — وهي أَولى به — بلا شيء. ونسخُه مرتين يجعل الحقيقتين تفترقان
 * عند أول تعديل. فمصدرٌ واحد لبيانه وعرضه.
 *
 * **والفراغ يُشرَح مكشوفًا لا مطويًّا:** يرى القارئ «المتن غير مُدخَل»
 * **ولماذا** — وإلا حسبه تقصيرًا منّا. وعرضُ ما فُحص وسببِ ردّه هو الفرق
 * بين نقصٍ مُعلَن ونقصٍ مسكوتٍ عنه.
 */
export function LexiconSlot({ roots }: { roots: string[] }) {
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [entries, setEntries] = useState<Record<string, SihahEntry>>({});

  useEffect(() => {
    getLexicon().then(setLexicon).catch(() => setLexicon(null));
  }, []);

  const unique = [...new Set(roots.filter(Boolean))];
  const key = unique.join("|");

  // مواد «مختار الصحاح» المنشورة — ولا يصل إلى ملفاتها إلا المراجَع (§24.6)
  useEffect(() => {
    if (!key) return;
    let live = true;
    Promise.all(
      key.split("|").map(async (root) => [root, await sihahEntry(root)] as const)
    ).then((pairs) => {
      if (!live) return;
      const next: Record<string, SihahEntry> = {};
      for (const [root, entry] of pairs) if (entry) next[root] = entry;
      setEntries(next);
    });
    return () => {
      live = false;
    };
  }, [key]);

  if (!lexicon || unique.length === 0) return null;
  const sihah = lexicon.sihah;

  return (
    <section className="lexicon-slot" aria-labelledby="lex-head">
      <h2 id="lex-head">المادة المعجمية</h2>

      {unique.map((root) => {
        const entry = entries[root];
        return (
          <div key={root} className="lex-entry-block">
            <p className="lex-entry">
              <span className="lex-locator">
                مادة <bdi>{root}</bdi>
              </span>
              {entry ? (
                <span
                  className={
                    entry.review === "human"
                      ? "lex-state has-text"
                      : "lex-state pending-review"
                  }
                >
                  مختار الصحاح — ص {entry.page} ·{" "}
                  {entry.review === "human"
                    ? "مُراجَعة بشريًّا"
                    : entry.review === "agent"
                      ? "راجعها وكيلٌ آلي مستقل — قيد مراجعة المالك"
                      : "نُسخت آليًّا — قيد المراجعة"}
                </span>
              ) : (
                <span className="lex-state">المتن غير مُدخَل</span>
              )}
            </p>
            {entry && sihah && (
              <article className="sihah-entry">
                {/* نصُّ الطبعة الحرّة كما نُسخ ورُوجع — بضبطه. */}
                <p className="sihah-text" lang="ar">
                  {entry.text}
                </p>
                <p className="sihah-provenance">
                  {sihah.work} — {sihah.author} · {sihah.edition} · ص{" "}
                  {entry.page} ·{" "}
                  <a href={sihah.scan} target="_blank" rel="noreferrer noopener">
                    المصوَّرة
                  </a>{" "}
                  · ملكية عامة —{" "}
                  {entry.review === "human"
                    ? "نُسخ آليًّا ورُوجعت صفحتُه بشريًّا"
                    : entry.review === "agent"
                      ? "نُسخ آليًّا وراجعه وكيلٌ مستقل، وينتظر مراجعة المالك"
                      : "نُسخ آليًّا وينتظر المراجعة — يُصحَّح فور ورودها"}
                </p>
              </article>
            )}
          </div>
        );
      })}

      {sihah && sihah.pages.reviewed < sihah.pages.transcribed && (
        <p className="notice-inline">
          من «مختار الصحاح»: {sihah.pages.transcribed} صفحات منسوخة،
          راجع المالكُ {sihah.pages.reviewed} منها — والباقي منشورٌ
          بوسم «قيد المراجعة» بقرار المالك (2026-07-30)، ويُصحَّح فور
          مراجعته.
        </p>
      )}
      <p className="notice-inline">{lexicon.reason}</p>

      {/* الإحالة بدل النقل: أفضل طبعةٍ مسمّاة بمحقّقها وناشرها، وطريقُ
          القارئ إليها. والترتيب بوفاة المؤلف — زمنيّ لا تفضيليّ. */}
      <h3 className="lex-sources-head">
        اقرأ المادة عند — {lexicon.references.length} معاجم
      </h3>
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

      <h3 className="lex-sources-head">
        ما فُحص من المعاجم — {lexicon.sources.length} ولم يجتز منها شيء
      </h3>
      <ul className="lex-sources">
        {lexicon.sources.map((source) => (
          <li key={source.name} data-status={source.status}>
            <a href={source.url} target="_blank" rel="noreferrer noopener">
              {source.name}
            </a>
            <span className="lex-licence">{source.licence}</span>
            <span className="muted">{source.note}</span>
          </li>
        ))}
      </ul>
      <p className="notice-inline">
        التفصيل بالأدلّة في{" "}
        <a
          href="https://github.com/hasanawida/quran-semantic-platform/blob/main/docs/audits/LEXICON_SOURCING.md"
          target="_blank"
          rel="noreferrer noopener"
        >
          سجلّ فحص المعاجم
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
  );
}
