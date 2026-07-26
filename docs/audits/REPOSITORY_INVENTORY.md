# جرد المستودع — المرحلة صفر

> مقيسٌ لا مقدَّر. كل رقم هنا مأخوذ بأمر يُعاد تشغيله، والأمر مذكور معه.
>
> الوسم المرجعي: `baseline-pre-knowledge-platform` · الالتزام: `3327482`
> · الفرع: `feat/knowledge-platform-10-of-10` · التاريخ: 2026-07-27

## ١) الأرقام

| المقيس | العدد | الأمر |
|---|---|---|
| ملفات متعقَّبة | 193 | `git ls-files \| wc -l` |
| جداول (ORM) | 30 | `grep -rh __tablename__ apps/api/app/models/*.py \| wc -l` |
| هجرات Alembic | 8 | `ls apps/api/alembic/versions/*.py \| wc -l` |
| مسارات API | 79 | `grep -rhoE '@router\.(get\|post\|patch\|put\|delete)\("[^"]*"' apps/api/app/api/v1/*.py \| wc -l` |
| صفحات الواجهة | 18 | `find apps/web/app -name "page*.tsx" \| wc -l` |
| منها **معدومة في الموقع المنشور** | 6 | `find apps/web/app -name "page.node.tsx" \| wc -l` |
| ملفات اختبار | 22 | `ls apps/api/tests/test_*.py \| wc -l` |
| نشرات CI | 3 | `ls .github/workflows/` |

## ٢) الجداول الموجودة

```text
audit_logs · ayahs · citations · claim_citations · claims
conflict_of_interest_declarations · corrections · disputes
golden_root_cases · morphological_analyses · morphology_sources
project_claims · project_members · projects · quran_text_versions
refresh_sessions · report_versions · reports · review_assignments
review_comments · reviewer_qualifications · root_occurrences · roots
source_works · surahs · token_root_decision_roots · token_root_decisions
tokens · user_roles · users
```

## ٣) الفجوة مقابل §22 من الوثيقة

الوثيقة تعدّ **٥٣ كيانًا** مطلوبًا. الموجود منها أو ما يكافئه: **١٥**.
**الناقص: ٣٨.**

| العائلة | الناقص |
|---|---|
| **المصادر** (٨) | `source_authors` `source_editions` `source_files` `source_licenses` `source_approvals` `source_reviews` `source_hashes` `source_restrictions` |
| **الكتب والمقاطع** (٧) | `authors` `scholars` `books` `editions` `documents` `pages` `passages` |
| **الاقتباس والقول** (٣) | `quotations` `scholarly_statements` `linguistic_meanings` |
| **الحديث** (٣) | `narrations` `hadith_sources` `hadith_gradings` |
| **القراءات والرسم** (٧) | `readings` `reciters` `narrators` `reading_paths` `orthography_features` `stop_positions` `verse_count_schools` |
| **الذكاء الاصطناعي** (٤) | `ai_runs` `ai_inputs` `ai_outputs` `ai_evidence` |
| **متفرقات** (٦) | `basmalas` `lemmas` `morphology_disagreements` `grammatical_analyses` `review_rounds` `quarantine_content` |

**المكافئات المقبولة** (اسم مختلف، دور واحد): `sources`←`source_works` ·
`releases`/`quran_releases`←`quran_text_versions` · `audit_events`←`audit_logs` ·
`reviews`←`review_assignments` · `evidence`←`claim_citations` ·
`disagreements`←`disputes` · `quran_words`←`tokens` ·
`word_segments`←`morphological_analyses`.

> **قراءة الفجوة:** الناقص ليس تفاصيل — إنه **طبقة المقاطع كلها**
> (`documents → pages → passages → quotations`). وهي التي تجعل الاستشهاد
> قابلًا للتحقق أصلًا. بدونها لا يعمل §25 (محرك التحقق) ولا §23 (سلسلة
> النسب) ولا الباب السادس كله.

## ٤) ما يعمل فعلًا في الإنتاج المنشور

الموقع الحيّ <https://hasanawida.github.io/quran-semantic-platform/> **ملفات
ثابتة على GitHub Pages. لا خادم، ولا قاعدة بيانات، ولا سرّ، ولا كتابة.**

فمن الجداول الثلاثين، **لا واحد** يعمل في المنشور. المنشور يقرأ من
`data/v1/*.json` مولَّدة وقت البناء (242 ملفًا، ‎21.5 م.ب خامًا).

الصفحات الستّ المستبعدة — `login` `register` `account` `review` `claims`
`admin/versions` — هي **بالضبط** واجهات العنصر البشري التي تطلبها الوثيقة
في البابين الرابع والسابع.

> هذا يصطدم مباشرة بـ§21: «PostgreSQL المصدر الرسمي للحقيقة، لا توجد حقيقة
> رسمية خارجها». المنشور اليوم **كله خارجها**.

## ٥) المصادر الداخلة فعلًا

| المصدر | الدور | البصمة | الحالة |
|---|---|---|---|
| تنزيل — عثماني، حفص، عدّ كوفي | نص المصحف | نعم، لكل ملف وآية | `imported` |
| المدونة القرآنية بجامعة ليدز 0.4 | الصرف (128,219 مقطعًا) | نعم | `imported` |

**ولا مصدر ثالث.** لا معجم، ولا تفسير، ولا حديث، ولا قراءات، ولا رسم.
مصفوفة الباب الثاني تسمّي نحو أربعين كتابًا — **صفرٌ منها داخل**.

`source_works` (سجل الكتب) **لا يُبذر أصلًا**: لا شيء في `apps/api/app/db/`
يكتب فيه، فلا يمتلئ إلا بطلب `POST /sources` من مستخدم موثَّق — وهو مسار
لا وجود له في المنشور.

## ٦) ما أُصلح قبل هذا الجرد

التزامان سبقا فتح هذا الفرع، ويُسجَّلان هنا لأن الجرد يجب أن يصف الحال لا
أن يخفي تاريخه:

- `3c2b60c` — سدّ ثغرة في حارس الروابط كان يعدّ الصفحات المحلية موجودة،
  وشارة «نسخة تجريبية»، و`SCIENTIFIC_CONSTITUTION_AR.md`.
- `3327482` — سدّ ثغرتَي **اعتماد ذاتي** في `resolve_dispute` و
  `approve_correction`، وإصلاح `ops/sql/audit-hardening.sql` الذي كان
  يبدو تحصينًا وليس به.

## ٧) الأوامر المستعملة

```bash
git ls-files | wc -l
grep -rh "__tablename__" apps/api/app/models/*.py | wc -l
ls apps/api/alembic/versions/*.py | wc -l
grep -rhoE '@router\.(get|post|patch|put|delete)\("[^"]*"' apps/api/app/api/v1/*.py | wc -l
find apps/web/app -name "page*.tsx" | wc -l
find apps/web/app -name "page.node.tsx" | wc -l
ls apps/api/tests/test_*.py | wc -l
```
