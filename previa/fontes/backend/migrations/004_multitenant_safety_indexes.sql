CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_cnpj_normalized
    ON tenants ((regexp_replace(cnpj, '\D', '', 'g')));

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_api_token_not_null
    ON tenants (api_token)
    WHERE api_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_sync_jobs_tenant_id ON sync_jobs (tenant_id);
CREATE INDEX IF NOT EXISTS ix_sync_erp_users_tenant_id ON sync_erp_users (tenant_id);
