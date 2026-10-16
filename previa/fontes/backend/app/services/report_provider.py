from app.services.erp_query_service import ERPQueryService


class ReportProvider:
    def execute(self, sql: str, params: dict) -> list[dict]:
        raise NotImplementedError


class FirebirdReportProvider(ReportProvider):
    """Usa a camada ERP existente, que resolve Firebird ou espelho SaaS por tenant."""

    def __init__(self):
        self.erp = ERPQueryService()

    def execute(self, sql: str, params: dict) -> list[dict]:
        return self.erp.fetch_all(sql, params)
