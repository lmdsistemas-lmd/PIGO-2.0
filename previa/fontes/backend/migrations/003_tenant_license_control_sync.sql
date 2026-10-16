CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS api_token_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS api_token_created_at timestamptz,
    ADD COLUMN IF NOT EXISTS api_token_last_used_at timestamptz,
    ADD COLUMN IF NOT EXISTS license_status varchar(30) DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS has_pigo_access boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS license_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS license_control_id varchar(100),
    ADD COLUMN IF NOT EXISTS product_slug varchar(100) DEFAULT 'p-i-g-o-dashboard',
    ADD COLUMN IF NOT EXISTS environment varchar(50) DEFAULT 'production';

UPDATE tenants
SET api_token_created_at = COALESCE(api_token_created_at, data_cadastro, now()),
    api_token_active = COALESCE(api_token_active, true),
    product_slug = COALESCE(product_slug, 'p-i-g-o-dashboard'),
    environment = COALESCE(environment, 'production')
WHERE api_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_tenants_license_control_id ON tenants (license_control_id);
CREATE INDEX IF NOT EXISTS ix_tenants_has_pigo_access ON tenants (has_pigo_access);
