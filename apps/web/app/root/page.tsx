"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { LexiconSlot } from "../components/LexiconSlot";
import { getMeta, rootOccurrences, type Meta } from "../lib/staticdata";

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

const PAGE_SIZE = 20;

type Payload = NonNullable<Awaited<ReturnType<typeof rootOccurrences>>>;

export default function RootPage() {
  const [root, setRoot] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Payload | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async (query: string, from: number) => {
    setError("");
    try {
      const [payload, info] = await Promise.all([
        rootOccurrences(query, from, PAGE_SIZE),
        getMeta(),
      ]);
      setMeta(info);
      if (!payload) {
        setData(null);
        setError("لم يُعثر على جذر بهذا الإدخال في هذه اللقطة.");
        return;
      }
      setData(payload);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("r") ?? "";
    const from = Math.max(0, Number(params.get("offset") ?? 0) || 0);
    if (!query) {
      setError("لا جذر في العنوان — الصيغة: /root?r=سمو");
      return;
    }
    setRoot(query);
    setOffset(from);
    load(query, from);
  }, [load]);

  function goto(next: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("offset", String(next));
    window.history.pushState(null, "", url);
    setOffset(next);
    load(root, next);
  }

  if (error) {
    return (
      <main id="main" className="container">
        <div className="status-box error" role="alert">
          <p>
            {error} <Link href="/">جرّب البحث</Link>
          </p>
        </div>
      </main>
    );
  }
  if (!data) return <main id="main" className="container" />;

  const { root: info, occurrences, pagination } = data;
  const last = Math.max(0, pagination.total_ayahs - PAGE_SIZE);

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

      {/* المادة المعجمية أَولى بصفحة الجذر منها بصفحة الكلمة —
          فالمعاجم العربية مرتَّبةٌ بالجذر لا باللفظ. */}
      <LexiconSlot roots={[info.display_root]} />

      <ol className="ayah-list">
        {occurrences.map((occ) => (
          <li key={`${occ.surah_number}:${occ.ayah_number}`} className="ayah-item">
            <p className="ayah-ref">
              سورة {occ.surah_name} — الآية {occ.ayah_number}
              <span className="ayah-ref-num">
                ({occ.surah_number}:{occ.ayah_number})
              </span>
            </p>
            <AyahText text={occ.uthmani_text} wordIndexes={occ.word_indexes} />
            <p className="ayah-actions">
              <Link href={`/ayah?s=${occ.surah_number}&a=${occ.ayah_number}`}>
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

      {/* الترقيم كاملًا: 377 جذرًا يتجاوز العشرين وأقصاه 1,879 آية،
          والبتر عند 20 بلا ترقيم كان نقصًا مثبَّتًا. */}
      <nav className="ayah-actions" aria-label="تصفّح المواضع">
        {offset > 0 && (
          <button type="button" className="ghost" onClick={() => goto(Math.max(0, offset - PAGE_SIZE))}>
            → السابقة
          </button>
        )}
        <span>
          {offset + 1}–{offset + occurrences.length} من {pagination.total_ayahs}
        </span>
        {offset + PAGE_SIZE < pagination.total_ayahs && (
          <button type="button" className="ghost" onClick={() => goto(offset + PAGE_SIZE)}>
            التالية ←
          </button>
        )}
        {offset < last && (
          <button type="button" className="ghost" onClick={() => goto(last)}>
            الأخيرة ⇤
          </button>
        )}
      </nav>

      {meta && (
        <div className="status-box notice">
          <p>
            النص من مشروع تنزيل والجذور من المدونة القرآنية بجامعة ليدز —
            بيانات مستوردة موثقة ببصمات، حالتها{" "}
            <strong>{STATUS_LABELS[info.status] ?? info.status}</strong>، ولم
            تخضع بعد لمراجعة المنصة المزدوجة. لقطة ثابتة بتاريخ{" "}
            {meta.snapshot_at}. <Link href="/provenance">بيان الأصول الكامل</Link>
          </p>
        </div>
      )}
    </main>
  );
}
