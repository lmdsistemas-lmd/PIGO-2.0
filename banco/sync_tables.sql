-- Tabelas para armazenamento de dados sincronizados do ERP

-- 1. Vendas Diárias (Agregadas)
CREATE TABLE IF NOT EXISTS sync_vendas_diarias (
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    data_venda DATE NOT NULL,
    faturamento DECIMAL(18,2) DEFAULT 0,
    pedidos INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, data_venda)
);

-- 2. Estatísticas Financeiras
CREATE TABLE IF NOT EXISTS sync_financeiro_stats (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    inadimplencia_total DECIMAL(18,2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Usuários do ERP
CREATE TABLE IF NOT EXISTS sync_erp_users (
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    usu_login VARCHAR(100) NOT NULL,
    usu_nome VARCHAR(255),
    usu_senha VARCHAR(255),
    usu_administrador VARCHAR(10),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, usu_login)
);

-- Índices para facilitar consultas do Dashboard
CREATE INDEX IF NOT EXISTS idx_sync_vendas_date ON sync_vendas_diarias(data_venda);
CREATE INDEX IF NOT EXISTS idx_sync_vendas_tenant ON sync_vendas_diarias(tenant_id);
