"""phase J: audit log immutability trigger (Postgres)

دفاع في العمق: طبقة ORM تمنع تعديل سجل التدقيق وحذفه أصلًا، وهذا المحفّز
يمنعه في قاعدة البيانات نفسها فلا يفلت عبر اتصال مباشر أو أداة خارجية.

المحفّز خاص بـ Postgres. في SQLite (التطوير) تبقى حماية ORM وحدها،
وهي كافية لأن قاعدة التطوير ليست مصدر حقيقة.

Revision ID: a1c9d4e77b10
Revises: fbedf650a558
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c9d4e77b10"
down_revision: str | None = "fbedf650a558"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE = """
CREATE OR REPLACE FUNCTION audit_logs_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'سجل التدقيق ملحق-فقط: لا يسمح بالتعديل أو الحذف';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();

DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
"""

_DROP = """
DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;
DROP FUNCTION IF EXISTS audit_logs_append_only();
"""


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute(_CREATE)


def downgrade() -> None:
    if _is_postgres():
        op.execute(_DROP)
