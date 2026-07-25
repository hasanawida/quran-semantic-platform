"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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
    parts.push(
      <Link
        key={`w-${word.word_number}`}
        href={`/ayah/${surah}/${ayah.ayah_number}#w${word.word_number}`}
        className="word-chip"
        title={`تحليل الكلمة ${word.word_number}`}
      >
        {text.slice(word.char_start, word.char_end)}
      </Link>
    );
    cursor = word.char_end;
  });

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return parts.length > 0 ? parts : text;
}

export default function MushafPage() {
  const params = useParams<{ surah: string }>();
  const surah = Number(params.surah);
  const [data, setData] = useState<SurahPage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    fetch(`${API_URL}/surahs/${surah}/ayahs?limit=300`)
      .then(async (response) => {
        const payload = await response.json();
        if (cancelled) return;
        if (!response.ok || !payload?.data) {
          setError(payload?.error?.message ?? "تعذّر جلب السورة.");
          return;
        }
        setData(payload.data);
      })
      .catch(() => {
        if (!cancelled) setError("تعذّر الاتصال بالخدمة الخلفية.");
      });
    return () => {
      cancelled = true;
    };
  }, [surah]);

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
                    href={`/ayah/${surah}/${ayah.ayah_number}`}
                    className="ayah-marker"
                    aria-label={`الآية ${ayah.ayah_number} — التحليل الصرفي`}
                  >
                    {ayah.ayah_number}
                  </Link>
                </p>
              </li>
            ))}
          </ol>

          <div className="status-box notice">
            <p>
              النص من إصدار <code>{data.version.version_code}</code> (
              {data.version.riwayah} — {data.version.script_type} — العد{" "}
              {data.version.counting_system}). كل كلمة قابلة للنقر لعرض
              تحليلها الصرفي منسوبًا لمصدره.
            </p>
          </div>
        </>
      )}
    </main>
  );
}
