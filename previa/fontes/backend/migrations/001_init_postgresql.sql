CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    legal_name varchar(255),
    cnpj varchar(14) UNIQUE,
    email varchar(255),
    phone varchar(30),
    status varchar(30) NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(100) NOT NULL UNIQUE,
    slug varchar(100) NOT NULL UNIQUE,
    description text,
    is_system boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module varchar(100) NOT NULL,
    action varchar(100) NOT NULL,
    slug varchar(150) NOT NULL UNIQUE,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    email varchar(255) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    password_hash text NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'active',
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action varchar(100) NOT NULL,
    entity_type varchar(100),
    entity_id varchar(100),
    ip_address inet,
    user_agent text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS application_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    level varchar(30) NOT NULL,
    logger varchar(150),
    message text NOT NULL,
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS error_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    error_type varchar(150),
    message text NOT NULL,
    traceback text,
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key varchar(150) NOT NULL UNIQUE,
    value jsonb NOT NULL DEFAULT '{}'::jsonb,
    description text,
    is_sensitive boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dashboards (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    name varchar(150) NOT NULL,
    slug varchar(150) NOT NULL,
    description text,
    is_default boolean NOT NULL DEFAULT false,
    layout jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_dashboards_company_slug UNIQUE (company_id, slug)
);

CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id uuid NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    widget_type varchar(100) NOT NULL,
    title varchar(150) NOT NULL,
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    position jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    provider varchar(100) NOT NULL,
    name varchar(150) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'inactive',
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    name varchar(150) NOT NULL,
    key_hash text NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'active',
    scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_used_at timestamptz,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(50),
    description text,
    price numeric(10, 2) DEFAULT 0,
    duration integer DEFAULT 30,
    active boolean DEFAULT true,
    reseller_id uuid REFERENCES users(id),
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cnpj varchar(14) UNIQUE NOT NULL,
    razao_social varchar(255) NOT NULL,
    nome_fantasia varchar(255),
    email varchar(255) NOT NULL,
    telefone varchar(20),
    responsavel varchar(255),
    status varchar(20) DEFAULT 'ATIVO',
    plano varchar(50) DEFAULT 'TESTE',
    plan_id uuid REFERENCES plans(id),
    data_vencimento timestamptz NOT NULL,
    data_cadastro timestamptz DEFAULT now(),
    api_token uuid UNIQUE DEFAULT gen_random_uuid(),
    logo_url text,
    last_sync timestamptz,
    updated_at timestamptz DEFAULT now(),
    reseller_id uuid REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS legacy_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    username varchar(100) UNIQUE NOT NULL,
    password text NOT NULL,
    role varchar(50) DEFAULT 'RESELLER',
    name varchar(255),
    logo_url text,
    status varchar(20) DEFAULT 'ATIVO',
    data_vencimento timestamptz,
    created_at timestamptz DEFAULT now(),
    reseller_id uuid REFERENCES legacy_users(id)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    status varchar(20),
    table_name varchar(100),
    records_synced integer DEFAULT 0,
    error_message text,
    started_at timestamptz DEFAULT now(),
    finished_at timestamptz
);

CREATE TABLE IF NOT EXISTS sync_vendas_diarias (
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    data_venda timestamptz,
    faturamento numeric(18, 2) DEFAULT 0,
    pedidos integer DEFAULT 0,
    updated_at timestamptz DEFAULT now(),
    PRIMARY KEY (tenant_id, data_venda)
);

CREATE TABLE IF NOT EXISTS sync_financeiro_stats (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    inadimplencia_total numeric(18, 2) DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_erp_users (
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    usu_login varchar(100),
    usu_nome varchar(255),
    usu_senha varchar(255),
    usu_administrador varchar(1),
    updated_at timestamptz DEFAULT now(),
    PRIMARY KEY (tenant_id, usu_login)
);

CREATE TABLE IF NOT EXISTS rh_departamentos (
    id serial PRIMARY KEY,
    nome varchar(100) NOT NULL,
    descricao varchar(255)
);

CREATE TABLE IF NOT EXISTS rh_cargos (
    id serial PRIMARY KEY,
    nome varchar(100) NOT NULL,
    descricao varchar(255)
);

CREATE TABLE IF NOT EXISTS rh_funcionarios (
    id serial PRIMARY KEY,
    col_pessoa integer NOT NULL UNIQUE,
    departamento_id integer NOT NULL REFERENCES rh_departamentos(id),
    cargo_id integer REFERENCES rh_cargos(id)
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (lower(email));
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
