CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS external_tenant_id varchar(100),
    ADD COLUMN IF NOT EXISTS license_source_updated_at timestamptz,
    ALTER COLUMN data_vencimento DROP NOT NULL;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS external_company_id varchar(100);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_external_tenant_id
    ON tenants (external_tenant_id)
    WHERE external_tenant_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_external_company_id
    ON companies (external_company_id)
    WHERE external_company_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_cnpj_normalized
    ON companies ((regexp_replace(cnpj, '\D', '', 'g')))
    WHERE cnpj IS NOT NULL;

CREATE TABLE IF NOT EXISTS license_control_sync_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    source varchar(50) NOT NULL,
    ip_address inet,
    received integer NOT NULL DEFAULT 0,
    created integer NOT NULL DEFAULT 0,
    updated integer NOT NULL DEFAULT 0,
    disabled integer NOT NULL DEFAULT 0,
    ignored integer NOT NULL DEFAULT 0,
    failed integer NOT NULL DEFAULT 0,
    duration_ms integer NOT NULL DEFAULT 0,
    status varchar(30) NOT NULL,
    message text,
    error_details jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_license_control_sync_logs_created_at
    ON license_control_sync_logs (created_at DESC);
