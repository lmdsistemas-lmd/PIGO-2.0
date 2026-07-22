BEGIN;

CREATE TABLE IF NOT EXISTS report_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(80) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS report_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key VARCHAR(30) NOT NULL REFERENCES report_categories(key),
    key VARCHAR(60) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(30) NOT NULL DEFAULT 'firebird',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS report_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(60) NOT NULL REFERENCES report_sources(key) ON DELETE CASCADE,
    key VARCHAR(60) NOT NULL,
    label VARCHAR(100) NOT NULL,
    data_type VARCHAR(30) NOT NULL,
    aggregations JSONB NOT NULL DEFAULT '[]'::jsonb,
    position INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_key, key)
);

CREATE TABLE IF NOT EXISTS report_filters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(60) NOT NULL REFERENCES report_sources(key) ON DELETE CASCADE,
    key VARCHAR(60) NOT NULL,
    label VARCHAR(100) NOT NULL,
    data_type VARCHAR(30) NOT NULL,
    operators JSONB NOT NULL DEFAULT '[]'::jsonb,
    options JSONB,
    UNIQUE (source_key, key)
);

CREATE TABLE IF NOT EXISTS report_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    category VARCHAR(30) NOT NULL,
    source VARCHAR(60) NOT NULL,
    schema JSONB NOT NULL,
    permissions JSONB NOT NULL DEFAULT '["all"]'::jsonb,
    created_by VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_report_templates_tenant_category ON report_templates(tenant_id, category) WHERE active;

CREATE TABLE IF NOT EXISTS report_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES report_templates(id) ON DELETE CASCADE,
    role VARCHAR(60) NOT NULL,
    can_view BOOLEAN NOT NULL DEFAULT TRUE,
    can_edit BOOLEAN NOT NULL DEFAULT FALSE,
    can_execute BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(template_id, role)
);

CREATE TABLE IF NOT EXISTS report_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template_id UUID REFERENCES report_templates(id) ON DELETE SET NULL,
    company_erp_id VARCHAR(50) NOT NULL,
    requested_by VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    request_id VARCHAR(100),
    error_code VARCHAR(60),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS report_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template_id UUID REFERENCES report_templates(id) ON DELETE SET NULL,
    requested_by VARCHAR(100) NOT NULL,
    format VARCHAR(20) NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO report_categories(key, name, position) VALUES
('sales', 'Vendas', 1), ('finance', 'Financeiro', 2),
('accounting', 'Contabilidade', 3), ('other', 'Outros', 4)
ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name, position = EXCLUDED.position;

COMMIT;
