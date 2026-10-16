CREATE TABLE IF NOT EXISTS erp_commands (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_erp_id integer NOT NULL CHECK (company_erp_id > 0),
    resource varchar(40) NOT NULL,
    action varchar(10) NOT NULL CHECK (action IN ('create','update')),
    record_id varchar(100),
    payload jsonb NOT NULL,
    expected jsonb NOT NULL DEFAULT '{}',
    requested_by varchar(100) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','applied','rejected')),
    lease_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_erp_commands_queue ON erp_commands (tenant_id, status, created_at);
CREATE TABLE IF NOT EXISTS erp_agent_capabilities (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    resources jsonb NOT NULL,
    seen_at timestamptz NOT NULL DEFAULT now()
);
