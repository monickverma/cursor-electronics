-- Circuit OS — PostgreSQL Schema
-- Run this once: psql -d circuitos -f schema.sql
--
-- NOTE — there is no migration tool in this repo. docker-compose mounts this
-- file into /docker-entrypoint-initdb.d, which Postgres runs ONLY on an empty
-- data directory. Any database whose `pgdata` volume already exists will not
-- pick up a table added here; it has to be applied by hand:
--
--   docker compose exec -T db psql -U circuitos_user -d circuitos < backend/db/schema.sql
--
-- (or just the new CREATE TABLE). Confirmed 2026-09-20 when `request_log` was
-- added and did not appear on an existing volume.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    tier VARCHAR(20) NOT NULL DEFAULT 'free',  -- free | pro | team | enterprise
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);

CREATE TABLE circuit_designs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    circuit_id VARCHAR(36) UNIQUE NOT NULL,  -- matches CircuitIR.circuit_id (UUID)
    version INTEGER NOT NULL DEFAULT 1,
    intent TEXT NOT NULL,
    application_class VARCHAR(50),
    safety_class VARCHAR(20) DEFAULT 'general',
    target_mcu VARCHAR(50),
    ir_json JSONB NOT NULL,
    intent_ir JSONB,     -- Stage 2: the IntentIR the design was realised from; NULL = pre-Stage-2
    annotations JSONB,   -- Stage 2: annotation layer, merged after generation
    simulation_passed BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Existing volumes get the two Stage 2 columns from backend/db/migrations.py
-- at startup; this file only runs on an empty data directory.

CREATE INDEX idx_designs_circuit_id ON circuit_designs(circuit_id);
CREATE INDEX idx_designs_user_id ON circuit_designs(user_id);
CREATE INDEX idx_designs_project_id ON circuit_designs(project_id);

CREATE TABLE simulation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_id VARCHAR(36) NOT NULL REFERENCES circuit_designs(circuit_id) ON DELETE CASCADE,
    celery_task_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued | running | complete | failed
    circuit_type VARCHAR(50),                       -- for monitoring: rc_filter, dht_sensor, etc.
    netlist_text TEXT,
    results_json JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_simulation_runs_circuit_id ON simulation_runs(circuit_id);
CREATE INDEX idx_simulation_runs_status ON simulation_runs(status);
CREATE INDEX idx_simulation_runs_circuit_type ON simulation_runs(circuit_type);

CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_id VARCHAR(36) NOT NULL REFERENCES circuit_designs(circuit_id) ON DELETE CASCADE,
    overall_pass BOOLEAN NOT NULL,
    rules_json JSONB NOT NULL,   -- array of {rule, passed, explanation, fix}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_validation_results_circuit_id ON validation_results(circuit_id);

CREATE TABLE patch_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_id VARCHAR(36) NOT NULL REFERENCES circuit_designs(circuit_id) ON DELETE CASCADE,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    patch_json JSONB,
    change_summary TEXT,
    prompted_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patch_history_circuit_id ON patch_history(circuit_id);

CREATE TABLE generated_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_id VARCHAR(36) NOT NULL REFERENCES circuit_designs(circuit_id) ON DELETE CASCADE,
    output_type VARCHAR(30) NOT NULL,  -- firmware | schematic | bom | netlist
    file_content TEXT NOT NULL,
    file_name VARCHAR(255),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generated_outputs_circuit_id ON generated_outputs(circuit_id);

-- One row per request. PHASE_2_PLAN_v2.md §4.5.
-- No foreign keys on purpose: an analytics log that participates in
-- referential integrity can be rejected or cascade-deleted, and the rows worth
-- keeping are the ones where the design was never persisted.
CREATE TABLE request_log (
    request_id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    route VARCHAR(200) NOT NULL,
    outcome VARCHAR(20) NOT NULL,     -- completed | refused | failed | abandoned | patched
    latency_ms INTEGER NOT NULL,
    api_calls INTEGER NOT NULL DEFAULT 0,
    schema_version VARCHAR(20) NOT NULL,
    prompt_hash VARCHAR(64),
    intent_ir JSONB,
    underdetermined JSONB,
    generator VARCHAR(100),           -- name@version
    refusal_reason TEXT,
    user_id VARCHAR(36),
    circuit_id VARCHAR(36),
    status_code INTEGER,
    error TEXT
);

CREATE INDEX idx_request_log_created_at ON request_log(created_at);

-- Stage 5: the compile gate's cache. Firmware is shown only once its project
-- has built; a project is keyed by the SHA-256 of its files, so identical
-- firmware compiles once. Also created by db/migrations.py on old volumes.
CREATE TABLE firmware_builds (
    build_hash VARCHAR(64) PRIMARY KEY,   -- SHA-256 of the project files
    target VARCHAR(50) NOT NULL,          -- data/mcu_targets id
    status VARCHAR(20) NOT NULL,          -- queued | passed | failed
    log TEXT,
    seconds DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX idx_request_log_outcome ON request_log(outcome);
CREATE INDEX idx_request_log_prompt_hash ON request_log(prompt_hash);
CREATE INDEX idx_request_log_generator ON request_log(generator);
CREATE INDEX idx_request_log_user_id ON request_log(user_id);
CREATE INDEX idx_request_log_circuit_id ON request_log(circuit_id);

-- Trigger: update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER circuit_designs_updated_at
    BEFORE UPDATE ON circuit_designs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
