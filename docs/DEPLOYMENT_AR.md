# النشر: موقعًا وتطبيقًا للهاتف

## ما الذي يُنشر بالضبط

| المكوّن | الصورة | المنفذ |
| --- | --- | --- |
| قاعدة البيانات | `postgres:16-alpine` | داخلي فقط |
| الـ API | `apps/api/Dockerfile` (FastAPI) | 8000 |
| الموقع | `apps/web/Dockerfile` (Next standalone) | 3000 |

الموقع نفسه هو تطبيق الهاتف: تطبيق ويب قابل للتثبيت (PWA) بأيقونات
وعمل بلا اتصال. لا يلزم متجر تطبيقات ليصل إلى المستخدم.

## 1) المتغيرات المطلوبة

انسخ `.env.production.example` إلى `.env` بجوار `docker-compose.prod.yml`
واملأ **كل** القيم. الملف يرفض الإقلاع إن نقص أي منها.

```bash
cp .env.production.example .env
# JWT_SECRET سر قوي — لا تترك القيمة الافتراضية أبدًا
openssl rand -base64 48
```

## 2) دور قاعدة بيانات غير مميز

الهجرات تُشغَّل بدور المالك، والتطبيق يعمل بدور لا يملك DDL:

```sql
-- بدور المالك
CREATE ROLE quran_app LOGIN PASSWORD '...';
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO quran_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quran_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO quran_app;
REVOKE UPDATE, DELETE ON audit_logs FROM quran_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO quran_app;
```

## 3) الهجرات (خطوة مستقلة، بدور المالك)

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e DATABASE_URL="postgresql+asyncpg://OWNER:PASS@postgres:5432/DB" \
  api alembic upgrade head
```

يُنشئ هذا المخطط كاملًا مع **محفّز حماية سجل التدقيق** في Postgres.

### 3‑ب) تحصين سجل التدقيق (بدور المالك، بعد الهجرات)

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_OWNER" -d "$POSTGRES_DB" \
  < ops/sql/audit-hardening.sql
```

يسحب صلاحية `UPDATE` و`DELETE` على `audit_logs` من دور التطبيق ومن
`PUBLIC` — طبقة ثالثة تحت منع ORM ومحفّز الهجرة.

> **لماذا خطوة منفصلة:** الملف يشير إلى جدول تنشئه Alembic، فلا يصحّ
> تنفيذه عند تهيئة القاعدة. كان موضوعًا في `ops/postgres-init/` وهو
> مركَّب على `/docker-entrypoint-initdb.d`، فكان **يُجهض أول إقلاع**
> بخطأ «relation does not exist» تحت `ON_ERROR_STOP=1`. نُقل إلى
> `ops/sql/` في 2026-07-25.

## 4) البذر والاستيراد (مرة واحدة، موثقة)

```bash
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.cli seed
```

يبذر السور والآيات من `data/quran_bundle.json.gz` ويُنشئ إصدار النص
ويُفعّله. **الأمر يعمل في الإنتاج** حيث `AUTO_CREATE_SCHEMA=false`،
لأن البذر إدخال بيانات لا إنشاء مخطط. وهو **يرفض** العمل إن كانت
القاعدة مبذورة أصلًا، فتكراره آمن.

ثم خط المعالجة:

```bash
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.cli pipeline
```

يرمّز الكلمات، ويستورد التحليل الصرفي (128,219 مقطعًا)، ويشتق مواضع
الجذور، ثم يفحص المواضع المرجعية الـ132. كل خطوة تُسجَّل في سجل
التدقيق. يستغرق دقيقة تقريبًا على Postgres، ويخرج برمز غير صفري إن
سقط أي موضع مرجعي.

> **لا تستعمل `bootstrap` في الإنتاج.** هو أمر تطوير يمرّ عبر
> `init_db()` التي تعود مبكرًا حين `AUTO_CREATE_SCHEMA=false` — فكان
> يخرج بلا بذر ثم يسقط بـ`NO_ACTIVE_VERSION`، ويترك موقعًا حيًّا بقاعدة
> فارغة. (صُحّح في 2026-07-25.)

## 5) الإقلاع

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 6) الوسيط العكسي (TLS)

الحاويتان تعملان على HTTP خلف وسيط يتولى الشهادة. المطلوب من الوسيط:

- إنهاء TLS وإجبار HTTPS (الـ API يرسل HSTS في وضع الإنتاج).
- تمرير `X-Forwarded-Proto` و`X-Forwarded-For` (uvicorn يعمل بـ
  `--proxy-headers`).
- توجيه `/api/` إلى `api:8000` و`/` إلى `web:3000` — بهذا يصير الأصل
  واحدًا فيسهل تخزين عامل الخدمة ولا يحتاج CORS.

> إن كان الـ API على نطاق مختلف، اضبط `ALLOWED_ORIGINS` على أصل الموقع
> بالضبط، ولا تستعمل `*` أبدًا.

## 7) بعد النشر — قائمة تحقق

```bash
curl -fsS https://example.org/health
curl -fsS https://example.org/api/v1/export/provenance | head -c 200
curl -fsS https://example.org/api/v1/ai/readiness | head -c 200
curl -fsSI https://example.org/api/v1/export/provenance | grep -i strict-transport
```

- [ ] `/health` يعيد `database: ok`
- [ ] بيان الأصول يظهر بصمة الإصدار وبصمة المصدر الصرفي
- [ ] `Strict-Transport-Security` موجودة
- [ ] `/docs` يعيد 404 (التوثيق معطَّل في الإنتاج)
- [ ] تسجيل دخول بحساب حقيقي يعمل، ولا وجود لحسابات `@qsp.example`
- [ ] بوابة الذكاء الاصطناعي تعيد `enabled: false`

## تثبيت التطبيق على الهاتف

بعد أن يعمل الموقع على HTTPS:

| النظام | الخطوات |
| --- | --- |
| Android (Chrome) | القائمة ← «تثبيت التطبيق» / «إضافة إلى الشاشة الرئيسة» |
| iOS (Safari) | زر المشاركة ← «إضافة إلى الشاشة الرئيسية» |
| سطح المكتب | أيقونة التثبيت في شريط العنوان |

ما يوفره التثبيت:

- أيقونة ونافذة مستقلة (`display: standalone`) بلا شريط متصفح.
- اختصارات سريعة: البحث بالجذر، بيان الأصول، الادعاءات.
- عمل بلا اتصال لما سبقت زيارته، مع **شارة صريحة** تنبّه أن المعروض قد
  لا يكون أحدث ما على الخادم — لا يُخفى ذلك عن الباحث.
- لا تُخزَّن مطلقًا استجابات المصادقة ولا المسارات الإدارية.

**شرطان لا بديل عنهما:** HTTPS (عامل الخدمة لا يعمل بدونه إلا على
localhost)، ووصول `/sw.js` و`/manifest.webmanifest` من جذر النطاق.

## تطبيق أصيل (لاحقًا)

المنصة API-first، فالمسار إلى تطبيق أصيل مفتوح دون إعادة بناء:
Expo/React Native يستهلك المسارات نفسها، مع تخزين محلي بحزم إصدارات
موقّعة ببصمات — تفصيله في `WEB_MOBILE_ROADMAP_AR.md`. لا يبدأ قبل أن
يستقر عقد الـ API ويكتمل ضمان الجودة.

## النسخ الاحتياطي

**مؤتمت في التركيب.** خدمة `backup` تعمل على الشبكة الداخلية وحدها،
وتأخذ `pg_dump -Fc` بدور المالك كل `BACKUP_INTERVAL_SECONDS` (يوميًا
افتراضًا)، باحتفاظ متدرّج: ٧ يومية و٤ أسبوعية.

> **لماذا هي شرط لا تحسين:** سجل التدقيق ملحق-فقط بحكم البناء — يمنعه
> محرّك ORM ومحفّز Postgres معًا — أي **لا يُعاد بناؤه**. ففقد القاعدة
> يفقد إسناد كل استيراد واعتماد ومراجعة وتصحيح، وهو ما بُني السجل
> ليحفظه.

### نسخة فورية قبل أي عملية خطرة

قبل كل استيراد أو تفعيل إصدار:

```bash
docker compose -f docker-compose.prod.yml exec backup \
  sh /usr/local/bin/backup.sh once
```

### التحقق من صلاحية النسخة — **لا تتخطَّ هذه**

نسخة لم تُجرَّب ليست نسخة. السكربت يسترجع إلى قاعدة **مؤقتة** ويعدّ فيها،
ولا يمسّ الإنتاج:

```bash
docker compose -f docker-compose.prod.yml exec backup \
  sh /usr/local/bin/restore-check.sh /backups/daily/qsp-<الختم>.dump
```

يفشل برمز غير صفري إن لم يجد ١١٤ سورة و٦٢٣٦ آية وإصدارًا نشطًا واحدًا
وسجل تدقيق غير فارغ.

### ⚠ النسخ داخل الخادم ليست نسخًا احتياطيًا

حجم `backup_data` يبقى بعد إعادة بناء الحاويات، لكنه **يذهب مع الخادم**
إن ضاع. انقلها إلى تخزين خارجي — مهمّة `cron` على المضيف:

```bash
0 4 * * * docker compose -f /srv/qsp/docker-compose.prod.yml \
  cp backup:/backups/daily /srv/qsp-offsite/ && \
  rclone sync /srv/qsp-offsite remote:qsp-backups
```

### الاسترجاع الفعلي

```bash
# 1) أوقف التطبيق ليتوقف الكتابة (القاعدة تبقى تعمل)
docker compose -f docker-compose.prod.yml stop api web
# 2) استرجع بدور المالك
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore --clean --if-exists --no-owner -U "$POSTGRES_OWNER" \
  -d "$POSTGRES_DB" < backups/daily/qsp-<الختم>.dump
# 3) أعد تحصين سجل التدقيق (‎--clean يسقط الصلاحيات)
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_OWNER" -d "$POSTGRES_DB" \
  -v app_role="$POSTGRES_APP_USER" < ops/sql/audit-hardening.sql
# 4) شغّل، ثم افحص المواضع المرجعية
docker compose -f docker-compose.prod.yml start api web
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.cli golden-check
```

> الخطوة ٣ ليست اختيارية: `pg_restore --clean` يُسقط الجدول ويعيد إنشاءه،
> فتذهب صلاحياته المسحوبة ويصير سجل التدقيق قابلًا للتعديل من دور التطبيق.

## قياس الاستعمال (اختياري)

الموقع الثابت لا يستطيع عدّ زوّاره بنفسه: العدّاد يحتاج خادمًا تملكه أو
سجلّاته، وGitHub Pages لا تعطي أيًّا منهما. فكل قياس ممكن يمرّ بخدمة
خارجية — وهذا مصرَّح به في `/privacy` بلا تلطيف.

**المعتمد:** [Umami](https://umami.is) — شيفرة مفتوحة (MIT)، بلا كوكيز،
ولا تخزّن عنوان IP. والخطة المجانية: ١٠٠ ألف حدث شهريًا، و٣ مواقع، وحفظ
٦ أشهر.

### التفعيل — أربع خطوات

1. أنشئ حسابًا على <https://cloud.umami.is> (مجاني، بلا بطاقة).
2. أضف موقعًا بعنوان `hasanawida.github.io` فيعطيك **Website ID**.
3. في المستودع: `Settings ▸ Secrets and variables ▸ Actions ▸ Variables`
   ثم `New repository variable` باسم `UMAMI_ID` وقيمته المعرّف.
4. ادفع أي تغيير (أو شغّل `Deploy to GitHub Pages` يدويًا) — يظهر
   القياس خلال دقائق.

### ما ستراه

| السؤال | الجواب في لوحة Umami |
| --- | --- |
| كم زائرًا؟ | الزوّار والجلسات يوميًا وشهريًا |
| **ماذا يفعلون؟** | أكثر الصفحات زيارةً — أي السور والآيات والجذور |
| **كم من الوقت؟** | متوسط مدة الزيارة، وعدد الصفحات لكل جلسة |
| من أين جاؤوا؟ | المواقع المُحيلة، والدول، والأجهزة والمتصفحات |

### التعطيل

احذف المتغيّر `UMAMI_ID` وادفع. لا تعديل شيفرة، ولا يبقى أثر في الموقع.

> **حدٌّ يجب أن يُعلم:** مانعات التعقّب تحجب هذا النوع من القياس، فالرقم
> الذي تراه أقل من الحقيقة — لا أكثر منها. وهذا حدُّ كل قياس من جهة
> المتصفح، لا عيب في الأداة.

## لقطة حركة المستودع (اختيارية)

سير `traffic.yml` يلتقط يوميًا **مشاهدات صفحة المستودع على github.com**
ونسخه. نافذة GitHub أربعة عشر يومًا فقط، فما لا يُلتقط يسقط بلا رجعة.

> **ليست زوّار الموقع.** هذه أرقام صفحة المستودع لا الموقع المنشور.
> لقياس الموقع انظر قسم «قياس الاستعمال» أعلاه.

### التفعيل — رمز شخصي

رمز GitHub التلقائي **لا يكفي** ولا يمكن أن يكفي: واجهة الحركة تشترط
صلاحية إدارة المستودع، و`administration` ليست مفتاحًا مقبولًا في
`permissions` أصلًا. فيلزم رمز شخصي:

1. <https://github.com/settings/personal-access-tokens> ← `Fine-grained`
2. `Repository access` ← هذا المستودع وحده.
3. `Permissions` ← `Administration: Read-only` (وهي التي تفتح الحركة).
4. انسخ الرمز، ثم في المستودع: `Settings ▸ Secrets and variables ▸
   Actions ▸ Secrets` ← `New repository secret` باسم **`TRAFFIC_TOKEN`**.

وبلا الرمز يتخطّى السير بإشعار واضح ولا يفشل — سيرٌ أحمرُ كل يوم بلا
سبب يُصلَح يُعلَّم ضجيجًا فيُهمَل، ويُهمَل معه ما يستحق الانتباه.

> ولا تمنح الرمز صلاحية كتابة: القراءة تكفي، وأقلّ الصلاحيات أسلم.
