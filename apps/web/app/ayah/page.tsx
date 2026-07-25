"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ayahAnalysis, getMeta, type Meta } from "../lib/staticdata";

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
            <p className="root-stats">{data.word_count} كلمة</p>
          </header>

          <p className="quran-text analysis-ayah" lang="ar">
            {renderAyah(data, selected, setSelected)}
          </p>

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
                    <span
                      className={`agreement-tag agreement-${word.root_agreement}`}
                    >
                      {AGREEMENT_LABELS[word.root_agreement]}
                    </span>
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
                    ([source, segments]) => (
                      <div key={source} className="source-block">
                        <p className="source-name">المصدر: {source}</p>
                        <table className="segment-table">
                          <thead>
                            <tr>
                              <th>المقطع</th>
                              <th>القسم</th>
                              <th>الأصل</th>
                              <th>الجذر</th>
                              <th>السمات (كما في المصدر)</th>
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
                                <td className="features-cell" data-label="السمات">
                                  <code dir="ltr">{segment.features}</code>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {segments.some((s) => !s.is_linked_to_token) && (
                          <p className="unlinked-note">
                            عدّ الكلمات في هذه الآية يختلف بين النص والمصدر،
                            فلم يُربط التحليل بكلمة بعينها ولا يُمكن التمييز.
                          </p>
                        )}
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

          <div className="status-box notice">
            <p>{data.notice}</p>
          </div>
        </>
      )}


      {data && meta && (
        <div className="status-box notice">
          <p>
            {data.notice} النص من إصدار <code>{meta.data_release}</code>،
            حالته <strong>{meta.review_status}</strong>، ولقطة ثابتة بتاريخ{" "}
            {meta.snapshot_at}. <Link href="/provenance">بيان الأصول</Link>
          </p>
        </div>
      )}
    </main>
  );
}

// ثم: Remove-Item -Recurse -Force apps/web/app/ayah/[surah]
