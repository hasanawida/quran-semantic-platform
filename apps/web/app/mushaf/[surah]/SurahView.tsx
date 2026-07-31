"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { surahPage } from "../../lib/staticdata";

type Word = { word_number: number; char_start: number; char_end: number };

type AyahRow = {
  ayah_number: number;
  uthmani_text: string;
  words: Word[];
};

type SurahPage = {
  surah: {
    number: number;
    arabic_name: string;
    revelation_type: string;
    basmala_text: string | null;
    ayah_count: number;
  };
  version: {
    version_code: string;
    riwayah: string;
    script_type: string;
    counting_system: string;
    review_status: string;
  };
  ayahs: AyahRow[];
};

const STATUS_LABELS: Record<string, string> = {
  imported: "مستورد — غير معتمد",
  approved: "معتمد",
  published: "منشور",
};

const REVELATION_LABELS: Record<string, string> = {
  Meccan: "مكية",
  Medinan: "مدنية",
};

/** يعرض نص الآية **كما ورد حرفيًا** ويجعل كلماتها قابلة للنقر.
 *
 *  القاعدة نفسها المطبَّقة في صفحة التحليل الصرفي: يُقطَّع النص بمواضع
 *  الحروف التي يعطيها الخادم، فما بين الكلمات (علامات الوقف، رموز نهاية
 *  الآية، الفراغات) يخرج كما هو. لا يُعاد تركيب الآية من كلماتها أبدًا.
 */
function renderAyah(ayah: AyahRow, surah: number) {
  const text = ayah.uthmani_text;
  const words = [...ayah.words].sort((a, b) => a.char_start - b.char_start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  words.forEach((word) => {
    if (word.char_start < cursor || word.char_end > text.length) return;
    if (word.char_start > cursor) {
      parts.push(
        <span key={`g-${cursor}`}>{text.slice(cursor, word.char_start)}</span>
      );
    }
    {/* بلا title: تلميح المتصفح كان يقفز فوق النص القراني مع كل
        تحويم — والرابط نصه الكلمة نفسها */}
    parts.push(
      <Link
        key={`w-${word.word_number}`}
        href={`/ayah?s=${surah}&a=${ayah.ayah_number}#w${word.word_number}`}
        className="word-chip"
      >
        {text.slice(word.char_start, word.char_end)}
      </Link>
    );
    cursor = word.char_end;
  });

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return parts.length > 0 ? parts : text;
}

export default function SurahView({ surah }: { surah: number }) {
  const [data, setData] = useState<SurahPage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    surahPage(surah)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [surah]);

  // القادم من «الآية في سياق سورتها» يحمل `#a12`: قفزة المتصفح الأصلية
  // تقع قبل أن تُجلب الآيات وتُرسم فتخيب — فيُعاد النزول هنا بعد الرسم،
  // وتُعلَّم الآية المقصودة (خلفية وحدٌّ لا لونًا وحده) ليجدها البصر فورًا
  useEffect(() => {
    if (!data) return;
    const match = /^#a(\d+)$/.exec(window.location.hash);
    if (!match) return;
    const target = document.getElementById(`a${match[1]}`);
    if (!target) return;
    target.classList.add("ayah-target");
    // مهلةٌ قصيرة بعد الرسم: استرجاعُ التمرير في الموجّه يجري بعد هذا
    // الأثر فيبتلع النزول الفوري — قِيست الحال: يصل الصنف ولا يقع التمرير
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(() => {
      target.scrollIntoView({
        block: "center",
        behavior: still ? "auto" : "smooth",
      });
    }, 150);
    return () => window.clearTimeout(timer);
  }, [data]);

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>المصحف — السورة {surah}</span>
      </nav>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <header className="analysis-header">
            <h1>سورة {data.surah.arabic_name}</h1>
            <p className="root-stats">
              {REVELATION_LABELS[data.surah.revelation_type] ??
                data.surah.revelation_type}{" "}
              — {data.surah.ayah_count} آية
            </p>
            <span className="review-tag">
              {STATUS_LABELS[data.version.review_status] ??
                data.version.review_status}
            </span>
          </header>

          <nav className="surah-nav" aria-label="التنقل بين السور">
            {surah > 1 && (
              <Link href={`/mushaf/${surah - 1}`} className="nav-link">
                → السورة السابقة
              </Link>
            )}
            {surah < 114 && (
              <Link href={`/mushaf/${surah + 1}`} className="nav-link">
                السورة التالية ←
              </Link>
            )}
          </nav>

          {/* البسملة بيان للسورة لا آية فيها — عدا الفاتحة (آية مستقلة)
              وبراءة (لا بسملة). البيانات تأتي من الخادم لا تُكتب هنا. */}
          {data.surah.basmala_text && (
            <p className="quran-text basmala" lang="ar">
              {data.surah.basmala_text}
            </p>
          )}

          <ol className="mushaf-list">
            {data.ayahs.map((ayah) => (
              <li key={ayah.ayah_number} id={`a${ayah.ayah_number}`}>
                <p className="quran-text" lang="ar">
                  {renderAyah(ayah, surah)}
                  <Link
                    href={`/ayah?s=${surah}&a=${ayah.ayah_number}`}
                    className="ayah-marker"
                    aria-label={`الآية ${ayah.ayah_number} — التحليل الصرفي`}
                  >
                    {ayah.ayah_number}
                  </Link>
                </p>
              </li>
            ))}
          </ol>

          {/* سطر واحد: تفصيل الرواية والرسم والعد في بيان الاصول،
              وجملة «كل كلمة قابلة للنقر» ارشاد يكتشف بالاستعمال */}
          <p className="notice-inline">
            النص من إصدار <code>{data.version.version_code}</code> —{" "}
            <Link href="/provenance">بيان الأصول ←</Link>
          </p>
        </>
      )}
    </main>
  );
}
