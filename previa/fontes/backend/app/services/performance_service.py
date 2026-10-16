from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.performance_repository import PerformanceRepository


def obter_data_hoje_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def obter_primeiro_dia_mes_atual_iso() -> str:
    hoje = datetime.now()
    return hoje.replace(day=1).strftime("%Y-%m-%d")


def formatar_dia_iso_para_br(data_iso: str) -> str:
    try:
        data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
        return data_obj.strftime("%d/%m")
    except Exception:
        return data_iso


def normalizar_data_para_iso(valor: str) -> str:
    texto = str(valor or "").strip()

    if not texto:
        return ""

    if "/" in texto:
        try:
            return datetime.strptime(texto, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return texto

    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return texto


def normalizar_periodo(data_inicial: str, data_final: str) -> tuple[str, str]:
    data_inicial_limpa = normalizar_data_para_iso(data_inicial)
    data_final_limpa = normalizar_data_para_iso(data_final)

    if not data_inicial_limpa and not data_final_limpa:
        return obter_primeiro_dia_mes_atual_iso(), obter_data_hoje_iso()

    if data_inicial_limpa and not data_final_limpa:
        return data_inicial_limpa, obter_data_hoje_iso()

    if not data_inicial_limpa and data_final_limpa:
        ano_mes = data_final_limpa[:7]
        return f"{ano_mes}-01", data_final_limpa

    return data_inicial_limpa, data_final_limpa


def montar_filtro_base(
    acao: str,
    data_inicial: str,
    data_final: str,
) -> tuple[str, dict]:
    filtros = ["1 = 1"]
    params: dict = {}

    acao_limpa = (acao or "").strip().upper()
    if acao_limpa:
        filtros.append("UPPER(COALESCE(a.AUD_ACAO, '')) = :acao")
        params["acao"] = acao_limpa

    if data_inicial:
        filtros.append(
            "CAST(a.AUD_DT_LANCAMENTO AS DATE) >= CAST(:data_inicial AS DATE)"
        )
        params["data_inicial"] = data_inicial

    if data_final:
        filtros.append(
            "CAST(a.AUD_DT_LANCAMENTO AS DATE) <= CAST(:data_final AS DATE)"
        )
        params["data_final"] = data_final

    return " AND ".join(filtros), params


def montar_filtro_detalhado(
    tipo: str,
    usuario: str,
    tabela: str,
    data_inicial: str,
    data_final: str,
) -> tuple[str, dict]:
    filtros, params = montar_filtro_base(
        acao=tipo,
        data_inicial=data_inicial,
        data_final=data_final,
    )

    lista_filtros = [filtros]

    usuario_limpo = (usuario or "").strip()
    if usuario_limpo:
        lista_filtros.append("""
            UPPER(
                COALESCE(
                    TRIM(u.USU_NOME) || ' (' || TRIM(u.USU_LOGIN) || ')',
                    TRIM(u.USU_LOGIN),
                    CAST(a.AUD_USUARIO AS VARCHAR(20))
                )
            ) = :usuario
        """)
        params["usuario"] = usuario_limpo.upper()

    tabela_limpa = (tabela or "").strip()
    if tabela_limpa and tabela_limpa.upper() != "TODAS":
        lista_filtros.append("""
            UPPER(COALESCE(TRIM(a.AUD_TABELA_DESC), TRIM(a.AUD_TABELA), '')) = :tabela
        """)
        params["tabela"] = tabela_limpa.upper()

    return " AND ".join(lista_filtros), params


class PerformanceService:
    def __init__(self, erp_db: Session):
        self.erp_db = erp_db
        self.repository = PerformanceRepository(erp_db)

    def obter_visao_geral(
        self,
        acao: str = "",
        data_inicial: str = "",
        data_final: str = "",
    ):
        data_inicial_normalizada, data_final_normalizada = normalizar_periodo(
            data_inicial,
            data_final,
        )

        where_sql, params = montar_filtro_base(
            acao=acao,
            data_inicial=data_inicial_normalizada,
            data_final=data_final_normalizada,
        )

        resumo_row = self.repository.buscar_resumo(where_sql, params)

        total = int(resumo_row[0] or 0) if resumo_row else 0
        inclusoes = int(resumo_row[1] or 0) if resumo_row else 0
        alteracoes = int(resumo_row[2] or 0) if resumo_row else 0
        exclusoes = int(resumo_row[3] or 0) if resumo_row else 0
        cancelamentos = int(resumo_row[4] or 0) if resumo_row else 0

        rows_dias = self.repository.buscar_acoes_por_dia(where_sql, params)
        acoes_por_dia = []

        for row in rows_dias:
            data_ref = str(row[0]) if row[0] else ""
            acoes_por_dia.append(
                {
                    "dia": formatar_dia_iso_para_br(data_ref),
                    "data_iso": data_ref,
                    "total": int(row[1] or 0),
                }
            )

        dias_com_atividade = len(acoes_por_dia)
        media_por_dia = round(total / dias_com_atividade, 1) if dias_com_atividade > 0 else 0

        rows_horas = self.repository.buscar_acoes_por_horario(where_sql, params)
        acoes_por_horario = []
        hora_mais_ativa = "-"
        maior_total_hora = -1

        for row in rows_horas:
            hora_num = int(row[0]) if row[0] is not None else None
            total_hora = int(row[1] or 0)

            if hora_num is None:
                continue

            hora_texto = f"{hora_num:02d}h"
            acoes_por_horario.append(
                {
                    "hora": hora_texto,
                    "total": total_hora,
                }
            )

            if total_hora > maior_total_hora:
                maior_total_hora = total_hora
                hora_mais_ativa = hora_texto

        row_tabela_mais = self.repository.buscar_tabela_mais_movimentada(where_sql, params)
        tabela_mais_movimentada = (
            str(row_tabela_mais[0]).strip()
            if row_tabela_mais and row_tabela_mais[0]
            else "-"
        )

        rows_funcionarios = self.repository.buscar_resumo_por_funcionario(where_sql, params)

        ranking_funcionarios = []
        tabela_resumo = []

        for row in rows_funcionarios:
            funcionario_nome = str(row[0]).strip() if row[0] else "Sem nome"
            usuario_login = str(row[1]).strip() if row[1] else ""
            total_func = int(row[2] or 0)
            inclusoes_func = int(row[3] or 0)
            alteracoes_func = int(row[4] or 0)
            exclusoes_func = int(row[5] or 0)
            cancelamentos_func = int(row[6] or 0)

            import re

            nome_exibicao = funcionario_nome

                # remove coisas como (6) (4) (1)
            nome_exibicao = re.sub(r"\(\d+\)", "", nome_exibicao)

                # remove espaços extras
            nome_exibicao = nome_exibicao.strip()

                # capitaliza nome
            nome_exibicao = nome_exibicao.title()

            ranking_funcionarios.append(
                {
                    "nome": nome_exibicao,
                    "departamento": None,
                    "total": total_func,
                    "inclusoes": inclusoes_func,
                    "alteracoes": alteracoes_func,
                    "exclusoes": exclusoes_func,
                    "cancelamentos": cancelamentos_func,
                }
            )

            tabela_resumo.append(
                {
                    "funcionario": nome_exibicao,
                    "departamento": None,
                    "acoes": total_func,
                    "inclusoes": inclusoes_func,
                    "alteracoes": alteracoes_func,
                    "exclusoes": exclusoes_func,
                    "cancelamentos": cancelamentos_func,
                }
            )

        return {
            "filtros": {
                "acao": (acao or "").strip().upper() or None,
                "data_inicial": data_inicial_normalizada,
                "data_final": data_final_normalizada,
            },
            "resumo": {
                "total": total,
                "inclusoes": inclusoes,
                "alteracoes": alteracoes,
                "exclusoes": exclusoes,
                "cancelamentos": cancelamentos,
            },
            "produtividade": {
                "dias_com_atividade": dias_com_atividade,
                "media_por_dia": media_por_dia,
                "hora_mais_ativa": hora_mais_ativa,
                "tabela_mais_movimentada": tabela_mais_movimentada,
            },
            "acoes_por_dia": acoes_por_dia,
            "acoes_por_horario": acoes_por_horario,
            "ranking_funcionarios": ranking_funcionarios,
            "tabela_resumo": tabela_resumo,
            "registros": [],
        }

    def obter_filtros_detalhe(
        self,
        tipo: str,
        data_inicial: str = "",
        data_final: str = "",
    ):
        data_inicial_normalizada, data_final_normalizada = normalizar_periodo(
            data_inicial,
            data_final,
        )

        where_sql, params = montar_filtro_detalhado(
            tipo=tipo,
            usuario="",
            tabela="",
            data_inicial=data_inicial_normalizada,
            data_final=data_final_normalizada,
        )

        rows_usuarios = self.repository.buscar_usuarios_filtro(where_sql, params)
        rows_tabelas = self.repository.buscar_tabelas_filtro(where_sql, params)

        usuarios = [
            str(row[0]).strip()
            for row in rows_usuarios
            if row[0] and str(row[0]).strip()
        ]

        tabelas = [
            str(row[0]).strip()
            for row in rows_tabelas
            if row[0] and str(row[0]).strip()
        ]

        return {
            "usuarios": usuarios,
            "tabelas": tabelas,
        }

    def obter_registros(
        self,
        tipo: str = "",
        usuario: str = "",
        tabela: str = "",
        data_inicial: str = "",
        data_final: str = "",
    ):
        data_inicial_normalizada, data_final_normalizada = normalizar_periodo(
            data_inicial,
            data_final,
        )

        where_sql, params = montar_filtro_detalhado(
            tipo=tipo,
            usuario=usuario,
            tabela=tabela,
            data_inicial=data_inicial_normalizada,
            data_final=data_final_normalizada,
        )

        rows = self.repository.buscar_registros(where_sql, params)

        registros = []
        for row in rows:
            id_registro = None
            valor_id_registro = row[3]

            if valor_id_registro is not None:
                texto_id_registro = str(valor_id_registro).strip()
                if texto_id_registro.isdigit():
                    id_registro = int(texto_id_registro)

            registros.append(
                {
                    "usuario": str(row[0]).strip() if row[0] else "",
                    "tabela_desc": str(row[1]).strip() if row[1] else "",
                    "tabela": str(row[2]).strip() if row[2] else "",
                    "id_registro": id_registro,
                    "descricao_registro": str(row[4]).strip() if row[4] else "",
                    "data_lancamento": row[5].isoformat() if row[5] else None,
                    "data_acao": row[6].isoformat() if row[6] else None,
                    "acao": str(row[7]).strip() if row[7] else "",
                }
            )

        return {
            "registros": registros
        }