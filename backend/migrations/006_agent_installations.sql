CREATE TABLE IF NOT EXISTS agent_installations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
    installation_id varchar(100) NOT NULL UNIQUE,
    machine_name varchar(255) NOT NULL,
    machine_fingerprint varchar(128) NOT NULL,
    agent_version varchar(50) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'ACTIVE',
    activated_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_agent_installations_status
        CHECK (status IN ('PENDING', 'ACTIVE', 'REVOKED', 'BLOCKED'))
);

CREATE INDEX IF NOT EXISTS ix_agent_installations_tenant
    ON agent_installations (tenant_id, status);
