-- سجل التدقيق ملحق-فقط: يُمنع دور التطبيق من تعديله أو حذفه في القاعدة
-- نفسها، فوق منع طبقة ORM ومحفّز الهجرة.
--
-- **يُنفَّذ بعد الهجرات، لا قبلها** — فهو يشير إلى جدول `audit_logs`
-- الذي تنشئه Alembic:
--   psql -U OWNER -d DB -f ops/sql/audit-hardening.sql
--
-- ولهذا موضعه **خارج** `ops/postgres-init/`: ذلك المجلد مركَّب على
-- `/docker-entrypoint-initdb.d`، فتنفّذه Postgres عند أول تهيئة — أي قبل
-- وجود الجدول — وتحت `ON_ERROR_STOP=1`، فكان يُجهض أول إقلاع كله ويترك
-- مجلد البيانات نصف مهيَّأ. (رصده فحص جاهزية النشر في 2026-07-25.)
REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;
DO $$
DECLARE app_role text := current_setting('qsp.app_role', true);
BEGIN
  IF app_role IS NOT NULL THEN
    EXECUTE format('REVOKE UPDATE, DELETE ON audit_logs FROM %I', app_role);
  END IF;
END $$;
