CREATE TABLE IF NOT EXISTS pigo_access_profiles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 name varchar(100) NOT NULL, permissions jsonb NOT NULL DEFAULT '[]', created_at timestamptz DEFAULT now(),
 CONSTRAINT uq_pigo_profile_tenant_name UNIQUE(tenant_id,name)
);
CREATE TABLE IF NOT EXISTS pigo_access_users (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 profile_id uuid NOT NULL REFERENCES pigo_access_profiles(id) ON DELETE RESTRICT,
 login varchar(100) NOT NULL, name varchar(150) NOT NULL, password_hash text NOT NULL,
 active boolean NOT NULL DEFAULT true, token_version integer NOT NULL DEFAULT 1, created_at timestamptz DEFAULT now(),
 CONSTRAINT uq_pigo_user_tenant_login UNIQUE(tenant_id,login)
);
