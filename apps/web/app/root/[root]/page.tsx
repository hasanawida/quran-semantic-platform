import type { Metadata } from "next";
import Link from "next/link";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type RootInfo = {
  display_root: string;
  normalized_root: string;
  status: string;
  confidence: string;
  occurrence_count: number;
  ayah_count: number;
};

type Occurrence = {
  surah_number: number;
  surah_name: string;
  ayah_number: number;
  uthmani_text: string;
  word_indexes: number[];
};

type Payload = {
  root: RootInfo;
  occurrences: Occurrence[];
  pagination: { total_ayahs: number; offset: number; limit: number };
};

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  imported: "مستورد — غير معتمد",
  machine_generated: "آلي فقط",
  under_review: "قيد المراجعة",
  approved: "معتمد",
  published: "منشور",
  disputed: "مختلف فيه",
  rejected: "مرفوض",
  deprecated: "متقادم",
};

const ARABIC_LETTER = /[ء-يٱ]/;
const PAGE_SIZE = 20;

async function fetchRoot(root: string): Promise<Payload | null> {
  try {
    const response = await fetch(
      `${API_URL}/roots/${encodeURIComponent(root)}/occurrences?limit=${PAGE_SIZE}`,
      { next: { revalidate: 300 } }
    );
    if (!response.ok) return null;
    const payload = await response.json();
    return payload?.data ?? null;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ root: string }>;
}): Promise<Metadata> {
  const { root } = await params;
  const decoded = decodeURIComponent(root);
  const data = await fetchRoot(decoded);
  if (!data) {
    return { title: `الجذر ${decoded}`, robots: { index: false } };
  }
  const status = STATUS_LABELS[data.root.status] ?? data.root.status;
  // الحالة العلمية جزء من البطاقة الوصفية: لا تُشارك نتيجة تبدو معتمدة
  // وهي ليست كذلك.
  const description =
    `الجذر ${data.root.display_root}: ${data.root.occurrence_count} موضعًا في ` +
    `${data.pagination.total_ayahs} آية. حالة البيانات: ${status}.`;
  return {
    title: `الجذر ${data.root.display_root}`,
    description,
    openGraph: { title: `الجذر ${data.root.display_root}`, description },
    alternates: { canonical: `/root/${encodeURIComponent(decoded)}` },
  };
}

/** يعرض نص الآية حرفيًا مع تمييز كلمات الجذر — بلا تغيير للنص. */
function AyahText({ text, wordIndexes }: { text: string; wordIndexes: number[] }) {
  const parts = text.split(" ");
  const targets = new Set(wordIndexes);
  let counter = 0;
  return (
    <p className="quran-text" lang="ar">
      {parts.map((part, index) => {
        const isWord = ARABIC_LETTER.test(part);
        if (isWord) counter += 1;
        const highlighted = isWord && targets.has(counter);
        return (
          <span key={index}>
            {highlighted ? <mark>{part}</mark> : part}
            {index < parts.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}

export default async function RootPage({
  params,
}: {
  params: Promise<{ root: string }>;
}) {
  const { root } = await params;
  const decoded = decodeURIComponent(root);
  const data = await fetchRoot(decoded);

  if (!data) {
    return (
      <main id="main" className="container">
        <div className="status-box error" role="alert">
          <p>
            لم يتم العثور على جذر بهذا الإدخال، أو تعذّر الاتصال بالخدمة.{" "}
            <Link href="/">جرّب البحث</Link>
          </p>
        </div>
      </main>
    );
  }

  const { root: info, occurrences, pagination } = data;

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>الجذر {info.display_root}</span>
      </nav>

      <header className="analysis-header">
        <h1>
          الجذر <bdi>{info.display_root}</bdi>
        </h1>
        <p className="root-stats">
          {info.occurrence_count} موضعًا في {pagination.total_ayahs} آية
        </p>
        <span className="review-tag">
          {STATUS_LABELS[info.status] ?? info.status}
        </span>
      </header>

      <ol className="ayah-list">
        {occurrences.map((occ) => (
          <li
            key={`${occ.surah_number}:${occ.ayah_number}`}
            className="ayah-item"
          >
            <p className="ayah-ref">
              سورة {occ.surah_name} — الآية {occ.ayah_number}
              <span className="ayah-ref-num">
                ({occ.surah_number}:{occ.ayah_number})
              </span>
            </p>
            <AyahText text={occ.uthmani_text} wordIndexes={occ.word_indexes} />
            <p className="ayah-actions">
              <Link href={`/ayah/${occ.surah_number}/${occ.ayah_number}`}>
                التحليل الصرفي ←
              </Link>
              {" · "}
              <Link href={`/mushaf/${occ.surah_number}#a${occ.ayah_number}`}>
                في سياق سورتها ←
              </Link>
            </p>
          </li>
        ))}
      </ol>

      {pagination.total_ayahs > occurrences.length && (
        <p className="ayah-actions">
          <Link href={`/?root=${encodeURIComponent(decoded)}`}>
            عرض بقية الآيات ({pagination.total_ayahs}) في صفحة البحث ←
          </Link>
        </p>
      )}

      <div className="status-box notice">
        <p>
          النص من مشروع تنزيل والجذور من المدونة القرآنية بجامعة ليدز —
          بيانات مستوردة موثقة ببصمات، حالتها{" "}
          <strong>{STATUS_LABELS[info.status] ?? info.status}</strong>، ولم
          تخضع بعد لمراجعة المنصة المزدوجة.{" "}
          <Link href="/provenance">بيان الأصول الكامل</Link>
        </p>
      </div>
    </main>
  );
}
