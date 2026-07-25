#!/bin/sh
# نسخ احتياطي لقاعدة الإنتاج، باحتفاظ متدرّج.
#
# **لماذا يلزم هنا أكثر مما يلزم غيره:** سجل التدقيق في هذه المنصة
# ملحق-فقط بحكم البناء — يمنع تعديله محرّكُ ORM ومحفّزُ Postgres معًا.
# وذلك يعني أنه **لا يُعاد بناؤه**. ففقدُ القاعدة ليس فقد بيانات فحسب،
# بل فقدُ إسناد كل عملية استيراد واعتماد ومراجعة وتصحيح جرت في المنصة —
# وهو بالضبط ما بُني السجل ليحفظه.
#
# يعمل في حاوية جانبية على الشبكة الداخلية، فلا يُفتح منفذ القاعدة.
#
# متغيرات البيئة (كلها إلزامية عدا المهلة):
#   PGHOST PGUSER PGPASSWORD PGDATABASE   بيانات الاتصال (بدور المالك)
#   BACKUP_DIR                            مجلد الحفظ (حجم مركَّب)
#   BACKUP_INTERVAL_SECONDS               الفاصل بين النسخ (افتراضي يومي)

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

# احتفاظ متدرّج: أسبوع من اليومية، وشهر من الأسبوعية
KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

take_backup() {
  stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
  target="${BACKUP_DIR}/daily/qsp-${stamp}.dump"
  mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly"

  # -Fc صيغة مضغوطة تسمح بالاسترجاع الانتقائي وبالتوازي
  # يُكتب إلى ملف مؤقت ثم يُنقل: نسخة نصف مكتوبة أسوأ من لا نسخة
  if pg_dump -Fc --no-owner --no-privileges -f "${target}.partial"; then
    mv "${target}.partial" "${target}"
    log "نسخة: ${target} ($(du -h "${target}" | cut -f1))"
  else
    rm -f "${target}.partial"
    log "فشل النسخ — أُبقيت النسخ السابقة كما هي"
    return 1
  fi

  # نسخة أسبوعية يوم الأحد
  if [ "$(date -u '+%u')" = "7" ]; then
    cp "${target}" "${BACKUP_DIR}/weekly/qsp-${stamp}.dump"
    log "ونسخة أسبوعية"
  fi

  # التشذيب بعد نجاح النسخة لا قبلها
  # shellcheck disable=SC2012 — الأسماء مولَّدة بختم زمني فلا مسافات فيها
  ls -1t "${BACKUP_DIR}/daily/"*.dump 2>/dev/null | tail -n "+$((KEEP_DAILY + 1))" \
    | while read -r old; do rm -f "$old" && log "حُذفت: $(basename "$old")"; done
  ls -1t "${BACKUP_DIR}/weekly/"*.dump 2>/dev/null | tail -n "+$((KEEP_WEEKLY + 1))" \
    | while read -r old; do rm -f "$old" && log "حُذفت: $(basename "$old")"; done
}

if [ "${1:-loop}" = "once" ]; then
  take_backup
  exit $?
fi

log "خدمة النسخ الاحتياطي — كل ${INTERVAL} ثانية، احتفاظ ${KEEP_DAILY}/${KEEP_WEEKLY}"
while true; do
  take_backup || log "سيُعاد المحاولة في الدورة القادمة"
  sleep "${INTERVAL}"
done
