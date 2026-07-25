"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getLabels, searchMorphology } from "../lib/staticdata";

type DimensionValue = { value: string; label: string };
type Dimension = { key: string; title: string; values: DimensionValue[] };

type Hit = {
  surah_number: number;
  surah_name: string;
  ayah_number: number;
  word_number: number;
  segment_number: number;
  surface_text: string | null;
  pos: string | null;
  pos_label: string | null;
  lemma: string | null;
  root: string | null;
  source: string;
  features: string;
  is_linked_to_token: boolean;
};

type Results = {
  total: number;
  offset: number;
  limit: number;
  items: Hit[];
  notice: string;
};

const PAGE_SIZE = 20;

// الوزن المجرد لا يوسمه المصدر: غيابه علامته، ويُترجم في الاستعلام
const EXTRA_VERB_FORM: DimensionValue = { value: "I", label: "مجرد (غير موسوم)" };

export default function MorphologySearchPage() {
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [root, setRoot] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getLabels()
      .then((labels) => setDimensions(labels.dimensions))
      .catch(() => setError("تعذّر جلب أبعاد البحث."));
  }, []);

  const search = useCallback(
    async (offset = 0) => {
      const active = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value)
      ) as Record<string, string>;
      if (!Object.keys(active).length && !root.trim()) {
        setError("حدّد بُعدًا واحدًا على الأقل أو اكتب جذرًا.");
        setResults(null);
        return;
      }

      setBusy(true);
      setError("");
      try {
        setResults(await searchMorphology(active, root, offset, PAGE_SIZE));
      } catch (err) {
        setError((err as Error).message);
        setResults(null);
      } finally {
        setBusy(false);
      }
    },
    [filters, root]
  );

  const setFilter = (key: string, value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));

  return (
    <main id="main" className="container">
      <header className="page-head">
        <h1>البحث بالصيغة الصرفية</h1>
      </header>
      <p className="page-lead">
        ابحث بأبعاد الصرف لا بالجذر وحده: الزمن والوزن والبناء والإعراب.
        النتيجة تحليل منقول عن مصادره، وسماته معروضة حرفيًا كما وردت.
      </p>

      <form
        className="feature-form"
        onSubmit={(event) => {
          event.preventDefault();
          search(0);
        }}
      >
        <div className="feature-grid">
          <div>
            <label htmlFor="root">الجذر (اختياري)</label>
            <input
              id="root"
              type="text"
              value={root}
              onChange={(event) => setRoot(event.target.value)}
              placeholder="مثال: سأل"
            />
          </div>

          {dimensions.map((dimension) => {
            const values =
              dimension.key === "verb_form"
                ? [EXTRA_VERB_FORM, ...dimension.values]
                : dimension.values;
            return (
              <div key={dimension.key}>
                <label htmlFor={dimension.key}>{dimension.title}</label>
                <select
                  id={dimension.key}
                  value={filters[dimension.key] ?? ""}
                  onChange={(event) =>
                    setFilter(dimension.key, event.target.value)
                  }
                >
                  <option value="">— أي —</option>
                  {values.map((value) => (
                    <option key={value.value} value={value.value}>
                      {value.label}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>

        <div className="row-actions">
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "جارٍ البحث…" : "بحث"}
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setFilters({});
              setRoot("");
              setResults(null);
              setError("");
            }}
          >
            تفريغ
          </button>
        </div>
      </form>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <section className="section" aria-live="polite">
          <h2>{results.total.toLocaleString("ar")} نتيجة</h2>

          {results.items.length === 0 ? (
            <p className="unlinked-note">
              لا توجد مقاطع مطابقة لهذه الأبعاد مجتمعةً.
            </p>
          ) : (
            <ul className="word-list">
              {results.items.map((hit) => (
                <li
                  key={`${hit.surah_number}:${hit.ayah_number}:${hit.word_number}:${hit.segment_number}`}
                  className="word-card"
                >
                  <div className="word-card-head">
                    <span className="word-index">{hit.word_number}</span>
                    {hit.surface_text && (
                      <bdi className="word-surface" lang="ar">
                        {hit.surface_text}
                      </bdi>
                    )}
                    <span className="chip">{hit.pos_label ?? hit.pos}</span>
                  </div>
                  <p className="claim-meta">
                    سورة {hit.surah_name} — الآية {hit.ayah_number} (
                    {hit.surah_number}:{hit.ayah_number}) · المصدر:{" "}
                    {hit.source}
                    {hit.lemma && (
                      <>
                        {" "}
                        · الأصل <bdi lang="ar">{hit.lemma}</bdi>
                      </>
                    )}
                    {hit.root && (
                      <>
                        {" "}
                        · الجذر{" "}
                        <Link href={`/root?r=${encodeURIComponent(hit.root)}`}>
                          <bdi lang="ar">{hit.root}</bdi>
                        </Link>
                      </>
                    )}
                  </p>
                  <p className="features-cell">
                    <code dir="ltr">{hit.features}</code>
                  </p>
                  <p className="ayah-actions">
                    <Link href={`/ayah?s=${hit.surah_number}&a=${hit.ayah_number}`}>
                      التحليل الكامل للآية ←
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
            </ul>
          )}

          {results.total > results.offset + results.items.length && (
            <button
              type="button"
              className="primary load-more"
              disabled={busy}
              onClick={() => search(results.offset + PAGE_SIZE)}
            >
              الصفحة التالية ({results.offset + results.items.length} من{" "}
              {results.total})
            </button>
          )}

          <div className="status-box notice">
            <p>{results.notice}</p>
          </div>
        </section>
      )}
    </main>
  );
}
