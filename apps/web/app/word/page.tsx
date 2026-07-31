"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";

import { LexiconSlot } from "../components/LexiconSlot";
import { lookupWord } from "../lib/staticdata";

type Result = Awaited<ReturnType<typeof lookupWord>>;

const PAGE_SIZE = 20;

/**
 * نص الآية حرفيًا، والكلمة المطلوبة مميَّزة **بمواضع الحروف** لا بإعادة
 * تركيب النص من كلماته. فإن غاب الموضع عُرض النص كما هو بلا تمييز —
 * ولا يُخمَّن موضعٌ ولا يُعاد بناء الآية.
 */
function AyahLine({
  text,
  start,
  end,
}: {
  text: string;
  start: number | null;
  end: number | null;
}) {
  if (start === null || end === null) {
    return (
      <p className="quran-text" lang="ar">
        {text}
      </p>
    );
  }
  return (
    <p className="quran-text" lang="ar">
      {text.slice(0, start)}
      <mark>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </p>
  );
}

function WordSearch() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Result>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");


  const run = useCallback(async (text: string, from: number) => {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      setData(await lookupWord(text, from, PAGE_SIZE));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  // الرابط يحمل الاستعلام فتصير النتيجة قابلة للمشاركة والرجوع إليها
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q") ?? "";
    if (q) {
      setQuery(q);
      void run(q, 0);
    }
  }, [run]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const url = new URL(window.location.href);
    if (query.trim()) url.searchParams.set("q", query.trim());
    else url.searchParams.delete("q");
    url.searchParams.delete("offset");
    window.history.replaceState(null, "", url);
    setOffset(0);
    void run(query, 0);
  }

  function turn(next: number) {
    setOffset(next);
    void run(query, next);
  }

  return (
    <main id="main" className="container">
      <header className="page-head">
        <h1>بحث الكلمة</h1>
      </header>
      {/* جملة واحدة: شرح التطبيع التقني يظهر في اشعار المطابقة
          التقريبية السياقي حين يقع فعلا */}
      <p className="page-lead">
        اكتب كلمةً كما تُرسم في المصحف، فتُعرض مواضعها كلها وجذرها
        ولمّتها كما في المدونة القرآنية.
      </p>

      <form className="search" onSubmit={submit}>
        <label htmlFor="word-q">الكلمة</label>
        <div className="search-row">
          <input
            id="word-q"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="مثال: العالمين أو يعلمون أو الكتاب"
            lang="ar"
            dir="rtl"
            autoComplete="off"
          />
          <button className="primary" disabled={busy}>
            {busy ? "جارٍ البحث…" : "بحث"}
          </button>
        </div>
      </form>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && !data.found && (
        <div className="status-box" role="status">
          <p>
            لا توجد كلمة بهذه الصورة في المصحف — بُحث بالصورة{" "}
            <bdi>{data.form}</bdi>.
          </p>
          {data.near.length > 0 && (
            <p className="near">
              أقرب الصور الموجودة:{" "}
              {data.near.map((form, i) => (
                <span key={form}>
                  {i > 0 ? " · " : ""}
                  <button
                    type="button"
                    className="linklike"
                    onClick={() => {
                      setQuery(form);
                      void run(form, 0);
                    }}
                  >
                    <bdi>{form}</bdi>
                  </button>
                </span>
              ))}
            </p>
          )}
        </div>
      )}

      {data && data.found && (
        <>
          <section className="word-summary" aria-label="بيان الكلمة">
            <h2>
              <bdi lang="ar">{data.query}</bdi>
            </h2>
            {/* لا صف لعدد المواضع (مذكور في عنوان المواضع) ولا لصورة
                البحث الا حين تخالف ما كتبه القارئ — عندها فقط تفيد */}
            {data.form !== data.typed && (
              <dl className="kv">
                <div>
                  <dt>صورة البحث</dt>
                  <dd>
                    <bdi>{data.form}</bdi>
                  </dd>
                </div>
              </dl>
            )}
            {data.layer === "skeleton" && (
              <p className="notice-inline">
                لم توجد <bdi>{data.typed}</bdi> بصورتها، ووُجدت{" "}
                <bdi>{data.form}</bdi> بمطابقة الهيكل — أي بتجاهل فروق رسم
                الألف والهمزة. والمعروض هو مواضع الصورة الموجودة في المصحف.
              </p>
            )}

            <h3>الجذر واللمّة</h3>
            {data.readings.length === 0 ? (
              <p className="muted">
                لم يعطِ المصدر الصرفي جذرًا ولا لمّةً لهذه الصورة.
              </p>
            ) : (
              <ul className="readings">
                {data.readings.map((reading, i) => (
                  <li key={i}>
                    {reading.root ? (
                      <Link href={`/root?r=${encodeURIComponent(reading.root)}`}>
                        الجذر <bdi>{reading.root}</bdi>
                      </Link>
                    ) : (
                      <span className="muted">بلا جذر في المصدر</span>
                    )}
                    {reading.lemma && (
                      <>
                        {" · اللمّة "}
                        <bdi>{reading.lemma}</bdi>
                      </>
                    )}
                    {data.readings.length > 1 && (
                      <span className="muted"> — {reading.count} موضعًا</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {data.readings.length > 1 && (
              <p className="notice-inline">
                للصورة الواحدة أكثر من تحليل في المصدر. تُعرض كلها بلا
                ترجيح، وعددُ مواضع كلٍّ بجانبه.
              </p>
            )}
            {data.analysed < data.count && (
              <p className="notice-inline">
                حُلِّل {data.analysed} من {data.count} موضعًا — الباقي بلا
                تحليل في المصدر لاختلاف ترقيم الكلمات.
              </p>
            )}
          </section>

          <LexiconSlot
            roots={data.readings.map((r) => r.root).filter(Boolean) as string[]}
          />

          <section aria-labelledby="occ-head">
            <h2 id="occ-head">المواضع — {data.pagination.total} موضعًا</h2>
            <ol className="occurrences">
              {data.occurrences.map((item) => (
                <li key={`${item.surah_number}:${item.ayah_number}:${item.word_number}`}>
                  <p className="ref">
                    <Link
                      href={`/ayah?s=${item.surah_number}&a=${item.ayah_number}`}
                    >
                      {item.surah_name} {item.surah_number}:{item.ayah_number}
                    </Link>
                    {/* رقم الكلمة لا يلزم الا حين لا تمييز في النص */}
                    {item.char_start === null && (
                      <span className="muted"> — الكلمة {item.word_number}</span>
                    )}
                  </p>
                  <AyahLine
                    text={item.uthmani_text}
                    start={item.char_start}
                    end={item.char_end}
                  />
                </li>
              ))}
            </ol>

            {data.pagination.total > PAGE_SIZE && (
              <nav className="pager" aria-label="تنقل النتائج">
                <button
                  type="button"
                  disabled={offset === 0}
                  onClick={() => turn(Math.max(0, offset - PAGE_SIZE))}
                >
                  السابق
                </button>
                <span>
                  {offset + 1}–
                  {Math.min(offset + PAGE_SIZE, data.pagination.total)} من{" "}
                  {data.pagination.total}
                </span>
                <button
                  type="button"
                  disabled={offset + PAGE_SIZE >= data.pagination.total}
                  onClick={() => turn(offset + PAGE_SIZE)}
                >
                  التالي
                </button>
              </nav>
            )}
          </section>

          {/* سطر واحد بدل فقرة شارحة تتكرر بعد كل بحث */}
          <p className="notice-inline">
            النص:{" "}
            {data.meta.review_status === "imported"
              ? "إصدار مستورد غير معتمد"
              : "الإصدار النشط"}{" "}
            · التحليل: المدونة القرآنية، متحقَّق آليًّا —{" "}
            <Link href="/provenance">بيان الأصول ←</Link>
          </p>
        </>
      )}
    </main>
  );
}

export default function WordPage() {
  return (
    <Suspense fallback={null}>
      <WordSearch />
    </Suspense>
  );
}
