"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";

import {
  getLexicon,
  laneEntries,
  lookupWord,
  type LaneEntry,
  type Lexicon,
} from "../lib/staticdata";

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
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [lane, setLane] = useState<Record<string, LaneEntry[]>>({});

  useEffect(() => {
    getLexicon().then(setLexicon).catch(() => setLexicon(null));
  }, []);

  // مواد لِين لجذور النتيجة — تُجلب بعد ظهورها لا قبله
  useEffect(() => {
    if (!data?.found) return;
    const roots = [...new Set(data.readings.map((r) => r.root).filter(Boolean))];
    let live = true;
    Promise.all(
      roots.map(async (root) => [root!, await laneEntries(root!)] as const)
    ).then((pairs) => {
      if (!live) return;
      const next: Record<string, LaneEntry[]> = {};
      for (const [root, entries] of pairs) if (entries) next[root] = entries;
      setLane(next);
    });
    return () => {
      live = false;
    };
  }, [data]);

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
      <p className="page-lead">
        اكتب كلمةً كما تُرسم في المصحف، فتُعرض مواضعها كلها، وجذرها ولمّتها
        كما في المدونة القرآنية. والبحث يقع على صورةٍ مطبَّعة للمطابقة،
        والمعروض نصُّ الآية حرفيًا من الإصدار الموثق.
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
            <dl className="kv">
              <div>
                <dt>عدد المواضع</dt>
                <dd>{data.count}</dd>
              </div>
              <div>
                <dt>صورة البحث</dt>
                <dd>
                  <bdi>{data.form}</bdi>
                </dd>
              </div>
            </dl>
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
                لم يعطِ المصدر الصرفي جذرًا ولا لمّةً لهذه الصورة. ويُعلن
                ذلك ولا يُخمَّن.
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
                حُلِّل {data.analysed} من {data.count} موضعًا. والباقي في
                آياتٍ يخالف فيها ترقيمُ المصدر للكلمات تقطيعَنا، فلا
                يُنسب إليها تحليل — ويُعلن ذلك ولا يُخمَّن.
              </p>
            )}
          </section>

          {/* المادة المعجمية: موضعٌ مفتوحٌ ومتنٌ غير مُدخَل. يُعرض
              الفراغ بسببه ولا يُسدّ بمتنٍ مجهول الطبعة. */}
          {lexicon && data.readings.some((r) => r.root) && (
            <section className="lexicon-slot" aria-labelledby="lex-head">
              <h2 id="lex-head">المادة المعجمية</h2>
              {/* بالجذر لا بالقراءة: لمّتان من جذرٍ واحد مادةٌ واحدة */}
              {[...new Set(data.readings.map((r) => r.root).filter(Boolean))].map(
                (root) => {
                  const entries = lane[root!];
                  return (
                    <div key={root} className="lex-entry-block">
                      {/* حالتان لا واحدة: المعنى **العربي** فارغٌ دائمًا
                          اليوم، ولِين شاهدٌ إنجليزي بجانبه لا بديلٌ عنه.
                          ودمجُهما في سطرٍ واحد يوهم أن المادة امتلأت. */}
                      <p className="lex-entry">
                        <span className="lex-locator">
                          مادة <bdi>{root}</bdi>
                        </span>
                        <span className="lex-state">
                          المعنى بالعربية — غير مُدخَل
                        </span>
                        {entries?.length ? (
                          <span className="lex-state has-text">
                            شاهد إنجليزي: لِين — {entries.length}{" "}
                            {entries.length === 1 ? "مدخل" : "مداخل"}
                          </span>
                        ) : null}
                      </p>
                      {entries?.map((item) => (
                        <article key={item.key} className="lane-entry">
                          <p className="lane-head">
                            <code className="translit">{item.key}</code>
                            <span className="muted">
                              لِين، طبعة لندن ١٨٦٣ — ص {item.page}
                            </span>
                            <span className="lang-tag">إنجليزي</span>
                          </p>
                          {/* نصّ لِين كما هو. وعربيّته بترميز Perseus
                              اللاتيني تُترك على حالها ولا تُفكّ. */}
                          <p className="lane-text" lang="en" dir="ltr">
                            {item.text}
                          </p>
                        </article>
                      ))}
                    </div>
                  );
                }
              )}
              <p className="notice-inline">{lexicon.reason}</p>

              {/* النسبة **شرطُ إتاحةٍ منصوص** في ملف المصدر، لا مجاملة:
                  «You credit Perseus … whenever you use the document». */}
              {Object.keys(lane).length > 0 && lexicon.lane && (
                <p className="attribution" lang="en" dir="ltr">
                  {lexicon.lane.availability.attribution_required}
                </p>
              )}
              <details>
                <summary>
                  حال المعاجم المرشَّحة ({lexicon.sources.length})
                </summary>
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
              </details>
            </section>
          )}

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
                    <span className="muted"> — الكلمة {item.word_number}</span>
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

          <p className="source-note">
            النص من {data.meta.review_status === "imported" ? "إصدارٍ مستورد غير معتمد" : "الإصدار النشط"}{" "}
            (<Link href="/provenance">بيان الأصول</Link>). والجذر واللمّة
            منقولان عن المدونة القرآنية بجامعة ليدز، حالتهما «متحقَّق آليًّا»
            ولم يجتازا مراجعة المنصة.
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
