#!/bin/sh
# استرجاع نسخة احتياطية إلى قاعدة **مؤقتة** والتحقق من سلامتها.
#
# القاعدة: نسخة لم تُجرَّب ليست نسخة. كثيرٌ من الأنظمة تكتشف أن نسخها
# فارغة أو ناقصة يوم تحتاجها. فهذا السكربت يسترجع فعلًا ويعدّ فعلًا.
#
# **لا يمسّ قاعدة الإنتاج**: ينشئ قاعدة باسم مؤقت، ويتحقق فيها، ثم
# يحذفها. تشغيله على خادم حيّ آمن.
#
#   sh ops/restore-check.sh /backups/daily/qsp-20260725T030000Z.dump
#
# متغيرات البيئة: PGHOST PGUSER PGPASSWORD PGDATABASE (بدور المالك)

set -eu

DUMP="${1:?الاستعمال: restore-check.sh <ملف-النسخة>}"
[ -f "$DUMP" ] || { echo "الملف غير موجود: $DUMP" >&2; exit 1; }

CHECK_DB="qsp_restore_check_$$"
cleanup() { dropdb --if-exists "$CHECK_DB" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "استرجاع $DUMP إلى قاعدة مؤقتة $CHECK_DB…"
createdb "$CHECK_DB"
# --no-owner: النسخة مأخوذة بلا ملكية، والقاعدة المؤقتة يملكها المنفّذ
pg_restore --no-owner --no-privileges -d "$CHECK_DB" "$DUMP"

echo "التحقق من الكمال…"
RESULT=$(psql -d "$CHECK_DB" -tA -F'|' <<'SQL'
SELECT
  (SELECT count(*) FROM surahs),
  (SELECT count(*) FROM ayahs),
  (SELECT count(*) FROM audit_logs),
  (SELECT count(*) FROM quran_text_versions WHERE is_active),
  (SELECT coalesce(sum(length(uthmani_text)), 0) FROM ayahs);
SQL
)

SURAHS=$(echo "$RESULT" | cut -d'|' -f1)
AYAHS=$(echo "$RESULT" | cut -d'|' -f2)
AUDIT=$(echo "$RESULT" | cut -d'|' -f3)
ACTIVE=$(echo "$RESULT" | cut -d'|' -f4)
CHARS=$(echo "$RESULT" | cut -d'|' -f5)

echo "  السور: $SURAHS   الآيات: $AYAHS   سجل التدقيق: $AUDIT"
echo "  إصدارات نشطة: $ACTIVE   محارف النص: $CHARS"

FAILED=0
[ "$SURAHS" = "114" ]  || { echo "✗ عدد السور ليس 114" >&2; FAILED=1; }
[ "$AYAHS" = "6236" ]  || { echo "✗ عدد الآيات ليس 6236" >&2; FAILED=1; }
[ "$ACTIVE" = "1" ]    || { echo "✗ الإصدارات النشطة ليست واحدًا" >&2; FAILED=1; }
[ "$CHARS" -gt 300000 ] || { echo "✗ نص الآيات أقصر مما يجب — نسخة ناقصة" >&2; FAILED=1; }
# سجل التدقيق لا يُعاد بناؤه، ففراغه في نسخة إنتاج علامة خطر
[ "$AUDIT" -gt 0 ]     || { echo "✗ سجل التدقيق فارغ" >&2; FAILED=1; }

if [ "$FAILED" = "0" ]; then
  echo "✓ النسخة سليمة وقابلة للاسترجاع."
else
  echo "✗ النسخة معطوبة — **لا تعتمد عليها**." >&2
fi
exit "$FAILED"
