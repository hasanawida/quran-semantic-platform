"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { compareRoots } from "../lib/staticdata";

type RootStats = {
  display_root: string;
  normalized_root: string;
  status: string;
  occurrence_count: number;
  ayah_count: number;
  surah_count: number;
  by_revelation: { meccan: number; medinan: number };
  by_surah: { surah_number: number; surah_name: string; count: number }[];
};

type SharedAyah = {
  surah_number: number;
  surah_name: string;
  ayah_number: number;
  uthmani_text: string;
  word_indexes_by_root: Record<string, number[]>;
};

type Comparison = {
  roots: RootStats[];
  shared: {
    ayah_count: number;
    surah_count: number;
    surahs: { surah_number: number; surah_name: string }[];
    ayahs: SharedAyah[];
    shown: number;
  };
  notice: string;
};

const STATUS_LABELS: Record<string, string> = {
  imported: "مستورد — غير معتمد",
  approved: "معتمد",
  published: "منشور",
  disputed: "مختلف فيه",
};

const ARABIC_LETTER = /[ء-يٱ]/;

/** يعرض نص الآية حرفيًا ويميّز كلمات كل جذر بأسلوب مختلف.
 *
 *  التمييز لا يُنقل باللون وحده: لكل جذر رقم ترتيبي يظهر في العلامة،
 *  فيُقرأ الفرق في الطباعة الأحادية وعند عمى الألوان. */
function SharedAyahText({
  text,
  byRoot,
  order,
}: {
  text: string;
  byRoot: Record<string, number[]>;
  order: string[];
}) {
  const marks = new Map<number, number>();
  order.forEach((root, index) => {
    (byRoot[root] ?? []).forEach((word) => marks.set(word, index + 1));
  });
  const parts = text.split(" ");
  let counter = 0;
  return (
    <p className="quran-text" lang="ar">
      {parts.map((part, index) => {
        const isWord = ARABIC_LETTER.test(part);
        if (isWord) counter += 1;
        const slot = isWord ? marks.get(counter) : undefined;
        return (
          <span key={index}>
            {slot ? (
              <mark className={`mark-root-${slot}`} data-root={slot}>
                {part}
              </mark>
            ) : (
              part
            )}
            {index < parts.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (roots: string) => {
    setBusy(true);
    setError("");
    try {
      const payload = await compareRoots(roots, 30);
      if (!payload) {
        setError("لم يُعثر على أي من هذه الجذور في هذه اللقطة.");
        setData(null);
        return;
      }
      setData(payload);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("roots");
    if (initial) {
      setInput(initial);
      run(initial);
    }
  }, [run]);

  function submit(event: FormEvent) {
    event.preventDefault();
    run(input);
  }

  const order = data?.roots.map((root) => root.display_root) ?? [];

  return (
    <main id="main" className="container">
      <header className="page-head">
        <h1>مقارنة الجذور</h1>
      </header>
      <p className="page-lead">
        قارن توزيع جذرين فأكثر على المصحف، وانظر الآيات التي يجتمعان فيها.
        عرض بيانات لا حكم دلالي: <strong>الاشتراك في الورود لا يعني
        الترادف</strong>.
      </p>

      <form className="search" onSubmit={submit}>
        <label htmlFor="roots">جذور مفصولة بفواصل</label>
        <div className="search-row">
          <input
            id="roots"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="مثال: سأل,طلب,دعو"
          />
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "جارٍ…" : "قارن"}
          </button>
        </div>
        <p className="hint">حتى خمسة جذور. صور الهمزة كلها تصل إلى الجذر نفسه.</p>
      </form>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <section className="section">
            <h2>التوزيع</h2>
            <div className="compare-scroll">
              <table className="segment-table">
                <thead>
                  <tr>
                    <th>الجذر</th>
                    <th>المواضع</th>
                    <th>الآيات</th>
                    <th>السور</th>
                    <th>مكي</th>
                    <th>مدني</th>
                    <th>الحالة</th>
                  </tr>
                </thead>
                <tbody>
                  {data.roots.map((root, index) => (
                    <tr key={root.normalized_root}>
                      <td data-label="الجذر">
                        <span className={`root-slot slot-${index + 1}`}>
                          {index + 1}
                        </span>{" "}
                        <Link
                          href={`/root?r=${encodeURIComponent(root.display_root)}`}
                        >
                          <bdi>{root.display_root}</bdi>
                        </Link>
                      </td>
                      <td data-label="المواضع">{root.occurrence_count}</td>
                      <td data-label="الآيات">{root.ayah_count}</td>
                      <td data-label="السور">{root.surah_count}</td>
                      <td data-label="مكي">{root.by_revelation.meccan}</td>
                      <td data-label="مدني">{root.by_revelation.medinan}</td>
                      <td data-label="الحالة">
                        {STATUS_LABELS[root.status] ?? root.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <h2>
              الآيات المشتركة ({data.shared.ayah_count}) في{" "}
              {data.shared.surah_count} سورة
            </h2>
            {data.shared.ayahs.length === 0 ? (
              <p className="unlinked-note">
                لا توجد آية يجتمع فيها هذه الجذور كلها.
              </p>
            ) : (
              <ol className="ayah-list">
                {data.shared.ayahs.map((item) => (
                  <li
                    key={`${item.surah_number}:${item.ayah_number}`}
                    className="ayah-item"
                  >
                    <p className="ayah-ref">
                      سورة {item.surah_name} — الآية {item.ayah_number}
                      <span className="ayah-ref-num">
                        ({item.surah_number}:{item.ayah_number})
                      </span>
                    </p>
                    <SharedAyahText
                      text={item.uthmani_text}
                      byRoot={item.word_indexes_by_root}
                      order={order}
                    />
                    <p className="ayah-actions">
                      <Link href={`/ayah?s=${item.surah_number}&a=${item.ayah_number}`}>
                        التحليل الصرفي ←
                      </Link>
                      {" · "}
                      <Link
                        href={`/mushaf/${item.surah_number}#a${item.ayah_number}`}
                      >
                        في سياق سورتها ←
                      </Link>
                    </p>
                  </li>
                ))}
              </ol>
            )}
            {data.shared.shown < data.shared.ayah_count && (
              <p className="unlinked-note">
                معروض {data.shared.shown} من {data.shared.ayah_count} آية.
              </p>
            )}
          </section>

          <div className="status-box notice">
            <p>{data.notice}</p>
          </div>
        </>
      )}
    </main>
  );
}
