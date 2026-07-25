"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  getMeta,
  listSurahs,
  searchAyahs,
  type Meta,
  type Surah,
} from "../lib/staticdata";

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

export default function MushafIndexPage() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [surahs, setSurahs] = useState<Surah[] | null>(null);
  const [allSurahs, setAllSurahs] = useState<Surah[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [search, setSearch] =
    useState<Awaited<ReturnType<typeof searchAyahs>> | null>(null);
  const [error, setError] = useState("");

  const run = useCallback(async (raw: string, from: number) => {
    setError("");
    const text = raw.trim();
    const latin = toLatinDigits(text);
    const reference = REFERENCE.exec(latin);
    const isBareNumber = BARE_NUMBER.test(latin);
    // مرجع رقمي أو رقم سورة لا يُبحث به في نص الآيات — ضجيج لا نتيجة
    const wantsTextSearch = text.length >= 2 && !reference && !isBareNumber;
    try {
      const [list, all, info] = await Promise.all([
        listSurahs(text || undefined),
        listSurahs(),
        getMeta(),
      ]);
      setSurahs(list);
      setAllSurahs(all);
      setMeta(info);
      setSearch(
        wantsTextSearch ? await searchAyahs(text, from, PAGE_SIZE) : null
      );
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  // الرابط العميق يعمل: /mushaf?q=…&offset=… يُقرأ من العنوان لا من الخادم
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("q") ?? "";
    const from = Math.max(0, Number(params.get("offset") ?? 0) || 0);
    setQuery(initial);
    setOffset(from);
    run(initial, from);
  }, [run]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const url = new URL(window.location.href);
    if (query.trim()) url.searchParams.set("q", query.trim());
    else url.searchParams.delete("q");
    url.searchParams.delete("offset");
    window.history.pushState(null, "", url);
    setOffset(0);
    run(query, 0);
  }

  function goto(next: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("offset", String(next));
    window.history.pushState(null, "", url);
    setOffset(next);
    run(query, next);
    window.scrollTo({ top: 0 });
  }

  const latin = toLatinDigits(query.trim());
  const reference = REFERENCE.exec(latin);
  const noActiveVersion = !allSurahs || allSurahs.length === 0;
  const reviewLabel = meta
    ? STATUS_LABELS[meta.review_status] ?? meta.review_status
    : "";

  // القفز بالمرجع (2:255) — يُتحقَّق من صحته بعدد آيات السورة **كما جاء
  // من البيانات** لا بثابت مكتوب، فيوافق نظام العدّ المعلن لهذا الإصدار.
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

      <form className="search" onSubmit={submit}>
        <label htmlFor="mushaf-q">ابحث في السور والآيات</label>
        <div className="search-row">
          <input
            id="mushaf-q"
            name="q"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
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
              <Link href={`/ayah?s=${jump.surah.number}&a=${jump.ayah}`}>
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
                    <Link href={`/ayah?s=${hit.surah_number}&a=${hit.ayah_number}`}>
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
