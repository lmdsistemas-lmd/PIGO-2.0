from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class LicenseControlRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_tenant(self, external_tenant_id: str, cnpj: str):
        return self.db.execute(
            text(
                """
                SELECT id, external_tenant_id, cnpj, has_pigo_access
                  FROM tenants
                 WHERE external_tenant_id = :external_tenant_id OR cnpj = :cnpj
                 ORDER BY (external_tenant_id = :external_tenant_id) DESC
                 LIMIT 1
                """
            ),
            {"external_tenant_id": external_tenant_id, "cnpj": cnpj},
        ).mappings().first()

    def find_company(self, external_company_id: str, cnpj: str):
        return self.db.execute(
            text(
                """
                SELECT id, external_company_id, cnpj
                  FROM companies
                 WHERE external_company_id = :external_company_id OR cnpj = :cnpj
                 ORDER BY (external_company_id = :external_company_id) DESC
                 LIMIT 1
                """
            ),
            {"external_company_id": external_company_id, "cnpj": cnpj},
        ).mappings().first()

    def upsert_company(self, item: dict[str, Any], existing_id):
        return self.db.execute(
            text(
                """
                INSERT INTO companies (
                    id, external_company_id, name, legal_name, cnpj, status,
                    metadata, updated_at
                ) VALUES (
                    COALESCE(:id, gen_random_uuid()), :external_company_id,
                    :name, :legal_name, :cnpj, :status, CAST(:metadata AS jsonb), now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    external_company_id = EXCLUDED.external_company_id,
                    name = EXCLUDED.name,
                    legal_name = EXCLUDED.legal_name,
                    cnpj = EXCLUDED.cnpj,
                    status = EXCLUDED.status,
                    metadata = companies.metadata || EXCLUDED.metadata,
                    updated_at = now()
                RETURNING id
                """
            ),
            {**item, "id": existing_id},
        ).mappings().one()

    def upsert_tenant(self, item: dict[str, Any], existing_id):
        return self.db.execute(
            text(
                """
                INSERT INTO tenants (
                    id, external_tenant_id, cnpj, razao_social, nome_fantasia,
                    email, status, plano, data_vencimento, license_status,
                    has_pigo_access, license_expires_at, license_control_id,
                    product_slug, environment, license_source_updated_at, updated_at
                ) VALUES (
                    COALESCE(:id, gen_random_uuid()), :external_tenant_id, :cnpj,
                    :razao_social, :nome_fantasia, 'license-control@pigo.local',
                    :access_status, :produto, :validade, :license_status,
                    :has_pigo_access, :validade, :external_tenant_id,
                    :produto, 'production', :source_updated_at, now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    external_tenant_id = EXCLUDED.external_tenant_id,
                    cnpj = EXCLUDED.cnpj,
                    razao_social = EXCLUDED.razao_social,
                    nome_fantasia = EXCLUDED.nome_fantasia,
                    status = EXCLUDED.status,
                    plano = EXCLUDED.plano,
                    data_vencimento = EXCLUDED.data_vencimento,
                    license_status = EXCLUDED.license_status,
                    has_pigo_access = EXCLUDED.has_pigo_access,
                    license_expires_at = EXCLUDED.license_expires_at,
                    license_control_id = EXCLUDED.license_control_id,
                    product_slug = EXCLUDED.product_slug,
                    license_source_updated_at = EXCLUDED.license_source_updated_at,
                    api_token = CASE
                        WHEN EXCLUDED.has_pigo_access AND NOT tenants.api_token_active
                        THEN gen_random_uuid()
                        ELSE tenants.api_token
                    END,
                    api_token_created_at = CASE
                        WHEN EXCLUDED.has_pigo_access AND NOT tenants.api_token_active
                        THEN now()
                        ELSE tenants.api_token_created_at
                    END,
                    api_token_active = EXCLUDED.has_pigo_access,
                    updated_at = now()
                RETURNING id
                """
            ),
            {**item, "id": existing_id},
        ).mappings().one()

    def write_sync_log(self, values: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO license_control_sync_logs (
                    source, ip_address, received, created, updated, disabled,
                    ignored, failed, duration_ms, status, message, error_details
                ) VALUES (
                    'license-control', CAST(:ip_address AS inet), :received,
                    :created, :updated, :disabled, :ignored, :failed,
                    :duration_ms, :status, :message, CAST(:error_details AS jsonb)
                )
                """
            ),
            values,
        )
