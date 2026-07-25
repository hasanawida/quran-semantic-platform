-- يُنفَّذ مرة واحدة عند أول تهيئة لقاعدة البيانات (docker-entrypoint-initdb.d).
-- ينشئ دور التطبيق غير المميز: لا DDL، ولا حذف ولا تعديل في سجل التدقيق.
-- الهجرات تُشغَّل بدور المالك خطوةً منفصلة (راجع docs/DEPLOYMENT_AR.md).

\set app_user `echo "$POSTGRES_APP_USER"`
\set app_password `echo "$POSTGRES_APP_PASSWORD"`

CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_user";

-- الجداول تُنشأ لاحقًا بالهجرات، فتُضبط الصلاحيات الافتراضية مسبقًا
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";
