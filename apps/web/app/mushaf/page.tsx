import type { Metadata } from "next";
import Link from "next/link";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Surah = {
  number: number;
  arabic_name: string;
  revelation_type: string;
  ayah_count: number;
};

type MatchWord = { word_number: number; char_start: number; char_end: number };

type SearchHit = {
  surah_number: number;
  surah_name: string;
  ayah_number: number;
  uthmani_text: string;
  match_kind: "exact" | "approximate";
  match_words: MatchWord[];
};

type SearchPayload = {
  normalized_query: string;
  skeleton_query: string | null;
  version: {
    version_code: string;
    riwayah: string;
    script_type: string;
    counting_system: string;
    review_status: string;
  };
  results: SearchHit[];
  pagination: { total: number; offset: number; limit: number };
  scope_note: string;
};

type Meta = {
  data_release: string;
  review_status: string;
  warning: string;
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

const PAGE_SIZE = 20;

/** أرقام عربية-هندية إلى لاتينية — تحويل أرقام لا تطبيع نص عربي. */
function toLatinDigits(value: string) {
  return value.replace(/[٠-٩]/g, (digit) =>
    String(digit.charCodeAt(0) - 0x0660)
  );
}

const REFERENCE = /^(\d{1,3})\s*[:،.\-/]\s*(\d{1,3})$/;
const BARE_NUMBER = /^\d{1,3}$/;

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_URL}${path}`, {
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;
    const payload = await response.json();
    return (payload?.data ?? null) as T | null;
  } catch {
    return null;
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const meta = await fetchJson<Meta>("/meta");
  const status = meta ? STATUS_LABELS[meta.review_status] ?? meta.review_status : "";
  const description = meta
    ? `فهرست سور المصحف مع البحث في أسماء السور وفي نص الآيات. إصدار النص: ${meta.data_release}. حالة البيانات: ${status}.`
    : "فهرست سور المصحف مع البحث في أسماء السور وفي نص الآيات.";
  return {
    title: "فهرست المصحف",
    description,
    openGraph: { title: "فهرست المصحف", description },
    alternates: { canonical: "/mushaf" },
  };
}

/** يعرض نص الآية **كما ورد حرفيًا** ويضع علامة على الكلمات المطابقة.
 *
 *  النمط نفسه المعتمد في صفحة السورة: القطع بمواضع الحروف التي يعطيها
 *  الخادم من جدول الكلمات، وما بين الكلمات (علامات الوقف والفراغات)
 *  يخرج كما هو. لا يُعاد تركيب النص من كلماته، ولا تُحسب مواضع التمييز
 *  في الواجهة — فمواضع المطابقة في النص المطبَّع لا تصلح مؤشرًا في نص
 *  العرض إطلاقًا (النصان مختلفان طولًا ومحارف).
 */
function MarkedAyah({ hit }: { hit: SearchHit }) {
  const text = hit.uthmani_text;
  const words = [...hit.match_words].sort((a, b) => a.char_start - b.char_start);
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
      <mark key={`w-${word.word_number}`}>
        {text.slice(word.char_start, word.char_end)}
      </mark>
    );
    cursor = word.char_end;
  });

  if (cursor < text.length) {
    parts.push(<span key="tail">{text.slice(cursor)}</span>);
  }

  return (
    <p className="quran-text" lang="ar">
      {parts.length > 0 ? parts : text}
    </p>
  );
}

export default async function MushafIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; offset?: string }>;
}) {
  const params = await searchParams;
  const query = (params.q ?? "").trim();
  const offset = Math.max(0, Number(params.offset ?? 0) || 0);

  const latin = toLatinDigits(query);
  const reference = REFERENCE.exec(latin);
  const isBareNumber = BARE_NUMBER.test(latin);
  // مرجع رقمي أو رقم سورة لا يُبحث به في نص الآيات — يعطي ضجيجًا لا نتيجة
  const wantsTextSearch = query.length >= 2 && !reference && !isBareNumber;

  const [surahs, meta, search] = await Promise.all([
    fetchJson<Surah[]>(
      query ? `/surahs?q=${encodeURIComponent(query)}` : "/surahs"
    ),
    fetchJson<Meta>("/meta"),
    wantsTextSearch
      ? fetchJson<SearchPayload>(
          `/search/ayahs?q=${encodeURIComponent(query)}` +
            `&limit=${PAGE_SIZE}&offset=${offset}`
        )
      : Promise.resolve(null),
  ]);

  // القائمة الكاملة لازمة للتحقق من صحة المرجع (عدد آيات السورة)
  const allSurahs = query ? await fetchJson<Surah[]>("/surahs") : surahs;
  const noActiveVersion = !allSurahs || allSurahs.length === 0;

  let jump: { surah: Surah; ayah: number } | null = null;
  let jumpError = "";
  if (reference && allSurahs) {
    const target = allSurahs.find((s) => s.number === Number(reference[1]));
    const ayah = Number(reference[2]);
    if (!target) {
      jumpError = "لا سورة بهذا الرقم — أرقام السور من 1 إلى 114.";
    } else if (ayah < 1 || ayah > target.ayah_count) {
      jumpError =
        `سورة ${target.arabic_name} ${target.ayah_count} آية في العدّ ` +
        `المعلن لهذا الإصدار، فلا آية برقم ${ayah}.`;
    } else {
      jump = { surah: target, ayah };
    }
  }

  const reviewLabel = meta
    ? STATUS_LABELS[meta.review_status] ?? meta.review_status
    : "";

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>فهرست المصحف</span>
      </nav>

      <header className="page-head">
        <h1>فهرست المصحف</h1>
        {meta && <span className="review-tag">{reviewLabel}</span>}
      </header>
      <p className="page-lead">
        اكتب اسم سورة أو رقمها، أو مرجعًا مثل ٢:٢٥٥، أو كلمةً من آية —
        فالحقل واحد يفهم الثلاثة.
      </p>

      <form className="search" action="/mushaf" method="get">
        <label htmlFor="mushaf-q">ابحث في السور والآيات</label>
        <div className="search-row">
          <input
            id="mushaf-q"
            name="q"
            defaultValue={query}
            autoComplete="off"
            maxLength={100}
          />
          <button className="primary">بحث</button>
        </div>
        <p className="hint">
          تُقبل صور الهمزة كلها والتاء المربوطة والهاء، والأرقام العربية
          واللاتينية معًا. وفروق الرسم العثماني تُعالَج بطبقة مطابقة
          تقريبية موسومة في النتائج.
        </p>
      </form>

      <div aria-live="polite" role="status">
        {jumpError && (
          <div className="status-box error">
            <p>{jumpError}</p>
          </div>
        )}
        {jump && (
          <div className="status-box success">
            <p>
              انتقال مباشر إلى{" "}
              <Link href={`/mushaf/${jump.surah.number}#a${jump.ayah}`}>
                سورة {jump.surah.arabic_name} — الآية {jump.ayah}
              </Link>
              {" · "}
              <Link href={`/ayah/${jump.surah.number}/${jump.ayah}`}>
                التحليل الصرفي
              </Link>
            </p>
          </div>
        )}
      </div>

      {noActiveVersion && (
        <div className="status-box error" role="alert">
          <p>
            لا يوجد إصدار نص مفعَّل، أو تعذّر الاتصال بالخدمة الخلفية — فلا
            يمكن عرض الفهرست.
          </p>
        </div>
      )}

      {!noActiveVersion && (
        <section className="section" aria-labelledby="surahs-head">
          <h2 id="surahs-head">
            السور{query && surahs ? ` — ${surahs.length} نتيجة` : ""}
          </h2>
          {surahs && surahs.length > 0 ? (
            <ol className="surah-grid">
              {surahs.map((surah) => (
                <li key={surah.number} className="surface">
                  <Link href={`/mushaf/${surah.number}`}>
                    <span className="word-index">{surah.number}</span>
                    <span>
                      <span className="surah-name">{surah.arabic_name}</span>
                      <span className="surah-meta">
                        {REVELATION_LABELS[surah.revelation_type] ??
                          surah.revelation_type}{" "}
                        — {surah.ayah_count} آية
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="page-lead">لا سورة تطابق هذا الطلب.</p>
          )}
        </section>
      )}

      {search && (
        <section className="section" aria-labelledby="ayahs-head">
          <h2 id="ayahs-head">في نص الآيات — {search.pagination.total} آية</h2>
          <p className="list-toolbar">
            <span>
              بُحث بالصورة <bdi>{search.normalized_query}</bdi>
              {search.skeleton_query
                ? " ومعها طبقة تقريبية لفروق الرسم العثماني"
                : ""}
            </span>
          </p>

          {search.results.length === 0 ? (
            <p className="page-lead">لا آية تطابق هذا الطلب.</p>
          ) : (
            <ol className="ayah-list">
              {search.results.map((hit) => (
                <li
                  key={`${hit.surah_number}:${hit.ayah_number}`}
                  className="ayah-item"
                >
                  <p className="ayah-ref">
                    سورة {hit.surah_name} — الآية {hit.ayah_number}
                    <span className="ayah-ref-num">
                      ({hit.surah_number}:{hit.ayah_number})
                    </span>
                    {hit.match_kind === "approximate" && (
                      <span className="chip is-caution">
                        مطابقة تقريبية — فروق الرسم العثماني
                      </span>
                    )}
                  </p>
                  <MarkedAyah hit={hit} />
                  <p className="ayah-actions">
                    <Link href={`/ayah/${hit.surah_number}/${hit.ayah_number}`}>
                      التحليل الصرفي ←
                    </Link>
                    {" · "}
                    <Link
                      href={`/mushaf/${hit.surah_number}#a${hit.ayah_number}`}
                    >
                      في سياق سورتها ←
                    </Link>
                  </p>
                </li>
              ))}
            </ol>
          )}

          <p className="ayah-actions">
            {offset > 0 && (
              <Link
                href={`/mushaf?q=${encodeURIComponent(query)}&offset=${Math.max(
                  0,
                  offset - PAGE_SIZE
                )}`}
              >
                → الصفحة السابقة
              </Link>
            )}
            {offset + PAGE_SIZE < search.pagination.total && (
              <>
                {offset > 0 ? " · " : ""}
                <Link
                  href={`/mushaf?q=${encodeURIComponent(query)}&offset=${
                    offset + PAGE_SIZE
                  }`}
                >
                  الصفحة التالية ←
                </Link>
              </>
            )}
          </p>

          <div className="status-box notice">
            <p>{search.scope_note}</p>
          </div>
        </section>
      )}

      {meta && (
        <div className="status-box notice">
          <p>
            النص من إصدار <code>{meta.data_release}</code>، حالته{" "}
            <strong>{reviewLabel}</strong>. {meta.warning}{" "}
            <Link href="/provenance">بيان الأصول الكامل</Link>
          </p>
        </div>
      )}
    </main>
  );
}
