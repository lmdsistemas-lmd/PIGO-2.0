from __future__ import annotations

from contextvars import copy_context

from app.repositories.dashboard_vendas_repository import DashboardVendasRepository
from app.services.base_dashboard_service import BaseDashboardService


class DashboardVendasService(BaseDashboardService):
    def __init__(self) -> None:
        self.repository = DashboardVendasRepository()

    def get_dashboard_vendas(
        self,
        period: str,
        start: str | None,
        end: str | None,
        empresa_id: int | None = None,
        status: str | None = None,
    ) -> dict:
        date_range = self._resolve_period(period, start, end)
        self.repository.set_status_filter(status)
        from concurrent.futures import ThreadPoolExecutor

        # Executa todas as consultas do dashboard em paralelo para máxima velocidade
        with ThreadPoolExecutor(max_workers=10) as executor:
            def submit_with_context(function, *args):
                context = copy_context()
                return executor.submit(context.run, function, *args)

            f_resumo = submit_with_context(self.repository.get_resumo_kpis, date_range, empresa_id)
            f_historico = submit_with_context(
                self.repository.get_historico_vendas, date_range, empresa_id
            )
            f_clientes = submit_with_context(self.repository.get_top_clientes, date_range, empresa_id)
            f_novos_clientes = submit_with_context(
                self.repository.get_novos_clientes_count, date_range, empresa_id
            )
            f_produtos = submit_with_context(self.repository.get_top_produtos, date_range, empresa_id)
            f_cidades = submit_with_context(self.repository.get_vendas_por_cidade, date_range, empresa_id)
            f_vendedores = submit_with_context(self.repository.get_vendas_por_vendedor, date_range, empresa_id)
            f_grupos = submit_with_context(self.repository.get_vendas_por_grupo, date_range, empresa_id)
            f_marcas = submit_with_context(self.repository.get_vendas_por_marca, date_range, empresa_id)
            f_horas = submit_with_context(self.repository.get_media_por_faixa_horaria, date_range, empresa_id)
            f_dias = submit_with_context(self.repository.get_media_por_dia_semana, date_range, empresa_id)
            f_variation = submit_with_context(self._get_faturamento_variation, date_range, empresa_id)

            # Coleta os resultados
            resumo = f_resumo.result()
            faturamento = resumo["faturamento"]
            pedidos = resumo["pedidos"]
            itens = resumo["itens"]
            custo = resumo["custo"]
            
        ticket_medio = faturamento / pedidos if pedidos > 0 else 0
        itens_por_venda = itens / pedidos if pedidos > 0 else 0
        lucro_bruto = faturamento - custo
        margem_lucro = (lucro_bruto / faturamento * 100) if faturamento > 0 else 0
        markup = (lucro_bruto / custo * 100) if custo > 0 else 0

        return {
            "resumo": {
                "faturamento": faturamento,
                "pedidos": pedidos,
                "novosClientes": f_novos_clientes.result(),
                "ticketMedio": round(ticket_medio, 2),
                "itensPorVenda": round(itens_por_venda, 2),
                "custoTotal": custo,
                "lucroBruto": lucro_bruto,
                "margemLucro": round(margem_lucro, 2),
                "markup": round(markup, 2),
                "lucratividade": round(margem_lucro, 2),
                "variation": f_variation.result(),
            },
            "historico": f_historico.result(),
            "topClientes": f_clientes.result(),
            "topProdutos": f_produtos.result(),
            "vendasPorCidade": f_cidades.result(),
            "vendasPorVendedor": f_vendedores.result(),
            "vendasPorGrupo": f_grupos.result(),
            "vendasPorMarca": f_marcas.result(),
            "mediaPorFaixaHoraria": f_horas.result(),
            "mediaPorDiaSemana": f_dias.result(),
        }

    def _apply_sync_data(self, sync_data: dict, period: str, date_range: DateRange) -> dict:
        """
        Mapeia os dados crus do JSON de sincronismo para o formato do Dashboard de Vendas,
        respeitando o filtro de datas.
        """
        vendas_diarias = sync_data.get("vendas_diarias", [])
        
        faturamento = 0.0
        pedidos = 0
        itens = 0.0
        custo = 0.0
        
        # Filtra os dados de acordo com o date_range selecionado no dashboard
        for dia in vendas_diarias:
            try:
                from datetime import datetime
                data_venda = datetime.strptime(dia["data"], "%Y-%m-%d").date()
                if date_range.start <= data_venda <= date_range.end:
                    faturamento += dia.get("faturamento", 0)
                    pedidos += dia.get("pedidos", 0)
                    itens += dia.get("itens", 0)
                    custo += dia.get("custo", 0)
            except Exception:
                pass
        
        ticket_medio = faturamento / pedidos if pedidos > 0 else 0
        itens_por_venda = itens / pedidos if pedidos > 0 else 0
        lucro_bruto = faturamento - custo
        
        margem_lucro = (lucro_bruto / faturamento * 100) if faturamento > 0 else 0
        markup = (lucro_bruto / custo * 100) if custo > 0 else 0
        lucratividade = margem_lucro

        return {
            "resumo": {
                "faturamento": faturamento,
                "pedidos": pedidos,
                "ticketMedio": round(ticket_medio, 2),
                "itensPorVenda": round(itens_por_venda, 2),
                "custoTotal": custo,
                "lucroBruto": lucro_bruto,
                "margemLucro": round(margem_lucro, 2),
                "markup": round(markup, 2),
                "lucratividade": round(lucratividade, 2),
                "variation": "Modo Sincronizado",
            },
            "historico": [],
            "topClientes": [],
            "topProdutos": [],
            "vendasPorCidade": [],
            "vendasPorVendedor": [],
            "vendasPorGrupo": [],
            "vendasPorMarca": [],
            "mediaPorFaixaHoraria": [],
            "mediaPorDiaSemana": [],
            "is_remote": True
        }

    def _get_faturamento_variation(self, date_range, empresa_id: int | None) -> str:
        previous_period = self._previous_period(date_range)
        current_value = self.repository.get_faturamento_total(date_range, empresa_id)
        previous_value = self.repository.get_faturamento_total(previous_period, empresa_id)
        return self._format_variation(current_value, previous_value)

    def get_detalhes_pedidos(self, period: str, start: str | None, end: str | None, empresa_id: int | None = None, page: int = 1, page_size: int = 10, status: str | None = None) -> dict:
        date_range = self._resolve_period(period, start, end)
        return self.repository.get_detalhes_pedidos(date_range, empresa_id, page, page_size, status)

    def get_detalhes_novos_clientes(self, period: str, start: str | None, end: str | None, empresa_id: int | None = None, page: int = 1, page_size: int = 10) -> dict:
        date_range = self._resolve_period(period, start, end)
        return self.repository.get_detalhes_novos_clientes(date_range, empresa_id, page, page_size)

    def get_pedido_detalhes_completos(self, pedido_id: int, empresa_id: int) -> dict:
        return self.repository.get_pedido_detalhes_completos(pedido_id, empresa_id)
