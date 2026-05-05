"""mci supergraph incident clustering

Revision ID: 20260506_0002
Revises: 20260504_0001
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op

revision = "20260506_0002"
down_revision = "20260504_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'incidents'
                  AND column_name = 'cluster_id'
                  AND udt_name <> 'uuid'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'incidents'
                  AND column_name = 'cluster_id_legacy_text'
            ) THEN
                ALTER TABLE incidents RENAME COLUMN cluster_id TO cluster_id_legacy_text;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS cluster_id UUID")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS is_mci BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS is_mci_coordinator BOOLEAN NOT NULL DEFAULT false")
    op.execute("CREATE INDEX IF NOT EXISTS idx_incidents_cluster_id ON incidents(cluster_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_incidents_mci_active ON incidents(is_mci, created_at DESC) WHERE is_mci = true")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_incidents_mci_active")
    op.execute("DROP INDEX IF EXISTS idx_incidents_cluster_id")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS is_mci_coordinator")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS is_mci")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS cluster_id")
