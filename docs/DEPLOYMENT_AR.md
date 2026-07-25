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

## 4) البذر والاستيراد (مرة واحدة، موثقة)

```bash
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.cli bootstrap
```

يبذر النص من `data/quran_bundle.json.gz`، يرمّز الكلمات، يستورد التحليل
الصرفي (128,219 مقطعًا)، يشتق مواضع الجذور، ثم يفحص المواضع المرجعية.
كل خطوة تُسجَّل في سجل التدقيق. الاستيراد يستغرق دقيقة تقريبًا على
Postgres.

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

## النسخ الاحتياطي (لم يُؤتمت بعد)

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U OWNER -Fc DB > backup-$(date +%F).dump
```

سجل التدقيق ملحق-فقط، فاستعادة نسخة قديمة تفقد أثر ما بعدها. أي جدولة
نسخ يجب أن تسبق أي عملية استيراد أو تفعيل إصدار.
