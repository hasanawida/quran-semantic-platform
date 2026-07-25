-- يُنفَّذ بعد الهجرات يدويًا:
--   psql -U OWNER -d DB -f ops/postgres-init/20-audit-hardening.sql
-- سجل التدقيق ملحق-فقط: يُمنع دور التطبيق من تعديله أو حذفه في القاعدة
-- نفسها، فوق منع طبقة ORM ومحفّز الهجرة.
REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;
DO $$
DECLARE app_role text := current_setting('qsp.app_role', true);
BEGIN
  IF app_role IS NOT NULL THEN
    EXECUTE format('REVOKE UPDATE, DELETE ON audit_logs FROM %I', app_role);
  END IF;
END $$;
