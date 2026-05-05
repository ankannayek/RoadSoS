"""production hardening baseline

Revision ID: 20260504_0001
Revises:
Create Date: 2026-05-04
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20260504_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "database" / "schema.sql"
    if schema_path.exists():
        op.get_bind().exec_driver_sql(schema_path.read_text(encoding="utf-8"))

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_private_profiles (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            key_id VARCHAR(80) NOT NULL,
            encrypted_payload TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_private_profiles_key ON user_private_profiles(key_id)")

    op.execute("ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(160)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_background_jobs_dedupe_active
        ON background_jobs(dedupe_key)
        WHERE dedupe_key IS NOT NULL AND status IN ('pending', 'running')
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_rag_chunks_embedding")
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
        ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_incidents_accepted_responder') THEN
                ALTER TABLE incidents
                ADD CONSTRAINT fk_incidents_accepted_responder
                FOREIGN KEY (accepted_responder_id) REFERENCES volunteers(id) ON DELETE SET NULL NOT VALID;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_notification_logs_incident') THEN
                ALTER TABLE notification_logs
                ADD CONSTRAINT fk_notification_logs_incident
                FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE SET NULL NOT VALID;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_service_reports_service') THEN
                ALTER TABLE service_reports
                ADD CONSTRAINT fk_service_reports_service
                FOREIGN KEY (service_id) REFERENCES emergency_services(id) ON DELETE SET NULL NOT VALID;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_service_reports_reporter') THEN
                ALTER TABLE service_reports
                ADD CONSTRAINT fk_service_reports_reporter
                FOREIGN KEY (reporter_user_id) REFERENCES users(id) ON DELETE SET NULL NOT VALID;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role') THEN
                ALTER TABLE users
                ADD CONSTRAINT ck_users_role
                CHECK (role IN ('user', 'volunteer', 'dispatcher', 'judge', 'admin')) NOT VALID;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_background_jobs_status') THEN
                ALTER TABLE background_jobs
                ADD CONSTRAINT ck_background_jobs_status
                CHECK (status IN ('pending', 'running', 'succeeded', 'failed')) NOT VALID;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_background_jobs_dedupe_active")
    op.execute("ALTER TABLE background_jobs DROP COLUMN IF EXISTS dedupe_key")
    op.execute("DROP TABLE IF EXISTS user_private_profiles")
    op.execute("DROP INDEX IF EXISTS idx_rag_chunks_embedding")
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL::vector(384)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
        ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )
