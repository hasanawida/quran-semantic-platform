"use client";

/** قراءة البيانات الثابتة المنشورة — بديل مباشر لنداءات الخدمة.
 *
 *  **الخطوط الحمراء:**
 *  1. نص الآية يُقرأ من `data/v1/text/s{n}.json` كما وُلِّد عن الحزمة
 *     الموثقة، ويُمرَّر إلى العرض سلسلةً واحدة. لا يُبنى من كلماته هنا
 *     ولا في أي مكان آخر.
 *  2. التطبيع للبحث لا للعرض: `norm.json` مفاتيحُ محسوبة في بايثون،
 *     و`Normalizer` يُطبَّق على **الطلب** وحده.
 *  3. كل مخرَج يحمل مصدره: `version()` و`snapshot()` يُرفقان بكل استجابة
 *     كما يفعل `QuranService._version_block` اليوم.
 */

import { Normalizer, type NormSpec } from "./normalize";

const BASE = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1`;

const cache = new Map<string, Promise<unknown>>();

/** يجلب ملفًا مرةً واحدة — و**يرمي** عند الفشل بدل أن يعيد null صامتًا. */
function loadJson<T>(path: string): Promise<T> {
  let pending = cache.get(path) as Promise<T> | undefined;
  if (!pending) {
    pending = fetch(`${BASE}/${path}`).then((response) => {
      if (!response.ok) {
        throw new Error(`تعذّر تحميل بيانات المنصة (${path}).`);
      }
      return response.json() as Promise<T>;
    });
    cache.set(path, pending as Promise<unknown>);
  }
  return pending;
}

// ---- الأنواع (مطابقة لأشكال الخدمة) ---------------------------------------
export type Surah = {
  number: number;
  arabic_name: string;
  revelation_type: string;
  ayah_count: number;
};
export type Meta = {
  data_release: string;
  review_status: string;
  counts: Record<string, number>;
  snapshot_at: string;
  warning: string;
};
export type Version = {
  version_code: string;
  riwayah: string;
  script_type: string;
  counting_system: string;
  review_status: string;
};
type SurahRow = {
  n: number;
  name: string;
  rev: string;
  count: number;
  basmala: string | null;
  key: string;
};
type SurahFile = { offsets: number[]; surahs: SurahRow[] };
type RootEntry = { d: string; o: [number, number[]][] };
type Manifest = {
  built_at: string;
  data_release: string;
  review_status: string;
  sources: Record<string, unknown>;
  files: Record<string, string>;
};

// ---- أساسيات ---------------------------------------------------------------
export const getManifest = () => loadJson<Manifest>("manifest.json");
export const getMeta = () => loadJson<Meta>("meta.json");
export const getProvenance = () => loadJson<Record<string, unknown>>("provenance.json");
export const getMethodology = () => loadJson<Record<string, unknown>>("methodology.json");
export const getLabels = () =>
  loadJson<{
    posLabels: Record<string, string>;
    featureLabels: Record<string, Record<string, string>>;
    featureTitles: Record<string, string>;
    dimensions: { key: string; title: string; values: { value: string; label: string }[] }[];
  }>("morph/labels.json");

let normalizer: Promise<Normalizer> | null = null;
export function getNormalizer(): Promise<Normalizer> {
  if (!normalizer) {
    normalizer = loadJson<NormSpec>("normspec.json").then((s) => new Normalizer(s));
  }
  return normalizer;
}

const getSurahFile = () => loadJson<SurahFile>("surahs.json");

export async function listSurahs(query?: string): Promise<Surah[]> {
  const file = await getSurahFile();
  const all: Surah[] = file.surahs.map((s) => ({
    number: s.n,
    arabic_name: s.name,
    revelation_type: s.rev,
    ayah_count: s.count,
  }));
  const raw = (query ?? "").trim();
  if (!raw) return all;

  // الأرقام العربية-الهندية: تحويل أرقام لا تطبيع نص عربي
  const latin = raw.replace(/[٠-٩]/g, (d) =>
    String(d.charCodeAt(0) - 0x0660)
  );
  if (/^\d+$/.test(latin)) {
    const number = Number(latin);
    return all.filter((s) => s.number === number);
  }

  // ترتيب `_filter_surahs` نفسه: تامة ثم بادئة ثم تضمين (من 3 أحرف).
  // الاتجاه مقصود: **الطلب** جزء من الاسم لا العكس، وإلا طابقت «ص» و«ق»
  // كل طلب. والمفاتيح المخزَّنة محسوبة في بايثون — تنفيذ واحد لها.
  const spec = await getNormalizer();
  const key = spec.surahName(raw);
  if (!key) return [];
  const exact: Surah[] = [];
  const prefix: Surah[] = [];
  const contains: Surah[] = [];
  file.surahs.forEach((row, i) => {
    if (row.key === key) exact.push(all[i]);
    else if (row.key.startsWith(key)) prefix.push(all[i]);
    else if (key.length >= 3 && row.key.includes(key)) contains.push(all[i]);
  });
  return [...exact, ...prefix, ...contains];
}

export async function ayahIndex(surah: number, ayah: number): Promise<number> {
  const file = await getSurahFile();
  return file.offsets[surah - 1] + (ayah - 1);
}
export async function fromIndex(position: number) {
  const file = await getSurahFile();
  let low = 0;
  let high = file.offsets.length - 1;
  while (low < high) {
    const mid = (low + high + 1) >> 1;
    if (file.offsets[mid] <= position) low = mid;
    else high = mid - 1;
  }
  const row = file.surahs[low];
  return {
    surah_number: row.n,
    surah_name: row.name,
    ayah_number: position - file.offsets[low] + 1,
  };
}

/** نص سورة كاملًا — كما وُلِّد عن الحزمة، بلا معالجة. */
export const surahText = (surah: number) =>
  loadJson<string[]>(`text/s${surah}.json`);

export async function ayahText(position: number): Promise<string> {
  const at = await fromIndex(position);
  const texts = await surahText(at.surah_number);
  return texts[at.ayah_number - 1];
}

export async function version(): Promise<Version> {
  const meta = await getMeta();
  const prov = (await getProvenance()) as {
    text_version: Record<string, string>;
  };
  return {
    version_code: prov.text_version.version_code,
    riwayah: prov.text_version.riwayah,
    script_type: prov.text_version.script_type,
    counting_system: prov.text_version.counting_system,
    review_status: meta.review_status,
  };
}

// ---- صفحة السورة -----------------------------------------------------------
export async function surahPage(surah: number) {
  const [file, texts, ver] = await Promise.all([
    getSurahFile(),
    surahText(surah),
    version(),
  ]);
  const row = file.surahs[surah - 1];
  if (!row) throw new Error("لا سورة بهذا الرقم — أرقام السور من 1 إلى 114.");
  const spec = await getNormalizer();
  return {
    surah: {
      number: row.n,
      arabic_name: row.name,
      revelation_type: row.rev,
      basmala_text: row.basmala,
      ayah_count: row.count,
    },
    version: ver,
    ayahs: texts.map((text, i) => ({
      ayah_number: i + 1,
      uthmani_text: text,
      // مواضع الحروف مشتقّة من النص المشحون نفسه — فلا مصدر ثانٍ لها
      // يمكن أن يفترق عنه، والتمييز مستحيل أن يقع خارج نص الآية.
      words: spec.tokenize(text),
    })),
  };
}

// ---- البحث النصي -----------------------------------------------------------
const getNorm = () => loadJson<string[]>("norm.json");

function windowHits(values: string[], target: string[]): Set<number> {
  const hits = new Set<number>();
  if (!target.length || target.length > values.length) return hits;
  for (let start = 0; start + target.length <= values.length; start += 1) {
    let ok = true;
    for (let k = 0; k < target.length; k += 1) {
      if (values[start + k] !== target[k]) {
        ok = false;
        break;
      }
    }
    if (ok) for (let k = 0; k < target.length; k += 1) hits.add(start + k);
  }
  return hits;
}

export async function searchAyahs(query: string, offset = 0, limit = 20) {
  const [spec, norms, ver, meta] = await Promise.all([
    getNormalizer(),
    getNorm(),
    version(),
    getMeta(),
  ]);
  const exactKey = spec.search(query);
  const skeletonKey = spec.skeleton(query);
  const useSkeleton = skeletonKey.length >= 3;

  // الطبقتان بترتيب `QuranService.search_ayahs`: الصارمة أولًا ثم
  // التقريبية، وداخل كل طبقة ترتيب المصحف. والدلالة تضمين داخل الكلمة
  // (LIKE %مفتاح%) كما هي في الخدمة — لا فهرس كلمي يغيّرها صامتًا.
  const exact: number[] = [];
  const approximate: number[] = [];
  for (let i = 0; i < norms.length; i += 1) {
    if (exactKey && norms[i].includes(exactKey)) exact.push(i);
    else if (useSkeleton) {
      let skel = norms[i];
      for (const [from, to] of Object.entries(spec["spec" as never] ?? {})) void [from, to];
      skel = spec.skeleton("") === "" ? skeletonOf(norms[i], spec) : skel;
      if (skel.includes(skeletonKey)) approximate.push(i);
    }
  }
  const ordered = [...exact, ...approximate];
  const page = ordered.slice(offset, offset + limit);

  const exactWords = exactKey.split(" ").filter(Boolean);
  const skeletonWords = useSkeleton ? skeletonKey.split(" ").filter(Boolean) : [];

  const results = await Promise.all(
    page.map(async (position) => {
      const at = await fromIndex(position);
      const text = await ayahText(position);
      const tokens = spec.tokenize(text);
      const plain = norms[position].split(" ").filter(Boolean);
      const skel = plain.map((w) => skeletonOf(w, spec));

      let hits = windowHits(plain, exactWords);
      if (!hits.size && skeletonWords.length) hits = windowHits(skel, skeletonWords);
      if (!hits.size) {
        const parts = exactWords.filter((w) => w.length >= 2);
        plain.forEach((w, i) => {
          if (parts.some((p) => w.includes(p))) hits.add(i);
        });
      }
      if (!hits.size && skeletonWords.length) {
        const parts = skeletonWords.filter((w) => w.length >= 3);
        skel.forEach((w, i) => {
          if (parts.some((p) => w.includes(p))) hits.add(i);
        });
      }
      return {
        ...at,
        // نص السجل كما وُلِّد — لا يُقطَّع ولا يُبرَز هنا
        uthmani_text: text,
        match_kind: exact.includes(position) ? ("exact" as const) : ("approximate" as const),
        match_words: [...hits].sort((a, b) => a - b).map((i) => tokens[i]).filter(Boolean),
      };
    })
  );

  return {
    query,
    normalized_query: exactKey,
    skeleton_query: useSkeleton ? skeletonKey : null,
    version: ver,
    results,
    pagination: { total: ordered.length, offset, limit },
    scope_note:
      `المطابقة على صورة مطبَّعة للبحث، والعرض من نص إصدار ` +
      `${ver.version_code} حرفيًا. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}

/** طبقة الهيكل مشتقّة من المفتاح المطبَّع المشحون — بصفر بايت إضافية. */
function skeletonOf(normalized: string, spec: Normalizer): string {
  return spec.skeleton(normalized);
}

// ---- الجذور ----------------------------------------------------------------
const getRoots = () =>
  loadJson<{ roots: Record<string, RootEntry> }>("roots.json");

async function resolveRoot(query: string) {
  const [spec, file] = await Promise.all([getNormalizer(), getRoots()]);
  const key = spec.rootInput(query);
  const entry = file.roots[key];
  return entry ? { key, entry } : null;
}

/** مواضع الجذر — القائمة **كاملة** تُحمَّل والترقيم يقع في المتصفح.
 *
 *  صفحة الجذر كانت تعرض 20 موضعًا بلا ترقيم و377 جذرًا يتجاوز هذا الحد
 *  (أقصاه 1,879 آية). الترقيم بمسارات إضافية كان سيضاعف عدد الصفحات؛
 *  وهذا يرقّم على قائمة محمَّلة بلا مسار واحد جديد. */
export async function rootOccurrences(query: string, offset = 0, limit = 20) {
  const found = await resolveRoot(query);
  if (!found) return null;
  const meta = await getMeta();
  const page = found.entry.o.slice(offset, offset + limit);
  const occurrences = await Promise.all(
    page.map(async ([position, words]) => {
      const at = await fromIndex(position);
      return { ...at, uthmani_text: await ayahText(position), word_indexes: words };
    })
  );
  return {
    root: {
      display_root: found.entry.d,
      normalized_root: found.key,
      status: meta.review_status,
      confidence: "machine_only",
      occurrence_count: found.entry.o.reduce((n, [, w]) => n + w.length, 0),
      ayah_count: found.entry.o.length,
    },
    occurrences,
    pagination: { total_ayahs: found.entry.o.length, offset, limit },
  };
}

export async function compareRoots(input: string, limit = 30) {
  const names = input
    .split(/[,،]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 5);
  const [file, meta] = await Promise.all([getSurahFile(), getMeta()]);
  const entries: { display: string; key: string; entry: RootEntry }[] = [];
  for (const name of names) {
    const found = await resolveRoot(name);
    if (found) entries.push({ display: found.entry.d, ...found });
  }
  if (!entries.length) return null;

  const stats = entries.map(({ entry, key }) => {
    const surahs = new Map<number, number>();
    let meccan = 0;
    let medinan = 0;
    entry.o.forEach(([position]) => {
      let low = 0;
      let high = file.offsets.length - 1;
      while (low < high) {
        const mid = (low + high + 1) >> 1;
        if (file.offsets[mid] <= position) low = mid;
        else high = mid - 1;
      }
      const row = file.surahs[low];
      surahs.set(row.n, (surahs.get(row.n) ?? 0) + 1);
      if (row.rev === "Meccan") meccan += 1;
      else medinan += 1;
    });
    return {
      display_root: entry.d,
      normalized_root: key,
      status: meta.review_status,
      occurrence_count: entry.o.reduce((n, [, w]) => n + w.length, 0),
      ayah_count: entry.o.length,
      surah_count: surahs.size,
      by_revelation: { meccan, medinan },
      by_surah: [...surahs].map(([n, count]) => ({
        surah_number: n,
        surah_name: file.surahs[n - 1].name,
        count,
      })),
    };
  });

  let shared = new Set(entries[0].entry.o.map(([p]) => p));
  entries.slice(1).forEach(({ entry }) => {
    const next = new Set(entry.o.map(([p]) => p));
    shared = new Set([...shared].filter((p) => next.has(p)));
  });
  const positions = [...shared].sort((a, b) => a - b);
  const ayahs = await Promise.all(
    positions.slice(0, limit).map(async (position) => {
      const at = await fromIndex(position);
      const byRoot: Record<string, number[]> = {};
      entries.forEach(({ entry }) => {
        const hit = entry.o.find(([p]) => p === position);
        if (hit) byRoot[entry.d] = hit[1];
      });
      return {
        ...at,
        uthmani_text: await ayahText(position),
        word_indexes_by_root: byRoot,
      };
    })
  );
  const surahSet = new Set(ayahs.map((a) => a.surah_number));
  return {
    roots: stats,
    shared: {
      ayah_count: positions.length,
      surah_count: surahSet.size,
      surahs: [...surahSet].map((n) => ({
        surah_number: n,
        surah_name: file.surahs[n - 1].name,
      })),
      ayahs,
      shown: ayahs.length,
    },
    notice:
      "عرض بيانات لا حكم دلالي: الاشتراك في الورود لا يعني الترادف. " +
      `لقطة ثابتة بتاريخ ${meta.snapshot_at}، حالتها ${meta.review_status}.`,
  };
}

// ---- الصرف -----------------------------------------------------------------
type MorphRow = [number, number, string, string | null, string, string | null, number | null, string | null];

export async function ayahAnalysis(surah: number, ayah: number) {
  const [file, texts, rows, aligned, labels, spec, meta] = await Promise.all([
    getSurahFile(),
    surahText(surah),
    loadJson<MorphRow[][]>(`morph/s${surah}.json`),
    loadJson<number[]>("aligned.json"),
    getLabels(),
    getNormalizer(),
    getMeta(),
  ]);
  const row = file.surahs[surah - 1];
  const text = texts?.[ayah - 1];
  if (!row || text === undefined) {
    throw new Error("الآية غير موجودة في الإصدار المفعَّل.");
  }
  const isLinked = aligned[file.offsets[surah - 1] + (ayah - 1)] === 1;
  const tokens = spec.tokenize(text);
  const source = "qac-0.4";

  const byWord = new Map<number, MorphRow[]>();
  (rows[ayah - 1] ?? []).forEach((segment) => {
    const list = byWord.get(segment[0]) ?? [];
    list.push(segment);
    byWord.set(segment[0], list);
  });

  const words = tokens.map((token) => {
    const segments = (byWord.get(token.word_number) ?? []).map((s) => ({
      segment_number: s[1],
      form_source: "",
      tag: s[2],
      pos: s[3],
      // السوابق واللواحق بلا POS صريح؛ وسمها هو قسمها
      pos_label: labels.posLabels[s[3] ?? s[2]] ?? (s[3] ?? s[2]),
      features: s[4], // حرفيًا كما وردت في المصدر — شرط الرخصة
      lemma: s[5],
      lemma_index: s[6],
      root: s[7],
      source_root_text: s[7],
      is_linked_to_token: isLinked,
    }));
    const roots = new Set(segments.map((s) => s.root).filter(Boolean));
    return {
      word_number: token.word_number,
      surface_text: text.slice(token.char_start, token.char_end),
      char_start: token.char_start,
      char_end: token.char_end,
      // التوسيع مقصود: `{ [source]: segments }` يُستنتج نوعًا ضيّقًا
      // بمفتاح واحد حرفي، فلا يقبله المستهلك الذي يتوقّع خريطة مصادر.
      // والمنصة مبنيّة على تعدّد المصادر ولو كان المعتمد اليوم واحدًا.
      analyses_by_source: (segments.length
        ? { [source]: segments }
        : {}) as Record<string, typeof segments>,
      root_agreement: !segments.length
        ? ("no_analysis" as const)
        : !roots.size
          ? ("no_root" as const)
          : ("single_source" as const),
      // اللقطة الثابتة لا تحمل قرارات المنصة: تُتَّخذ في النسخة المحلية
      // ولا تُنشر. عرض «لا قرار» أصدق من عرض قرار لا وجود له.
      decision: null,
    };
  });

  return {
    surah_number: surah,
    surah_name: row.name,
    ayah_number: ayah,
    uthmani_text: text,
    word_count: tokens.length,
    words,
    notice:
      "التحليل الصرفي منقول عن مصادره ومنسوب إليها، وحالته «مستورد — غير " +
      `معتمد». نص الآية وحده هو المرجع. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}

type DimRow = [
  string, string, string | null, string | null, number | null, string | null,
  string | null, ...(string | null)[],
];
const DIM_KEYS = [
  "aspect", "verb_form", "voice", "mood", "person", "gender",
  "grammatical_number", "case_marking", "definiteness", "nominal_form",
] as const;

export async function searchMorphology(
  filters: Record<string, string>,
  rootQuery: string,
  offset = 0,
  limit = 20
) {
  const [dims, stream, spec, labels, meta] = await Promise.all([
    loadJson<DimRow[]>("morph/dims.json"),
    loadJson<string[]>("morph/all.json"),
    getNormalizer(),
    getLabels(),
    getMeta(),
  ]);
  const rootKey = rootQuery.trim() ? spec.rootInput(rootQuery) : "";

  // ترشيح 12,405 سلسلة سمات أولًا (مقيس: أقل من مللي ثانية)، ثم مسح
  // 128,219 مقطعًا — بلا فهرس مقلوب لأن لا مشكلة يحلّها.
  const allowed = new Set<number>();
  dims.forEach((row, i) => {
    if (filters.pos && row[1] !== filters.pos) return;
    if (rootKey && row[6] !== rootKey) return;
    for (let k = 0; k < DIM_KEYS.length; k += 1) {
      const want = filters[DIM_KEYS[k]];
      if (!want) continue;
      const got = row[7 + k] ?? (DIM_KEYS[k] === "verb_form" ? "I" : null);
      if (got !== want) return;
    }
    allowed.add(i);
  });

  const hits: [number, number, number, number][] = [];
  for (let position = 0; position < stream.length; position += 1) {
    const line = stream[position];
    if (!line) continue;
    const words = line.split("|");
    for (let w = 0; w < words.length; w += 1) {
      if (!words[w]) continue;
      const segs = words[w].split(",");
      for (let s = 0; s < segs.length; s += 1) {
        const feature = Number(segs[s]);
        if (allowed.has(feature)) hits.push([position, w + 1, s + 1, feature]);
      }
    }
  }

  const items = await Promise.all(
    hits.slice(offset, offset + limit).map(async ([position, word, segment, feature]) => {
      const at = await fromIndex(position);
      const text = await ayahText(position);
      const token = spec.tokenize(text)[word - 1];
      const row = dims[feature];
      return {
        ...at,
        word_number: word,
        segment_number: segment,
        surface_text: token ? text.slice(token.char_start, token.char_end) : null,
        pos: row[2],
        pos_label: labels.posLabels[(row[2] ?? row[1]) as string] ?? row[1],
        lemma: row[3],
        root: row[6],
        source: "qac-0.4",
        features: row[0],
        is_linked_to_token: token !== undefined,
      };
    })
  );

  return {
    total: hits.length,
    offset,
    limit,
    items,
    notice:
      "التحليل منقول عن المدونة القرآنية (جامعة ليدز)، وسماته معروضة " +
      `حرفيًا كما وردت. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}
