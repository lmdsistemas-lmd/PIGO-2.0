from __future__ import annotations
from app.repositories.base_dashboard_repository import BaseDashboardRepository
from app.services.base_dashboard_service import DateRange
from typing import Any

class DashboardConsolidadoRepository(BaseDashboardRepository):
    def get_resumo_consolidado(self, date_range: DateRange) -> list[dict[str, Any]]:
        sql = """
            SELECT
                E.EMP_FANTASIA AS FILIAL,
                PV.PEV_EMPRESA AS EMPRESA_ID,
                COALESCE(SUM(CAST(COALESCE(PV.PEV_VALOR_TOTAL, 0) AS NUMERIC(18,2))), 0) AS FATURAMENTO,
                COUNT(*) AS VENDAS
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_EMPRESA E ON E.EMP_ID = PV.PEV_EMPRESA
            WHERE PV.PEV_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'CANCELADO'
            GROUP BY 1, 2
            ORDER BY FATURAMENTO DESC
        """
        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
        }
        rows = self._fetch_all(sql, params)
        
        total_rede = sum(self._safe_float(row.get("FATURAMENTO")) for row in rows)
        
        result = []
        for row in rows:
            faturamento = self._safe_float(row.get("FATURAMENTO"))
            vendas = self._safe_int(row.get("VENDAS"))
            participacao = (faturamento / total_rede * 100) if total_rede > 0 else 0
            ticket_medio = (faturamento / vendas) if vendas > 0 else 0
            
            result.append({
                "id": row.get("EMPRESA_ID"),
                "nome": (row.get("FILIAL") or f"Filial {row.get('EMPRESA_ID')}").strip(),
                "faturamento": faturamento,
                "participacao": participacao,
                "vendas": vendas,
                "ticket_medio": round(ticket_medio, 2),
            })
            
        return result

    def get_vendas_por_dia_semana(self, date_range: DateRange) -> list[dict[str, Any]]:
        sql = """
            SELECT
                EXTRACT(WEEKDAY FROM PV.PEV_DT_LANCAMENTO) AS DIA_NUM,
                E.EMP_FANTASIA AS FILIAL,
                COALESCE(SUM(CAST(COALESCE(PV.PEV_VALOR_TOTAL, 0) AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_EMPRESA E ON E.EMP_ID = PV.PEV_EMPRESA
            WHERE PV.PEV_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'CANCELADO'
            GROUP BY 1, 2
            ORDER BY 1, 2
        """
        params = {
            "start_date": date_range.start,
            "end_date": date_range.end,
        }
        rows = self._fetch_all(sql, params)
        
        dias_labels = {0: "Dom", 1: "Seg", 2: "Ter", 3: "Qua", 4: "Qui", 5: "Sex", 6: "Sab"}
        
        # Estruturar para Recharts (um objeto por dia com chaves de filiais)
        temp_data = {}
        filiais = set()
        
        for row in rows:
            dia_num = self._safe_int(row.get("DIA_NUM"))
            dia_label = dias_labels.get(dia_num, str(dia_num))
            filial = row.get("FILIAL") or "Desconhecida"
            valor = self._safe_float(row.get("TOTAL"))
            
            filiais.add(filial)
            
            if dia_label not in temp_data:
                temp_data[dia_label] = {"name": dia_label}
            
            temp_data[dia_label][filial] = valor
            
        return [temp_data[d] for d in dias_labels.values() if d in temp_data]

    def get_vendas_mensais(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                EXTRACT(YEAR FROM PV.PEV_DT_LANCAMENTO) AS ANO,
                EXTRACT(MONTH FROM PV.PEV_DT_LANCAMENTO) AS MES,
                E.EMP_FANTASIA AS FILIAL,
                COALESCE(SUM(CAST(COALESCE(PV.PEV_VALOR_TOTAL, 0) AS NUMERIC(18,2))), 0) AS TOTAL
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_EMPRESA E ON E.EMP_ID = PV.PEV_EMPRESA
            WHERE PV.PEV_DT_LANCAMENTO >= DATEADD(-6 MONTH TO CURRENT_DATE)
              AND PV.PEV_STATUS <> 'CANCELADO'
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
        """
        rows = self._fetch_all(sql, {})
        
        temp_data = {}
        for row in rows:
            mes_num = self._safe_int(row.get("MES"))
            ano = self._safe_int(row.get("ANO"))
            label = f"{self._month_label(mes_num)}/{ano}"
            filial = row.get("FILIAL") or "Desconhecida"
            valor = self._safe_float(row.get("TOTAL"))
            
            if label not in temp_data:
                temp_data[label] = {"name": label}
            
            temp_data[label][filial] = valor
            
        return list(temp_data.values())
