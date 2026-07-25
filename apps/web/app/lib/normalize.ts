/** تطبيع **للبحث فقط** — لا يُطبَّق على نص مصحف أبدًا.
 *
 *  الشحنة `data/v1/normspec.json` مولَّدة آليًا من ثوابت
 *  `apps/api/app/utils/arabic.py` في وقت البناء. هذا الملف مفسّرها:
 *  لا يحمل معرفةً بالعربية، ولا قاعدة همزةٍ ولا ألفٍ مكتوبةً هنا.
 *
 *  **عقد ملزم من ثلاثة تنفيذات** — بايثون (`arabic.py`) وSQL
 *  (`QuranService._skeleton_expr`) وهذا المفسّر. يحرسه
 *  `apps/api/tests/test_browser_normalizer_matches_python.py`:
 *  26,913 حالة، وأي اختلاف يُحمِّر البناء. وبدونه يعيد البحث صفرًا
 *  صامتًا بلا رسالة خطأ — وهو ما بُني له الحارس.
 */

export type NormSpec = {
  drop: number[];
  combiningHamza: number[];
  combiningHamzaTo: string;
  combiningHamzaRootTo: string;
  wawDaggerAlef: [string, string, string];
  searchMap: Record<string, string>;
  taMarbutaToHa: Record<string, string>;
  skeletonDrop: string[];
  minSkeleton: number;
  definiteArticle: string;
  rootHamzaMap: Record<string, string>;
  rootLetterMap: Record<string, string>;
  rootKeep: [number, number];
  wordLetter: [number, number][];
};

export class Normalizer {
  private drop: Set<string>;
  private hamza: Set<string>;

  constructor(private spec: NormSpec) {
    const chars = (points: number[]) =>
      new Set(points.map((point) => String.fromCodePoint(point)));
    this.drop = chars(spec.drop);
    this.hamza = chars(spec.combiningHamza);
  }

  private replaceAll(value: string, from: string, to: string) {
    return value.split(from).join(to);
  }

  /** نظير `normalize_arabic_search` — للبحث فقط. */
  search(value: string): string {
    let staged = value.normalize("NFC");

    let out = "";
    for (const char of staged) {
      out += this.hamza.has(char) ? this.spec.combiningHamzaTo : char;
    }

    // واو + ألف خنجرية غير متبوعة بألف صريحة
    const [pattern, notAfter, into] = this.spec.wawDaggerAlef;
    staged = "";
    for (let i = 0; i < out.length; i += 1) {
      if (out.startsWith(pattern, i) && out[i + pattern.length] !== notAfter) {
        staged += into;
        i += pattern.length - 1;
      } else {
        staged += out[i];
      }
    }

    out = "";
    for (const char of staged) {
      if (!this.drop.has(char)) out += this.spec.searchMap[char] ?? char;
    }
    return out.replace(/\s+/gu, " ").trim();
  }

  /** نظير `normalize_search_skeleton` — طبقة المطابقة التقريبية. */
  skeleton(value: string): string {
    let out = this.search(value);
    for (const [from, to] of Object.entries(this.spec.taMarbutaToHa)) {
      out = this.replaceAll(out, from, to);
    }
    for (const char of this.spec.skeletonDrop) {
      out = this.replaceAll(out, char, "");
    }
    return out;
  }

  /** نظير `normalize_surah_name` — يُطبَّق على **الطلب** وحده؛ مفاتيح
   *  الأسماء المخزَّنة محسوبة في بايثون ومشحونة في `surahs.json`. */
  surahName(value: string): string {
    let out = this.search(value);
    for (const [from, to] of Object.entries(this.spec.taMarbutaToHa)) {
      out = this.replaceAll(out, from, to);
    }
    const article = this.spec.definiteArticle;
    const next = out[article.length];
    return out.startsWith(article) && next !== undefined && /\S/u.test(next)
      ? out.slice(article.length)
      : out;
  }

  /** نظير `normalize_root_input` — مفتاح الجذر القانوني. */
  rootInput(value: string): string {
    let staged = "";
    for (const char of value.normalize("NFC")) {
      staged += this.hamza.has(char) ? this.spec.combiningHamzaRootTo : char;
    }
    let out = "";
    for (const char of staged) if (!this.drop.has(char)) out += char;
    staged = "";
    for (const char of out) {
      staged +=
        this.spec.rootHamzaMap[char] ?? this.spec.rootLetterMap[char] ?? char;
    }
    const [low, high] = this.spec.rootKeep;
    out = "";
    for (const char of staged) {
      const point = char.codePointAt(0) as number;
      if (point >= low && point <= high) out += char;
    }
    return out;
  }

  private isWordLetter(char: string): boolean {
    const point = char.codePointAt(0) as number;
    return this.spec.wordLetter.some(([a, b]) => point >= a && point <= b);
  }

  /** نظير `tokenize_ayah` — **يعيد مواضع فقط، ولا يمسّ النص**.
   *
   *  الكلمة ما حمل حرفًا عربيًا؛ علامات الوقف ورموز نهاية الآية لا تأخذ
   *  رقمًا. المواضع فهارس محارف في نص الآية كما هو، فيبقى التمييز
   *  مرتبطًا بالنص الموثق لا بنسخة معالجة منه. */
  tokenize(text: string): { word_number: number; char_start: number; char_end: number }[] {
    const tokens: { word_number: number; char_start: number; char_end: number }[] = [];
    let position = 0;
    for (const part of text.split(" ")) {
      const start = position;
      position += part.length + 1;
      if ([...part].some((char) => this.isWordLetter(char))) {
        tokens.push({
          word_number: tokens.length + 1,
          char_start: start,
          char_end: start + part.length,
        });
      }
    }
    return tokens;
  }
}
