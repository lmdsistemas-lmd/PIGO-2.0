"""Commercial analysis over PIGO's tenant-scoped ERP mirror."""
from datetime import date, datetime
from decimal import Decimal

from app.repositories.base_repository import BaseRepository
from app.services.base_dashboard_service import BaseDashboardService


def classify_abc(rows):
    """Include the product crossing 80/95% in the preceding class."""
    products = [dict(row, valor=float(row.get("valor") or 0)) for row in rows
                if Decimal(str(row.get("valor") or 0)) > 0]
    products.sort(key=lambda row: (-row["valor"], str(row.get("codigo", ""))))
    total = sum((Decimal(str(row["valor"])) for row in products), Decimal(0))
    cumulative = Decimal(0)
    for row in products:
        before = cumulative / total * 100
        value = Decimal(str(row["valor"]))
        cumulative += value
        row.update(classe="A" if before < 80 else "B" if before < 95 else "C",
                   participacao=float(value / total * 100),
                   acumulado=float(cumulative / total * 100))
    return {"produtos": products, "total": float(total),
            "classes": [{"classe": key, "produtos": sum(p["classe"] == key for p in products),
                         "valor": sum(p["valor"] for p in products if p["classe"] == key)}
                        for key in "ABC"]}


class CommercialAnalyticsService(BaseDashboardService, BaseRepository):
    def sellers(self, empresa_id):
        company, params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        return self._fetch_all(f"""
            SELECT DISTINCT PV.PEV_VENDEDOR AS CODIGO, P.PES_RSOCIAL_NOME AS NOME
            FROM TB_PEDIDO_VENDA PV
            JOIN TB_PESSOA P ON P.PES_ID = PV.PEV_VENDEDOR
            WHERE PV.PEV_VENDEDOR IS NOT NULL {company} ORDER BY 2
        """, params)

    def period(self, period, start=None, end=None):
        if period == "custom" and not (start and end):
            raise ValueError("Informe a data inicial e final.")
        result = self._resolve_period(period, start, end)
        if result.start > result.end:
            raise ValueError("A data inicial deve ser anterior à data final.")
        return result

    def sales(self, empresa_id, start, end, dimension="customer"):
        # Only this fixed registry chooses SQL identifiers.
        fields = {"customer": "PV.PEV_CLIENTE", "seller": "PV.PEV_VENDEDOR"}
        field = fields[dimension]
        company, params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        return self._fetch_all(f"""
            SELECT {field} AS CODIGO,
                   COALESCE(P.PES_RSOCIAL_NOME, 'Não informado') AS NOME,
                   COUNT(*) AS PEDIDOS, SUM(PV.PEV_VALOR_TOTAL) AS VALOR,
                   MAX(CAST(PV.PEV_DT_FATURAMENTO AS DATE)) AS ULTIMA_COMPRA
            FROM TB_PEDIDO_VENDA PV
            LEFT JOIN TB_PESSOA P ON P.PES_ID = {field}
            WHERE CAST(PV.PEV_DT_FATURAMENTO AS DATE) BETWEEN :start_date AND :end_date
              AND COALESCE(PV.PEV_STATUS, '') NOT IN ('C', 'CANCELADO') {company}
            GROUP BY 1, 2 ORDER BY 4 DESC
        """, {**params, "start_date": start, "end_date": end})

    def customers(self, empresa_id, period="month", start=None, end=None):
        dates = self.period(period, start, end)
        company, params = self._empresa_filter("C.CLI_EMPRESA", empresa_id)
        rows = self._fetch_all(f"""
            SELECT C.CLI_PESSOA AS CODIGO, P.PES_RSOCIAL_NOME AS NOME,
                   CI.CID_NOME AS CIDADE, P.PES_DT_CADASTRO AS CADASTRO
            FROM TB_CLIENTE C
            JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA
            LEFT JOIN TB_CIDADE CI ON CI.CID_ID = P.PES_CIDADE
            WHERE 1=1 {company} ORDER BY 2
        """, params)
        sales = self.sales(empresa_id, dates.start, dates.end)
        active = {str(row["CODIGO"]) for row in sales}
        cities = {}
        new = 0
        inactive = []
        for row in rows:
            city = row.get("CIDADE") or "Não informada"
            cities[city] = cities.get(city, 0) + 1
            registered = row.get("CADASTRO")
            if isinstance(registered, datetime):
                registered = registered.date()
            elif registered and not isinstance(registered, date):
                try:
                    registered = date.fromisoformat(str(registered)[:10])
                except ValueError:
                    registered = None
            new += bool(registered and dates.start <= registered <= dates.end)
            if str(row["CODIGO"]) not in active:
                inactive.append({"codigo": row["CODIGO"], "nome": row.get("NOME"), "cidade": city})
        revenue = sum(float(row.get("VALOR") or 0) for row in sales)
        orders = sum(int(row.get("PEDIDOS") or 0) for row in sales)
        return {"periodo": {"inicio": dates.start, "fim": dates.end},
                "resumo": {"clientes": len(rows), "compradores": len(active), "novos": new,
                           "semCompras": len(inactive), "faturamento": revenue,
                           "ticketMedio": revenue / orders if orders else 0},
                "ranking": [{"codigo": row["CODIGO"], "nome": row["NOME"],
                             "pedidos": int(row["PEDIDOS"]), "valor": float(row["VALOR"] or 0)} for row in sales],
                "cidades": [{"nome": key, "clientes": value} for key, value in
                            sorted(cities.items(), key=lambda pair: (-pair[1], pair[0]))],
                "semCompras": inactive}

    def abc(self, empresa_id, period="month", start=None, end=None):
        dates = self.period(period, start, end)
        company, params = self._empresa_filter("I.PEVI_EMPRESA", empresa_id)
        rows = self._fetch_all(f"""
            SELECT I.PEVI_PRODUTO AS CODIGO,
                   COALESCE(P.PRD_DESCRICAO, 'Produto sem descrição') AS PRODUTO,
                   SUM(I.PEVI_QUANTIDADE) AS QUANTIDADE, SUM(I.PEVI_VALOR_TOTAL) AS VALOR
            FROM TB_PEDIDO_VENDA_ITEM I
            JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA AND PV.PEV_EMPRESA = I.PEVI_EMPRESA
            LEFT JOIN TB_PRODUTO P ON P.PRD_ID = I.PEVI_PRODUTO AND P.PRD_EMPRESA = I.PEVI_EMPRESA
            WHERE CAST(PV.PEV_DT_FATURAMENTO AS DATE) BETWEEN :start_date AND :end_date
              AND COALESCE(PV.PEV_STATUS, '') NOT IN ('C', 'CANCELADO') {company}
            GROUP BY 1, 2
        """, {**params, "start_date": dates.start, "end_date": dates.end})
        result = classify_abc([{"codigo": row["CODIGO"], "produto": row["PRODUTO"],
                               "quantidade": float(row["QUANTIDADE"] or 0),
                               "valor": float(row["VALOR"] or 0)} for row in rows])
        return {**result, "periodo": {"inicio": dates.start, "fim": dates.end}}
