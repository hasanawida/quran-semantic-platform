"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { LexiconSlot } from "./components/LexiconSlot";
import { rootOccurrences } from "./lib/staticdata";
const PAGE_SIZE = 10;

// تعريب حالات السجل القادمة من الخلفية
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

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "success";
      root: RootInfo;
      occurrences: Occurrence[];
      totalAyahs: number;
      loadingMore: boolean;
    }
  | { kind: "error"; message: string };

const ARABIC_LETTER = /[ء-يٱ]/;

/** عرض نص الآية كما هو حرفيًا مع تمييز كلمات الجذر دون أي تغيير للنص */
function AyahText({
  text,
  wordIndexes,
}: {
  text: string;
  wordIndexes: number[];
}) {
  const tokens = text.split(" ");
  const targets = new Set(wordIndexes);
  let wordCounter = 0;
  return (
    <p className="quran-text" lang="ar">
      {tokens.map((token, i) => {
        const isWord = ARABIC_LETTER.test(token);
        if (isWord) wordCounter += 1;
        const highlighted = isWord && targets.has(wordCounter);
        return (
          <span key={i}>
            {highlighted ? <mark>{token}</mark> : token}
            {i < tokens.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}

function AlertIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const [quranSize, setQuranSize] = useState(1.75);
  const lastQueryRef = useRef("");

  function applyQuranSize(next: number) {
    const clamped = Math.min(3, Math.max(1.25, next));
    setQuranSize(clamped);
    document.documentElement.style.setProperty(
      "--quran-font-size",
      `${clamped}rem`
    );
  }

  async function fetchOccurrences(
    rootQuery: string,
    offset: number
  ): Promise<{
    root: RootInfo;
    occurrences: Occurrence[];
    pagination: { total_ayahs: number };
  }> {
    // البيانات تُقرأ من لقطة ثابتة لا من خدمة: لا مهلة ولا إلغاء طلب.
    // وتُخزَّن بعد أول قراءة، فالبحث الثاني بلا شبكة أصلًا.
    const data = await rootOccurrences(rootQuery, offset, PAGE_SIZE);
    if (!data) {
      throw new Error("لم يُعثر على جذر بهذا الإدخال في هذه اللقطة.");
    }
    return data;
  }

  const runSearch = useCallback(async (rootQuery: string) => {
    setState({ kind: "loading" });
    lastQueryRef.current = rootQuery;
    try {
      const data = await fetchOccurrences(rootQuery, 0);
      setState({
        kind: "success",
        root: data.root,
        occurrences: data.occurrences,
        totalAyahs: data.pagination.total_ayahs,
        loadingMore: false,
      });
    } catch (err) {
      const aborted = (err as Error).name === "AbortError";
      setState({
        kind: "error",
        message: aborted
          ? "انتهت مهلة الطلب. تحقق من تشغيل الخدمة الخلفية ثم أعد المحاولة."
          : (err as Error).message || "تعذر الاتصال بالخدمة الخلفية.",
      });
    }
    // fetchOccurrences ثابت الهوية عمليًا (لا يعتمد على حالة)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // فتح الصفحة بجذر جاهز: /?root=ق و ل (من صفحة التحليل الصرفي)
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("root");
    if (initial) {
      setQuery(initial);
      runSearch(initial);
    }
  }, [runSearch]);

  async function search(event: FormEvent) {
    event.preventDefault();
    await runSearch(query);
  }

  async function loadMore() {
    if (state.kind !== "success" || state.loadingMore) return;
    setState({ ...state, loadingMore: true });
    try {
      const data = await fetchOccurrences(
        lastQueryRef.current,
        state.occurrences.length
      );
      setState({
        kind: "success",
        root: state.root,
        occurrences: [...state.occurrences, ...data.occurrences],
        totalAyahs: data.pagination.total_ayahs,
        loadingMore: false,
      });
    } catch {
      setState({ ...state, loadingMore: false });
    }
  }

  const success = state.kind === "success" ? state : null;

  return (
    <main id="main">
      <section className="hero container">
        <p className="eyebrow">بحث لغوي موثق وقابل للمراجعة</p>
        <h1>منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم</h1>
        <p className="lead">
          اكتب جذرًا عربيًا فتظهر جميع الآيات التي ورد فيها، مع تمييز
          الكلمات المشتقة منه — من نص موثق ببصمة رقمية.
        </p>

        <form className="search" onSubmit={search}>
          <label htmlFor="root-input">ابحث بجذر عربي</label>
          <div className="search-row">
            <input
              id="root-input"
              name="root"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="مثال: ع ص ر أو سأل أو قرأ"
              required
              autoComplete="off"
            />
            <button className="primary" disabled={state.kind === "loading"}>
              {state.kind === "loading" ? "جارٍ البحث…" : "بحث بالجذر"}
            </button>
          </div>
          <p className="hint">
            تُقبل صيغ الكتابة المختلفة: بمسافات، بشرطات، أو متصلة — وصور
            الهمزة كلها (سأل، سءل، سؤل) تصل إلى الجذر نفسه.
          </p>
        </form>

        <div aria-live="polite" role="status">
          {success && (
            <p className="visually-hidden">
              وُجد الجذر {success.root.display_root} في {success.totalAyahs}{" "}
              آية.
            </p>
          )}
          {state.kind === "error" && (
            <div className="status-box error">
              <AlertIcon />
              <p>{state.message}</p>
            </div>
          )}
        </div>

        {success && (
          <section className="results" aria-label="نتائج البحث">
            <div className="root-card">
              <div>
                <h2 className="root-title">
                  الجذر: <bdi>{success.root.display_root}</bdi>
                </h2>
                <p className="root-stats">
                  {success.root.occurrence_count} موضعًا في{" "}
                  {success.totalAyahs} آية
                </p>
              </div>
              <div className="root-card-side">
                <span className="review-tag">
                  {STATUS_LABELS[success.root.status] ?? success.root.status}
                </span>
                <Link
                  href={`/root?r=${encodeURIComponent(lastQueryRef.current)}`}
                  className="nav-link"
                >
                  رابط ثابت لهذا الجذر ←
                </Link>
              </div>
            </div>

            {/* المادة المعجمية هنا أيضًا: هذا مسار البحث الرئيس، وكانت
                على /root و/word وحدهما — فمن بحث من الرئيسة لم يرَ متنًا. */}
            <LexiconSlot roots={[success.root.display_root]} />

            <div className="list-toolbar">
              <span id="font-size-label">حجم النص القرآني</span>
              <div
                className="font-controls"
                role="group"
                aria-labelledby="font-size-label"
              >
                <button
                  type="button"
                  className="ghost"
                  onClick={() => applyQuranSize(quranSize - 0.25)}
                  aria-label="تصغير النص القرآني"
                >
                  ا−
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => applyQuranSize(quranSize + 0.25)}
                  aria-label="تكبير النص القرآني"
                >
                  ا+
                </button>
              </div>
            </div>

            <ol className="ayah-list">
              {success.occurrences.map((occ) => (
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
                  <AyahText
                    text={occ.uthmani_text}
                    wordIndexes={occ.word_indexes}
                  />
                  <p className="ayah-actions">
                    <Link
                      href={`/ayah?s=${occ.surah_number}&a=${occ.ayah_number}`}
                    >
                      التحليل الصرفي كلمةً كلمة ←
                    </Link>
                    {" · "}
                    <Link
                      href={`/mushaf/${occ.surah_number}#a${occ.ayah_number}`}
                    >
                      الآية في سياق سورتها ←
                    </Link>
                  </p>
                </li>
              ))}
            </ol>

            {success.occurrences.length < success.totalAyahs && (
              <button
                type="button"
                className="primary load-more"
                onClick={loadMore}
                disabled={success.loadingMore}
              >
                {success.loadingMore
                  ? "جارٍ التحميل…"
                  : `عرض المزيد (${success.occurrences.length} من ${success.totalAyahs})`}
              </button>
            )}
          </section>
        )}

        <div className="status-box notice">
          <InfoIcon />
          <p>
            النص من مشروع تنزيل (رواية حفص، الرسم العثماني) والجذور من
            المدونة القرآنية بجامعة ليدز — بيانات مستوردة موثقة ببصمات،
            ولم تخضع بعد لمراجعة المنصة المزدوجة.
          </p>
        </div>
      </section>

      <section className="method">
        <div className="container">
          <h2>أربع طبقات لا تختلط</h2>
          <p>
            القيمة الأساسية للمنصة هي الفصل الصريح بين ما هو نص موثق وما هو
            تحليل منقول وما هو قرار بشري وما هو اقتراح آلي.
          </p>
          <ol className="layers">
            <li>
              <strong>النص القرآني الموثق</strong>
              <span>إصدار معروف ببصمة رقمية، لا يعدَّل عبر محرر عادي.</span>
            </li>
            <li>
              <strong>التحليل اللغوي المنقول</strong>
              <span>منسوب لمصادره مع إظهار اختلاف المصادر حقلًا بحقل.</span>
            </li>
            <li>
              <strong>القرار العلمي البشري</strong>
              <span>مراجعة مستقلة معللة، ولا يعتمد باحث عمله بنفسه.</span>
            </li>
            <li>
              <strong>الاقتراح الآلي</strong>
              <span>موسوم دائمًا بحالة «آلي فقط» ولا يُعتمد تلقائيًا.</span>
            </li>
          </ol>
        </div>
      </section>
    </main>
  );
}
