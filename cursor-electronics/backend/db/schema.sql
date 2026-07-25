-- Circuit OS — PostgreSQL Schema
-- Run this once: psql -d circuitos -f schema.sql

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
    simulation_passed BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
