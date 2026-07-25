import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import SurahView from "./SurahView";

type SurahRow = { n: number; name: string; rev: string; count: number };

/** يُقرأ من الملف المولَّد بـfs لا بـfetch: البناء لا يعتمد على خدمة
 *  حيّة، ونقص الملف يُسقط البناء بصوت بدل أن يُخرج صفحات فارغة. */
function rows(): SurahRow[] {
  const file = path.join(
    process.cwd(),
    "public",
    "data",
    "v1",
    "surahs.json"
  );
  const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as {
    surahs: SurahRow[];
  };
  if (parsed.surahs.length !== 114) {
    throw new Error(`فهرس السور ناقص: ${parsed.surahs.length} من 114`);
  }
  return parsed.surahs;
}

export function generateStaticParams() {
  return rows().map((row) => ({ surah: String(row.n) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ surah: string }>;
}): Promise<Metadata> {
  const { surah } = await params;
  const row = rows().find((r) => r.n === Number(surah));
  if (!row) return { title: "سورة غير موجودة", robots: { index: false } };
  const kind = row.rev === "Meccan" ? "مكية" : "مدنية";
  const description =
    `سورة ${row.name} (${kind}) — ${row.count} آية، نصًّا موثقًا من إصدار ` +
    `مستورد ببصمته، مع تحليل صرفي منسوب لمصدره لكل كلمة.`;
  return {
    title: `سورة ${row.name}`,
    description,
    openGraph: { title: `سورة ${row.name}`, description },
    alternates: { canonical: `/mushaf/${row.n}` },
  };
}

export default async function Page({
  params,
}: {
  params: Promise<{ surah: string }>;
}) {
  const { surah } = await params;
  return <SurahView surah={Number(surah)} />;
}
