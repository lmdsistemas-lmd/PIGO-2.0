import unittest
from unittest.mock import patch

from app.services.empresa_service import listar_empresas_erp


class FakeERPQueryService:
    last_sql = ""

    def fetch_all(self, sql):
        self.__class__.last_sql = sql
        return [{
            "EMP_ID": "1",
            "EMP_FANTASIA": "QUATRO PATAS",
            "EMP_RAZAO_SOCIAL": "GABRIEL BOALENTO COLE DE LAIA",
            "EMP_CNPJ": "47645430000124",
        }]


class EmpresaResolutionTests(unittest.TestCase):
    @patch("app.services.empresa_service.ERPQueryService", FakeERPQueryService)
    def test_company_list_uses_synced_schema_and_exposes_erp_id(self):
        companies = listar_empresas_erp()

        self.assertNotIn("EMP_CIDADE", FakeERPQueryService.last_sql)
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["id"], "1")
        self.assertEqual(companies[0]["empresa_id"], "1")
        self.assertEqual(companies[0]["erp_id"], "1")


if __name__ == "__main__":
    unittest.main()
