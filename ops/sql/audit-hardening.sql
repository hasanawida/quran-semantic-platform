-- سجل التدقيق ملحق-فقط: يُمنع دور التطبيق من تعديله أو حذفه في القاعدة
-- نفسها، فوق منع طبقة ORM ومحفّز الهجرة.
--
-- **يُنفَّذ بعد الهجرات، لا قبلها** — فهو يشير إلى جدول `audit_logs`
-- الذي تنشئه Alembic:
--   psql -U OWNER -d DB -v app_role=qsp_app -f ops/sql/audit-hardening.sql
--
-- **ودور التطبيق يُمرَّر صراحةً ولا يُخمَّن.** كان الملف يقرأه من
-- `current_setting('qsp.app_role', true)` — وهو إعداد لا يضبطه شيء في
-- المستودع كله. فيعود NULL، ويُتخطّى السحب بلا كلمة، ولا ينفَّذ إلا
-- `REVOKE ... FROM PUBLIC` وهو لا يمسّ دورًا له منحٌ صريح ولا مالكَ
-- الجدول. فكان الملف **يبدو تحصينًا وليس به**. (رصده تدقيق مواصفة
-- «سجل لا يُعدَّل بعد النشر» في 2026-07-26.)
--
-- ولهذا موضعه **خارج** `ops/postgres-init/`: ذلك المجلد مركَّب على
-- `/docker-entrypoint-initdb.d`، فتنفّذه Postgres عند أول تهيئة — أي قبل
-- وجود الجدول — وتحت `ON_ERROR_STOP=1`، فكان يُجهض أول إقلاع كله ويترك
-- مجلد البيانات نصف مهيَّأ. (رصده فحص جاهزية النشر في 2026-07-25.)
\if :{?app_role}
\else
  \echo '!! app_role غير ممرَّر — والتحصين بلا دور التطبيق لا معنى له.'
  \echo '   psql -U OWNER -d DB -v app_role=qsp_app -f ops/sql/audit-hardening.sql'
  \quit
\endif

REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE ON audit_logs FROM :"app_role";

-- والتحقق جزء من التحصين لا حاشية له: لو بقي للدور حقُّ تعديل أو حذف
-- أُجهض السكربت بخطأ، فلا يُظنّ أنه وقع وهو لم يقع.
DO $$
DECLARE leftover text;
BEGIN
  SELECT string_agg(priv, ', ') INTO leftover
  FROM unnest(ARRAY['UPDATE', 'DELETE']) AS priv
  WHERE has_table_privilege(:'app_role', 'audit_logs', priv);

  IF leftover IS NOT NULL THEN
    RAISE EXCEPTION
      'التحصين لم يقع: الدور % ما زال يملك (%) على audit_logs. '
      'أرجح سبب: الدور مالكُ الجدول — والمالك لا يُسحب منه. '
      'شغّل التطبيق بدور غير المالك.', :'app_role', leftover;
  END IF;
END $$;

\echo 'audit_logs: سُحب UPDATE/DELETE من PUBLIC ومن دور التطبيق، وتُحقّق منه.'
