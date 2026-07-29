"use client";

import { useEffect, useState } from "react";

import { getLexicon, type Lexicon } from "../lib/staticdata";

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

  useEffect(() => {
    getLexicon().then(setLexicon).catch(() => setLexicon(null));
  }, []);

  const unique = [...new Set(roots.filter(Boolean))];
  if (!lexicon || unique.length === 0) return null;

  return (
    <section className="lexicon-slot" aria-labelledby="lex-head">
      <h2 id="lex-head">المادة المعجمية</h2>

      {unique.map((root) => (
        <p key={root} className="lex-entry">
          <span className="lex-locator">
            مادة <bdi>{root}</bdi>
          </span>
          <span className="lex-state">المتن غير مُدخَل</span>
        </p>
      ))}
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
