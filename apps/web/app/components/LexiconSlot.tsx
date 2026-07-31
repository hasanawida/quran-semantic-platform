"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  getLexicon,
  openitiEntry,
  sihahEntry,
  type Lexicon,
  type OpenitiEntry,
  type SihahEntry,
} from "../lib/staticdata";

/** ترتيب عرض الكتب الأربعة: بوفاة المؤلف — زمنيٌّ لا تفضيليّ (ADR-013). */
const OPENITI_ORDER = ["sihah_jawhari", "maqayis", "mufradat", "lisan"] as const;

/**
 * المادة المعجمية — قراءةٌ هادئة بقرار المالك (2026-08-01):
 *
 * **كلُّ معجمٍ مطويٌّ افتراضًا والقارئ يفتح ما يشاء.** ظاهرُ الركن سطرُ
 * عنوانٍ لكل كتاب (اسمه وموضع المادة وحالها)، ومتنُ المادة خلف طيّةٍ
 * `<details>` — فلا يُصبّ على القارئ خمسةُ متونٍ دفعةً واحدة.
 *
 * **وسجلات الإسناد الطويلة لها صفحتها:** قوائم «اقرأ المادة عند» وما
 * فحص من المصادر وبيانات الطبعات انتقلت إلى `/lexicon-sources` — يبلغها
 * من أرادها من رابط واحد، ولا تزاحم من جاء يقرأ.
 */
export function LexiconSlot({ roots }: { roots: string[] }) {
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [entries, setEntries] = useState<Record<string, SihahEntry>>({});
  const [classic, setClassic] = useState<Record<string, OpenitiEntry>>({});

  useEffect(() => {
    getLexicon().then(setLexicon).catch(() => setLexicon(null));
  }, []);

  const unique = [...new Set(roots.filter(Boolean))];
  const key = unique.join("|");

  // مواد «مختار الصحاح» المنسوخة بصريًّا عن طبعة ١٩٢٠ الحرة
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

  // متون الكتب الأربعة (§٢٠): متنٌ كلاسيكي مستورد، مسندٌ لا مُراجَع
  useEffect(() => {
    if (!key) return;
    let live = true;
    Promise.all(
      key.split("|").map(async (root) => [root, await openitiEntry(root)] as const)
    ).then((pairs) => {
      if (!live) return;
      const next: Record<string, OpenitiEntry> = {};
      for (const [root, entry] of pairs) if (entry) next[root] = entry;
      setClassic(next);
    });
    return () => {
      live = false;
    };
  }, [key]);

  if (!lexicon || unique.length === 0) return null;
  const sihah = lexicon.sihah;
  const openiti = lexicon.openiti;

  return (
    <section className="lexicon-slot" aria-labelledby="lex-head">
      <h2 id="lex-head">المادة المعجمية</h2>

      {unique.map((root) => {
        const entry = entries[root];
        const classicEntry = classic[root];
        const bookCount =
          (entry ? 1 : 0) +
          (classicEntry
            ? OPENITI_ORDER.filter((book) => classicEntry[book]).length
            : 0);
        return (
          <div key={root} className="lex-entry-block">
            <p className="lex-entry">
              <span className="lex-locator">
                مادة <bdi>{root}</bdi>
              </span>
              {bookCount > 0 ? (
                <span className="lex-state has-text">
                  في {bookCount} {bookCount > 2 ? "معاجم" : "معجم"} — افتح ما
                  تشاء
                </span>
              ) : (
                <span className="lex-state">المتن غير مُدخَل</span>
              )}
            </p>

            {/* «مختار الصحاح» أولًا: الطبقة الأوثق — نسخٌ بصري عن طبعة
                حرة تُراجَع صفحةً صفحة */}
            {entry && sihah && (
              <details className="lex-details">
                <summary>
                  <span className="lex-book-title">{sihah.work}</span>
                  <span className="lex-book-info">
                    ص {entry.page} ·{" "}
                    {entry.review === "human"
                      ? "مُراجَعة بشريًّا"
                      : entry.review === "agent"
                        ? "راجعها وكيل مستقل"
                        : "قيد المراجعة"}
                  </span>
                </summary>
                <article className="sihah-entry">
                  {/* نصُّ الطبعة الحرّة كما نُسخ — بضبطه. */}
                  <p className="sihah-text" lang="ar">
                    {entry.text}
                  </p>
                  <p className="sihah-provenance">
                    {sihah.work} — {sihah.author} · {sihah.edition} · ص{" "}
                    {entry.page} ·{" "}
                    <a
                      href={sihah.scan}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
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
              </details>
            )}

            {/* متون الكتب الأربعة (§٢٠) — كلٌّ خلف طيّته */}
            {classicEntry &&
              openiti &&
              OPENITI_ORDER.filter((book) => classicEntry[book]).map((book) => {
                const meta = openiti.books[book];
                return (
                  <details className="lex-details" key={book}>
                    <summary>
                      <span className="lex-book-title">{meta.title}</span>
                      <span className="lex-book-info">
                        {meta.author.split("(")[0].split("،")[0].trim()} (ت
                        {meta.author_died_hijri}هـ)
                        {classicEntry[book][0].page
                          ? ` · ${classicEntry[book][0].page}`
                          : ""}
                      </span>
                    </summary>
                    {classicEntry[book].map((record, i) => (
                      <article className="sihah-entry openiti-entry" key={i}>
                        <p className="sihah-text" lang="ar">
                          {record.text}
                        </p>
                        <p className="sihah-provenance">
                          {meta.title} — {meta.author} (ت{meta.author_died_hijri}
                          هـ){record.page ? ` · ${record.page}` : ""} · نصُّ
                          طبعة {meta.editor} · {meta.publisher}
                          {meta.edition ? ` · ${meta.edition}` : ""} ·{" "}
                          <a
                            href={meta.source_url}
                            target="_blank"
                            rel="noreferrer noopener"
                          >
                            المصدر الرقمي (OpenITI)
                          </a>{" "}
                          · متنٌ كلاسيكي مستورد آليًّا — جهاز المحقِّق
                          مستبعَد، والنسبةُ إقرارٌ بالمصدر لا إذنٌ منه
                        </p>
                      </article>
                    ))}
                  </details>
                );
              })}
          </div>
        );
      })}

      {/* سجلات الإسناد كلها في صفحتها — رابط واحد بدل قوائم تثقل القراءة */}
      <p className="lex-sources-link">
        <Link href="/lexicon-sources">مصادر المعاجم وإسنادها وما فُحص منها ←</Link>
      </p>
    </section>
  );
}
