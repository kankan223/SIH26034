"""add audit_logs SELECT+INSERT only grants

Revision ID: 002
Revises: 001
Create Date: 2026-09-06

Grant the application role SELECT + INSERT only on audit_logs,
revoking UPDATE and DELETE to enforce append-only at the DB layer.

See: prd.md §20.1 (audit_logs table), prd.md §25.1 (audit trail)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Grant SELECT and INSERT on audit_logs to the app role.
    # This permits the application to write audit entries and read
    # them for admin queries, while UPDATE/DELETE remain unavailable.
    op.execute(sa.text("GRANT SELECT, INSERT ON TABLE audit_logs TO app_user"))

    # Explicitly revoke any lingering UPDATE/DELETE grants (defensive).
    op.execute(sa.text("REVOKE ALL ON TABLE audit_logs FROM app_user"))
    op.execute(sa.text("GRANT SELECT, INSERT ON TABLE audit_logs TO app_user"))


def downgrade() -> None:
    op.execute(sa.text("REVOKE ALL ON TABLE audit_logs FROM app_user"))
    # Restore full access so the migration is reversible for dev environments.
    op.execute(sa.text("GRANT ALL ON TABLE audit_logs TO app_user"))
