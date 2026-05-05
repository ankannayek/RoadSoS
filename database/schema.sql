-- RoadSoS production-ready baseline schema for Neon Postgres + PostGIS + pgvector
-- Run: psql "$DATABASE_URL" -f database/schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
    CREATE TYPE priorityenum AS ENUM ('P1_CRITICAL', 'P2_HIGH', 'P3_MEDIUM', 'P4_LOW');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE incidentstatus AS ENUM ('active', 'acknowledged', 'escalated', 'resolved', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE incidentsource AS ENUM ('manual', 'auto_detect', 'voice', 'silent', 'bystander');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    blood_group VARCHAR(10),
    medical_conditions VARCHAR(500),
    allergies VARCHAR(300),
    emergency_contacts JSONB,
    preferred_language VARCHAR(12) NOT NULL DEFAULT 'en',
    role VARCHAR(30) NOT NULL DEFAULT 'user',
    fcm_tokens JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(30) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_tokens JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS volunteers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    available BOOLEAN NOT NULL DEFAULT false,
    rating DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    completed_responses DOUBLE PRECISION NOT NULL DEFAULT 0,
    cancelled_responses DOUBLE PRECISION NOT NULL DEFAULT 0,
    skills TEXT[] DEFAULT ARRAY[]::TEXT[],
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    location GEOGRAPHY(POINT, 4326),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    priority priorityenum NOT NULL,
    triage_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    source incidentsource NOT NULL DEFAULT 'manual',
    silent BOOLEAN NOT NULL DEFAULT false,
    bystander_mode BOOLEAN NOT NULL DEFAULT false,
    victim_name VARCHAR(100),
    victim_phone VARCHAR(20),
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    location GEOGRAPHY(POINT, 4326),
    status incidentstatus NOT NULL DEFAULT 'active',
    accepted_responder_id UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS incident_responder_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    responder_type VARCHAR(30) NOT NULL,
    responder_id UUID,
    channel VARCHAR(30) NOT NULL,
    tier VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS emergency_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    type VARCHAR(30) NOT NULL,
    phone VARCHAR(20),
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    capacity INTEGER,
    confidence_score NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    source VARCHAR(40) NOT NULL DEFAULT 'user_report',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS service_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID,
    reporter_user_id UUID,
    name VARCHAR(150) NOT NULL,
    type VARCHAR(30) NOT NULL,
    phone VARCHAR(20),
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    note TEXT,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    volunteer_id UUID REFERENCES volunteers(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_feedback_incident_volunteer UNIQUE (incident_id, volunteer_id)
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID,
    recipient_type VARCHAR(30) NOT NULL,
    recipient VARCHAR(255),
    channel VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    provider_message_id VARCHAR(255),
    error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(80) NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(160) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    source_type VARCHAR(40) NOT NULL DEFAULT 'static',
    version VARCHAR(40) NOT NULL DEFAULT 'v1',
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES rag_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    heading VARCHAR(255),
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    embedding_model VARCHAR(80) NOT NULL DEFAULT 'hashing-v1',
    embedding vector(384),
    search_vector TSVECTOR,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rag_source_chunk UNIQUE (source_id, chunk_index)
);

-- Keep location columns synchronized for raw SQL writes.
CREATE OR REPLACE FUNCTION set_volunteer_location() RETURNS trigger AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326)::geography;
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_incident_location() RETURNS trigger AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326)::geography;
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_service_location() RETURNS trigger AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326)::geography;
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_volunteer_location ON volunteers;
CREATE TRIGGER trg_volunteer_location BEFORE INSERT OR UPDATE ON volunteers
FOR EACH ROW EXECUTE FUNCTION set_volunteer_location();

DROP TRIGGER IF EXISTS trg_incident_location ON incidents;
CREATE TRIGGER trg_incident_location BEFORE INSERT OR UPDATE ON incidents
FOR EACH ROW EXECUTE FUNCTION set_incident_location();

DROP TRIGGER IF EXISTS trg_service_location ON emergency_services;
CREATE TRIGGER trg_service_location BEFORE INSERT OR UPDATE ON emergency_services
FOR EACH ROW EXECUTE FUNCTION set_service_location();

-- Core indexes.
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_volunteers_available ON volunteers(available) WHERE available = true;
CREATE INDEX IF NOT EXISTS idx_volunteers_location ON volunteers USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_volunteers_last_active ON volunteers(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_user_created ON incidents(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents(priority);
CREATE INDEX IF NOT EXISTS idx_incidents_location ON incidents USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_services_type_active ON emergency_services(type, is_active);
CREATE INDEX IF NOT EXISTS idx_services_location ON emergency_services USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_feedback_incident ON feedback(incident_id);
CREATE INDEX IF NOT EXISTS idx_feedback_volunteer ON feedback(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_notification_incident ON notification_logs(incident_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_background_jobs_due ON background_jobs(status, run_at);
CREATE INDEX IF NOT EXISTS idx_background_jobs_type ON background_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_rag_sources_key ON rag_sources(source_key);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_search ON rag_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Seed example services around Chennai/IITM region; replace with validated OSM/Gov/NHAI pipeline.
INSERT INTO emergency_services (name, type, phone, lat, lng, confidence_score, source, metadata_json) VALUES
('ERSS India Unified Emergency', 'POLICE', '112', 13.0827, 80.2707, 0.950, 'gov', '{"coverage":"India", "note":"Unified police/fire/medical emergency routing"}'::jsonb),
('National Highway Emergency Helpline', 'AMBULANCE', '1033', 13.0827, 80.2707, 0.900, 'nhai', '{"coverage":"National Highways"}'::jsonb),
('Government Ambulance', 'AMBULANCE', '108', 13.0067, 80.2206, 0.850, 'gov', '{"coverage":"regional"}'::jsonb),
('Nearby Trauma/Hospital Placeholder', 'TRAUMA', '108', 13.0108, 80.2209, 0.700, 'seed', '{}'::jsonb),
('Fire and Rescue Placeholder', 'FIRE', '101', 13.0150, 80.2250, 0.700, 'seed', '{}'::jsonb)
ON CONFLICT DO NOTHING;
