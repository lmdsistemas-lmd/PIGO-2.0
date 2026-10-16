CREATE TABLE IF NOT EXISTS sales_goals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_erp_id integer NOT NULL CHECK (company_erp_id > 0),
    month date NOT NULL CHECK (EXTRACT(DAY FROM month) = 1),
    seller_id integer NOT NULL DEFAULT 0 CHECK (seller_id >= 0),
    target numeric(18,2) NOT NULL CHECK (target > 0),
    updated_by varchar(100) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_sales_goals_scope UNIQUE (tenant_id, company_erp_id, month, seller_id)
);
