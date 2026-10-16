from __future__ import annotations
from typing import TYPE_CHECKING
from app.repositories.base_dashboard_repository import BaseDashboardRepository

if TYPE_CHECKING:
    from app.services.erp_query_service import DateRange

class DashboardVendasRepository(BaseDashboardRepository):
    def get_resumo_kpis(self, date_range: DateRange, empresa_id: int | None) -> dict:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        # Keep each query flat so the SaaS adapter can apply tenant guards to
        # its actual root. Aggregating orders independently also avoids counting
        # their totals once per item or merging equal IDs in different companies.
        orders_sql = f"""
            SELECT CAST(SUM(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS FATURAMENTO,
                   COUNT(*) AS PEDIDOS
            FROM TB_PEDIDO_VENDA PV
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
        """
        items_sql = f"""
            SELECT SUM(I.PEVI_QUANTIDADE) AS ITENS,
                   SUM(I.PEVI_QUANTIDADE * I.PEVI_VALOR_CUSTO_UNITARIO) AS CUSTO
            FROM TB_PEDIDO_VENDA_ITEM I
            INNER JOIN TB_PEDIDO_VENDA PV
                ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA
               AND PV.PEV_EMPRESA = I.PEVI_EMPRESA
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        row = self._fetch_one(orders_sql, dict(params)) or {}
        items = self._fetch_one(items_sql, dict(params)) or {}
            
        return {
            "faturamento": self._safe_float(row.get("FATURAMENTO")),
            "pedidos": self._safe_int(row.get("PEDIDOS")),
            "itens": self._safe_float(items.get("ITENS")),
            "custo": self._safe_float(items.get("CUSTO"))
        }

    def get_faturamento_total(self, date_range: DateRange, empresa_id: int | None) -> float:
        res = self.get_resumo_kpis(date_range, empresa_id)
        return res["faturamento"]

    def get_total_pedidos(self, date_range: DateRange, empresa_id: int | None) -> int:
        res = self.get_resumo_kpis(date_range, empresa_id)
        return res["pedidos"]

    def get_total_itens(self, date_range: DateRange, empresa_id: int | None) -> float:
        res = self.get_resumo_kpis(date_range, empresa_id)
        return res["itens"]

    def get_custo_total(self, date_range: DateRange, empresa_id: int | None) -> float:
        res = self.get_resumo_kpis(date_range, empresa_id)
        return res["custo"]

    def get_top_clientes(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME) AS NOME,
                COUNT(PV.PEV_ID) AS PEDIDOS,
                CAST(SUM(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_PESSOA P ON P.PES_ID = PV.PEV_CLIENTE
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 3 DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"nome": r.get("NOME"), "pedidos": self._safe_int(r.get("PEDIDOS")), "valor": self._safe_float(r.get("VALOR"))} for r in rows]

    def get_top_produtos(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                PR.PRD_DESCRICAO AS PRODUTO,
                SUM(I.pevi_quantidade) AS QUANTIDADE,
                CAST(SUM(I.PEVI_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA_ITEM I
            INNER JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA
            INNER JOIN TB_PRODUTO PR ON PR.PRD_ID = I.PEVI_PRODUTO
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 3 DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"produto": r.get("PRODUTO"), "quantidade": self._safe_float(r.get("QUANTIDADE")), "valor": self._safe_float(r.get("VALOR"))} for r in rows]

    def get_vendas_por_cidade(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        city_columns=self.erp.table_columns('TB_CIDADE')
        code='CID.CID_CODIGO_MUNICIPIO' if 'CID_CODIGO_MUNICIPIO' in city_columns else 'NULL'
        group_code=', CID.CID_CODIGO_MUNICIPIO' if 'CID_CODIGO_MUNICIPIO' in city_columns else ''
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                CID.CID_NOME AS CIDADE, {code} AS CODIGO_IBGE,
                COUNT(PV.PEV_ID) AS QTD
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_CLIENTE C ON C.CLI_PESSOA = PV.PEV_CLIENTE
            INNER JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA
            INNER JOIN TB_CIDADE CID ON CID.CID_ID = P.PES_CIDADE
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY CID.CID_NOME{group_code}
            ORDER BY QTD DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"codigo_ibge":str(r["CODIGO_IBGE"]).strip() if r.get("CODIGO_IBGE") else None,"cidade": r.get("CIDADE"), "quantidade": self._safe_int(r.get("QTD"))} for r in rows]

    def get_vendas_por_vendedor(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                COALESCE(P.PES_RSOCIAL_NOME, 'NAO INFORMADO') AS VENDEDOR,
                COUNT(PV.PEV_ID) AS PEDIDOS,
                CAST(SUM(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA PV
            LEFT JOIN TB_VENDEDOR V ON V.vdr_pessoa = PV.PEV_VENDEDOR
            LEFT JOIN TB_PESSOA P ON P.PES_ID = V.vdr_pessoa
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 3 DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"vendedor": r.get("VENDEDOR"), "pedidos": self._safe_int(r.get("PEDIDOS")), "valor": self._safe_float(r.get("VALOR"))} for r in rows]

    def get_vendas_por_grupo(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                G.PGRU_DESCRICAO AS GRUPO,
                CAST(SUM(I.PEVI_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA_ITEM I
            INNER JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA
            INNER JOIN TB_PRODUTO PR ON PR.PRD_ID = I.PEVI_PRODUTO
            INNER JOIN TB_PROD_GRUPO G ON G.PGRU_ID = PR.PRD_GRUPO
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 2 DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"label": r.get("GRUPO"), "valor": self._safe_float(r.get("VALOR"))} for r in rows]

    def get_vendas_por_marca(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT FIRST 10
                M.PMAR_DESCRICAO AS MARCA,
                CAST(SUM(I.PEVI_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA_ITEM I
            INNER JOIN TB_PEDIDO_VENDA PV ON PV.PEV_ID = I.PEVI_PEDIDO_VENDA
            INNER JOIN TB_PRODUTO PR ON PR.PRD_ID = I.PEVI_PRODUTO
            INNER JOIN TB_PROD_MARCA M ON M.PMAR_ID = PR.PRD_MARCA
            WHERE PV.PEV_DT_FATURAMENTO BETWEEN :start_date AND :end_date
              AND PV.PEV_STATUS <> 'C'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 2 DESC
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"label": r.get("MARCA"), "valor": self._safe_float(r.get("VALOR"))} for r in rows]

    def get_media_por_faixa_horaria(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT
                EXTRACT(HOUR FROM PV.PEV_DT_LANCAMENTO) AS HORA,
                CAST(AVG(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR,
                COUNT(PV.PEV_ID) AS PEDIDOS
            FROM TB_PEDIDO_VENDA PV
            WHERE PV.PEV_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              AND COALESCE(PV.PEV_STATUS, '') <> 'CANCELADO'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 1
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        return [{"faixa": f"{int(r.get('HORA')):02d}h", "valor": self._safe_float(r.get("VALOR")), "pedidos": self._safe_int(r.get("PEDIDOS"))} for r in rows]

    def get_media_por_dia_semana(self, date_range: DateRange, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        # 1=Dom, 7=Sab no Firebird
        sql = f"""
            SELECT
                EXTRACT(WEEKDAY FROM PV.PEV_DT_LANCAMENTO) + 1 AS DIA_NUM,
                CAST(AVG(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR,
                COUNT(PV.PEV_ID) AS PEDIDOS
            FROM TB_PEDIDO_VENDA PV
            WHERE PV.PEV_DT_LANCAMENTO BETWEEN :start_date AND :end_date
              AND COALESCE(PV.PEV_STATUS, '') <> 'CANCELADO'
              {empresa_sql}
            GROUP BY 1
            ORDER BY 1
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        rows = self._fetch_all(sql, params)
        labels = {1: "Dom", 2: "Seg", 3: "Ter", 4: "Qua", 5: "Qui", 6: "Sex", 7: "Sab"}
        return [{"dia": labels.get(self._safe_int(r.get("DIA_NUM")), str(r.get("DIA_NUM"))), "valor": self._safe_float(r.get("VALOR")), "pedidos": self._safe_int(r.get("PEDIDOS"))} for r in rows]

    def get_historico_vendas(self, empresa_id: int | None) -> list[dict]:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        sql = f"""
            SELECT
                EXTRACT(YEAR FROM PV.PEV_DT_LANCAMENTO) AS ANO,
                EXTRACT(MONTH FROM PV.PEV_DT_LANCAMENTO) AS MES_NUM,
                CAST(SUM(PV.PEV_VALOR_TOTAL) AS NUMERIC(18,2)) AS VALOR,
                COUNT(PV.PEV_ID) AS PEDIDOS
            FROM TB_PEDIDO_VENDA PV
            WHERE PV.PEV_DT_LANCAMENTO >= CURRENT_DATE - INTERVAL '2 years'
              AND COALESCE(PV.PEV_STATUS, '') <> 'CANCELADO'
              {empresa_sql}
            GROUP BY 1, 2
            ORDER BY 1 DESC, 2 ASC
        """
        rows = self._fetch_all(sql, empresa_params)
        labels = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
        return [{"ano": int(r.get("ANO")), "label": labels.get(int(r.get("MES_NUM")), str(r.get("MES_NUM"))), "valor": self._safe_float(r.get("VALOR")), "pedidos": self._safe_int(r.get("PEDIDOS"))} for r in rows]

    def get_detalhes_pedidos(self, date_range: DateRange, empresa_id: int | None, page: int = 1, page_size: int = 10, status: str | None = None) -> dict:
        empresa_sql, empresa_params = self._empresa_filter("PV.PEV_EMPRESA", empresa_id)
        
        status_sql = ""
        status_params = {}
        if status and status != "TODOS":
            # Mapeamento: F=Faturados, A=Aberto, O=Orcamento, C=Cancelado
            mapeamento = {
                "ABERTO": "A",
                "FATURADO": "F",
                "CANCELADO": "C",
                "ORCAMENTO": "O"
            }
            status_db = mapeamento.get(status.upper(), status.upper())
            status_sql = " AND PV.PEV_STATUS = :status "
            status_params = {"status": status_db}

        offset = (page - 1) * page_size
        
        print(f"[DEBUG] Filtrando pedidos - Status: {status} (DB: {status_params.get('status')}), Empresa: {empresa_id}")

        count_sql = f"""
            SELECT COUNT(*) AS TOTAL 
            FROM TB_PEDIDO_VENDA PV 
            WHERE PV.PEV_DT_EMISSAO BETWEEN :start_date AND :end_date 
              {status_sql}
              {empresa_sql}
        """
        
        sql = f"""
            SELECT
                PV.PEV_ID AS ID,
                PV.PEV_DT_EMISSAO AS DATA,
                COALESCE(NULLIF(TRIM(P.PES_FANTASIA_APELIDO), ''), P.PES_RSOCIAL_NOME) AS CLIENTE,
                CAST(COALESCE(PV.PEV_VALOR_TOTAL, 0) AS NUMERIC(18,2)) AS VALOR,
                CASE PV.PEV_STATUS
                    WHEN 'A' THEN 'ABERTO'
                    WHEN 'F' THEN 'FATURADO'
                    WHEN 'C' THEN 'CANCELADO'
                    WHEN 'O' THEN 'ORCAMENTO'
                    ELSE COALESCE(PV.PEV_STATUS, 'ABERTO')
                END AS STATUS
            FROM TB_PEDIDO_VENDA PV
            INNER JOIN TB_CLIENTE C ON C.CLI_PESSOA = PV.PEV_CLIENTE
            INNER JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA
            WHERE PV.PEV_DT_EMISSAO BETWEEN :start_date AND :end_date
              {status_sql}
              {empresa_sql}
            ORDER BY PV.PEV_DT_EMISSAO DESC
            ROWS {offset + 1} TO {offset + page_size}
        """
        
        params = {
            "start_date": date_range.start, 
            "end_date": date_range.end, 
            **empresa_params,
            **status_params
        }
        
        total_row = self._fetch_one(count_sql, params)
        total = self._safe_int(total_row.get("TOTAL")) if total_row else 0
        
        rows = self._fetch_all(sql, params)
        data = [{"id": r.get("ID"), "data": self._iso_date(r.get("DATA")), "cliente": r.get("CLIENTE"), "valor": self._safe_float(r.get("VALOR")), "status": r.get("STATUS")} for r in rows]
        return {"total": total, "data": data}

    def get_detalhes_novos_clientes(self, date_range: DateRange, empresa_id: int | None, page: int = 1, page_size: int = 10) -> dict:
        empresa_sql, empresa_params = self._empresa_filter("C.CLI_EMPRESA", empresa_id)
        offset = (page - 1) * page_size
        count_sql = f"SELECT COUNT(*) AS TOTAL FROM TB_CLIENTE C INNER JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA WHERE P.PES_DT_CADASTRO BETWEEN :start_date AND :end_date {empresa_sql}"
        sql = f"""
            SELECT
                P.PES_ID AS ID,
                P.PES_RSOCIAL_NOME AS NOME,
                P.PES_FANTASIA_APELIDO AS FANTASIA,
                P.PES_DT_CADASTRO AS DATA_CADASTRO
            FROM TB_CLIENTE C
            INNER JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA
            WHERE P.PES_DT_CADASTRO BETWEEN :start_date AND :end_date
              {empresa_sql}
            ORDER BY P.PES_DT_CADASTRO DESC
            ROWS {offset + 1} TO {offset + page_size}
        """
        params = {"start_date": date_range.start, "end_date": date_range.end, **empresa_params}
        total = self._safe_int(self._fetch_one(count_sql, params).get("TOTAL"))
        rows = self._fetch_all(sql, params)
        data = [{"id": r.get("ID"), "nome": r.get("NOME"), "fantasia": r.get("FANTASIA"), "data_cadastro": self._iso_date(r.get("DATA_CADASTRO"))} for r in rows]
        return {"total": total, "data": data}

    def get_pedido_detalhes_completos(self, pedido_id: int, empresa_id: int) -> dict:
        # 1. Buscar Itens do Pedido
        sql_itens = """
            SELECT 
                PI.PEVI_PRODUTO AS ID,
                PR.PRD_DESCRICAO AS DESCRICAO,
                PI.PEVI_QUANTIDADE AS QTD,
                CAST(PI.PEVI_VALOR_UNITARIO AS NUMERIC(18,2)) AS UNITARIO,
                CAST(PI.PEVI_VALOR_TOTAL AS NUMERIC(18,2)) AS TOTAL
            FROM TB_PEDIDO_VENDA_ITEM PI
            LEFT JOIN TB_PRODUTO PR ON PI.PEVI_PRODUTO = PR.PRD_ID
            WHERE PI.PEVI_PEDIDO_VENDA = :pedido_id
              AND PI.PEVI_EMPRESA = :empresa_id
        """
        
        # 2. Buscar Financeiro (Formas de Pagamento)
        sql_fin = """
            SELECT 
                E.ESP_DESCRICAO AS FORMA,
                CAST(PF.PEVF_VALOR AS NUMERIC(18,2)) AS VALOR
            FROM TB_PEDIDO_VENDA_FIN PF
            LEFT JOIN TB_ESPECIE_MOEDA E ON PF.PEVF_ESPECIE_MOEDA = E.ESP_ID
            WHERE PF.PEVF_PEDIDO_VENDA = :pedido_id
              AND PF.PEVF_EMPRESA = :empresa_id
        """
        
        # 3. Buscar Cabeçalho resumido
        sql_head = """
            SELECT 
                P.PEV_ID AS ID,
                C.PES_RSOCIAL_NOME AS CLIENTE,
                V.PES_RSOCIAL_NOME AS VENDEDOR,
                P.PEV_DT_EMISSAO AS DATA,
                CAST(P.PEV_VALOR_TOTAL AS NUMERIC(18,2)) AS TOTAL,
                P.PEV_STATUS AS STATUS
            FROM TB_PEDIDO_VENDA P
            LEFT JOIN TB_PESSOA C ON P.PEV_CLIENTE = C.PES_ID
            LEFT JOIN TB_PESSOA V ON P.PEV_VENDEDOR = V.PES_ID
            WHERE P.PEV_ID = :pedido_id 
              AND P.PEV_EMPRESA = :empresa_id
        """

        params = {"pedido_id": pedido_id, "empresa_id": empresa_id}
        
        itens = self._fetch_all(sql_itens, params)
        fin = self._fetch_all(sql_fin, params)
        head = self._fetch_one(sql_head, params)

        return {
            "cabecalho": head,
            "itens": itens,
            "pagamentos": fin
        }
