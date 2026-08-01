"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ayahAnalysis,
  getMeta,
  getTafsirMeta,
  tafsirSurah,
  type Meta,
  type TafsirMeta,
  type TafsirPassage,
} from "../lib/staticdata";

// انقل من الملف القديم حرفيًا: النوع Segment/Word/AyahAnalysis،
// وAGREEMENT_LABELS، وDECISION_LABELS، ودالة renderAyah كاملةً.
// renderAyah هي حارس الخط الأحمر: تقطّع uthmani_text بمواضع الحروف
// وما بين الكلمات يخرج كما هو — لا تُمسّ بحرف.

// النوع مشتقّ من مخرَج القارئ لا مكتوبًا يدويًا: نسخة ثانية منه
// تتعتّق بصمت حين يتغيّر شكل البيانات.
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Segment = {
  segment_number: number;
  form_source: string;
  tag: string;
  pos: string | null;
  pos_label: string | null;
  features: string;
  lemma: string | null;
  lemma_index: number | null;
  root: string | null;
  source_root_text: string | null;
  is_linked_to_token: boolean;
};

type Word = {
  word_number: number;
  surface_text: string;
  char_start: number;
  char_end: number;
  analyses_by_source: Record<string, Segment[]>;
  root_agreement:
    | "no_analysis"
    | "no_root"
    | "conflict"
    | "single_source"
    | "agreement";
  decision: { status: string; rationale: string } | null;
};

type AyahAnalysis = {
  surah_number: number;
  surah_name: string;
  ayah_number: number;
  uthmani_text: string;
  word_count: number;
  words: Word[];
  notice: string;
};

const AGREEMENT_LABELS: Record<Word["root_agreement"], string> = {
  no_analysis: "بلا تحليل مستورد",
  no_root: "لا جذر لها",
  conflict: "اختلاف بين المصادر",
  single_source: "مصدر واحد",
  agreement: "اتفاق المصادر",
};

const DECISION_LABELS: Record<string, string> = {
  under_review: "قرار قيد المراجعة",
  approved: "قرار معتمد",
  disputed: "مختلف فيه",
  rejected: "قرار مرفوض",
};

/** يعرض نص الآية **كما ورد حرفيًا** ويجعل الكلمات قابلة للنقر.
 *
 *  لا يُعاد تركيب النص من الكلمات: ذلك يُسقط علامات الوقف ورموز نهاية
 *  الآية ويغيّر الفراغات. بدل ذلك يُقطَّع `uthmani_text` بمواضع الحروف
 *  التي يعطيها الخادم (char_start/char_end)، فما بين الكلمات يخرج كما هو.
 */
function renderAyah(
  data: AyahAnalysis,
  selected: number | null,
  setSelected: (value: number | null) => void
) {
  const text = data.uthmani_text;
  const words = [...data.words].sort((a, b) => a.char_start - b.char_start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  words.forEach((word) => {
    // حماية: أي موضع غير متسق يعني عرض النص كما هو بلا تقطيع
    if (word.char_start < cursor || word.char_end > text.length) return;
    if (word.char_start > cursor) {
      parts.push(
        <span key={`gap-${cursor}`}>{text.slice(cursor, word.char_start)}</span>
      );
    }
    parts.push(
      <button
        key={`w-${word.word_number}`}
        type="button"
        className={`word-chip${
          selected === word.word_number ? " is-selected" : ""
        }`}
        onClick={() =>
          setSelected(selected === word.word_number ? null : word.word_number)
        }
        aria-pressed={selected === word.word_number}
        aria-label={`الكلمة ${word.word_number}: ${word.surface_text}`}
      >
        {text.slice(word.char_start, word.char_end)}
      </button>
    );
    cursor = word.char_end;
  });

  if (cursor < text.length) {
    parts.push(<span key="tail">{text.slice(cursor)}</span>);
  }
  // لم تُقطَّع أي كلمة (بيانات غير متوقعة) → النص الأصلي كاملًا
  return parts.length > 0 ? parts : text;
}


export default function AyahAnalysisPage() {
  const [ref, setRef] = useState<{ surah: number; ayah: number } | null>(null);
  const [data, setData] = useState<AyahAnalysis | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [tafsir, setTafsir] = useState<TafsirPassage[] | null>(null);
  const [tafsirMeta, setTafsirMeta] = useState<TafsirMeta | null>(null);

  // مقاطع التفسير (§٢٠): يُقرأ البيان اولا لتعرف الكتب، ثم تجلب شظية
  // كل كتاب لهذه السورة — والاية تلتقط مقطعها منها
  useEffect(() => {
    if (!ref) return;
    let live = true;
    getTafsirMeta()
      .then(async (info) => {
        if (!live) return;
        setTafsirMeta(info);
        const parts = await Promise.all(
          Object.keys(info.works).map((work) => tafsirSurah(work, ref.surah))
        );
        if (!live) return;
        setTafsir(parts.filter(Boolean).flat() as TafsirPassage[]);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [ref]);

  // المعاملان من العنوان لا من مسار مولَّد — فمسار واحد يخدم 6,236 آية
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const surah = Number(params.get("s"));
    const ayah = Number(params.get("a"));
    if (!Number.isInteger(surah) || !Number.isInteger(ayah) || surah < 1 || ayah < 1) {
      setError("مرجع الآية ناقص أو غير صحيح — الصيغة: /ayah?s=2&a=255");
      return;
    }
    setRef({ surah, ayah });
  }, []);

  useEffect(() => {
    if (!ref) return;
    let cancelled = false;
    setData(null);
    setError("");
    // تجزئة العنوان تنقل رقم الكلمة كما كانت #w{n} تفعل
    const word = Number(window.location.hash.replace("#w", ""));
    if (Number.isInteger(word) && word > 0) setSelected(word);
    Promise.all([ayahAnalysis(ref.surah, ref.ayah), getMeta()])
      .then(([payload, info]) => {
        if (cancelled) return;
        setData(payload);
        setMeta(info);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [ref]);

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>
          التحليل الصرفي {ref ? `(${ref.surah}:${ref.ayah})` : ""}
        </span>
      </nav>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <header className="analysis-header">
            <h1>
              سورة {data.surah_name} — الآية {data.ayah_number}
            </h1>
            <p className="root-stats">
              {data.word_count} كلمة
              {(() => {
                // مصدر التحليل يقال مرة واحدة هنا — لا مع كل كلمة:
                // كان «المصدر: qac-0.4» يتكرر بعدد كلمات الآية
                const sources = new Set(
                  data.words.flatMap((w) => Object.keys(w.analyses_by_source))
                );
                return sources.size === 1
                  ? ` · التحليل من المصدر ${[...sources][0]} — منسوب حقلا بحقل`
                  : "";
              })()}
            </p>
          </header>

          <p className="quran-text analysis-ayah" lang="ar">
            {renderAyah(data, selected, setSelected)}
          </p>

          {/* تنبيه اختلاف العد على مستوى الاية — مرة واحدة هنا، كان
              يتكرر داخل كل بطاقة كلمة فيها مقطع غير مربوط */}
          {data.words.some((w) =>
            Object.values(w.analyses_by_source).some((segs) =>
              segs.some((s) => !s.is_linked_to_token)
            )
          ) && (
            <p className="notice-inline">
              عدّ الكلمات في هذه الآية يختلف بين النص والمصدر، فلم يُربط
              التحليل بكلمة بعينها ولا يُمكن التمييز.
            </p>
          )}

          <ol className="word-list">
            {data.words
              .filter((w) => selected === null || w.word_number === selected)
              .map((word) => (
                <li key={word.word_number} className="word-card">
                  <div className="word-card-head">
                    <span className="word-index">{word.word_number}</span>
                    <bdi className="word-surface" lang="ar">
                      {word.surface_text}
                    </bdi>
                    {/* الوسم للخبر لا للضجيج: «مصدر واحد» مع كل كلمة لا
                        يخبر شيئا — يبقى وسم الخلاف وغياب التحليل وما
                        يحمل قرارا، فيبرز المهم بدل أن يغرق في المكرر */}
                    {word.root_agreement !== "single_source" &&
                      word.root_agreement !== "no_root" && (
                        <span
                          className={`agreement-tag agreement-${word.root_agreement}`}
                        >
                          {AGREEMENT_LABELS[word.root_agreement]}
                        </span>
                      )}
                  </div>

                  {word.decision && (
                    <p className="decision-note">
                      <strong>
                        {DECISION_LABELS[word.decision.status] ??
                          word.decision.status}
                        :
                      </strong>{" "}
                      {word.decision.rationale}
                    </p>
                  )}

                  {Object.entries(word.analyses_by_source).map(
                    ([source, segments], _, allSources) => (
                      <div key={source} className="source-block">
                        {/* اسم المصدر مع الكلمة لا يذكر إلا عند تعدد
                            المصادر — والمصدر الواحد مذكور رأس الصفحة */}
                        {allSources.length > 1 && (
                          <p className="source-name">المصدر: {source}</p>
                        )}
                        <table className="segment-table">
                          <thead>
                            <tr>
                              <th>المقطع</th>
                              <th>القسم</th>
                              <th>الأصل</th>
                              <th>الجذر</th>
                            </tr>
                          </thead>
                          <tbody>
                            {segments.map((segment) => (
                              <tr key={segment.segment_number}>
                                <td data-label="المقطع">{segment.segment_number}</td>
                                <td data-label="القسم">{segment.pos_label ?? segment.tag}</td>
                                <td lang="ar" data-label="الأصل">
                                  {segment.lemma ? (
                                    <bdi>{segment.lemma}</bdi>
                                  ) : (
                                    "—"
                                  )}
                                </td>
                                <td lang="ar" data-label="الجذر">
                                  {segment.root ? (
                                    <Link
                                      href={`/root?r=${encodeURIComponent(
                                        segment.root
                                      )}`}
                                    >
                                      <bdi>{segment.root}</bdi>
                                    </Link>
                                  ) : (
                                    "—"
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {/* السمات الخام بحروفها اللاتينية علم لأهله لا
                            لمسار القراءة — خلف طية، ولا تحذف: هي نص
                            المصدر الذي يسند كل ما في الجدول */}
                        <details className="lex-details features-details">
                          <summary>
                            <span className="lex-book-info">
                              السمات كما في المصدر ({source})
                            </span>
                          </summary>
                          <ul className="features-raw">
                            {segments.map((segment) => (
                              <li key={segment.segment_number}>
                                <code dir="ltr">{segment.features}</code>
                              </li>
                            ))}
                          </ul>
                        </details>
                      </div>
                    )
                  )}

                  {Object.keys(word.analyses_by_source).length === 0 && (
                    <p className="unlinked-note">
                      لا يوجد تحليل مستورد لهذه الكلمة بعد.
                    </p>
                  )}
                </li>
              ))}
          </ol>

          {/* التفسير (§٢٠): مقاطع كلاسيكية مطوية، مداها من ارقام ايات
              المطبوع، وحارس المطابقة يثبت الربط او يسمه صراحة */}
          {ref &&
            tafsir &&
            tafsirMeta &&
            (() => {
              // ترتيب المفسرين بوفاة المؤلف — زمني لا تفضيلي (ADR-013)
              const here = tafsir
                .filter((p) => p.ayah_start <= ref.ayah && ref.ayah <= p.ayah_end)
                .sort((a, b) => {
                  const died = (w: string) =>
                    Number(tafsirMeta.works[w]?.author_died_hijri ?? 9999);
                  return died(a.work) - died(b.work);
                });
              if (here.length === 0) return null;
              return (
                <section className="lexicon-slot" aria-labelledby="tafsir-head">
                  <h2 id="tafsir-head" className="slot-head">
                    <span>التفسير</span>
                    <span className="lex-state has-text">
                      {here.length} {here.length > 2 ? "تفاسير" : "تفسير"} — افتح
                      ما تشاء
                    </span>
                  </h2>
                  {here.map((passage, i) => {
                    const work = tafsirMeta.works[passage.work];
                    if (!work) return null;
                    return (
                      <details className="lex-details" key={i}>
                        <summary>
                          <span className="lex-book-title">{work.title}</span>
                          <span className="lex-book-info">
                            {/* اسم المؤلف مختصرا: المصدر يذيله بوفاته
                                بين قوسين ونحن نعرضها موحدة بعده */}
                            {work.author
                              .split("(")[0]
                              .split("،")[0]
                              .trim()}{" "}
                            (ت{work.author_died_hijri}هـ) · الآيات{" "}
                            {passage.ayah_start}
                            {passage.ayah_end > passage.ayah_start
                              ? `–${passage.ayah_end}`
                              : ""}
                            {passage.page ? ` · ${passage.page}` : ""}
                          </span>
                        </summary>
                        <article className="sihah-entry openiti-entry">
                          <p className="sihah-text" lang="ar">
                            {passage.text}
                          </p>
                          <p className="sihah-provenance">
                            {work.title} — {work.author} (ت
                            {work.author_died_hijri}هـ)
                            {passage.page ? ` · ${passage.page}` : ""} · نصُّ
                            طبعة {work.editor} · {work.publisher}
                            {work.edition ? ` · ${work.edition}` : ""} ·{" "}
                            <a
                              href={work.source_url}
                              target="_blank"
                              rel="noreferrer noopener"
                            >
                              المصدر الرقمي (OpenITI)
                            </a>{" "}
                            · متنٌ كلاسيكي مستورد آليًّا — جهاز المحقِّق
                            مستبعَد، والنسبةُ إقرارٌ بالمصدر لا إذنٌ منه ·{" "}
                            {passage.anchored
                              ? "الربط بالآية مثبَت بمطابقة اقتباس المطبوع بنص المصحف"
                              : "رُبط بترتيب المطبوع وأرقام آياته — ولم تثبت المطابقة الآلية لاقتباسه"}
                            {work.notes ? ` · ${work.notes}` : ""}
                          </p>
                        </article>
                      </details>
                    );
                  })}
                </section>
              );
            })()}

          {/* بيان واحد آخر الصفحة — كان يطبع مرتين متتاليتين */}
          <div className="status-box notice">
            <p>
              {data.notice}
              {meta && (
                <>
                  {" "}
                  النص من إصدار <code>{meta.data_release}</code>، حالته{" "}
                  <strong>{meta.review_status}</strong>، ولقطة ثابتة بتاريخ{" "}
                  {meta.snapshot_at}. <Link href="/provenance">بيان الأصول</Link>
                </>
              )}
            </p>
          </div>
        </>
      )}
    </main>
  );
}
