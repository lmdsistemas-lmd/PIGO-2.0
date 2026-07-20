from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.erp_query_service import ERPQueryService

router = APIRouter(prefix="/funcionarios", tags=["Funcionários"])
logger = logging.getLogger(__name__)


def _normalizar_funcionario_erp(row: dict[str, Any]) -> dict[str, Any]:
    pes_id = row.get("COL_PESSOA") or row.get("PES_ID")
    nome = str(row.get("PES_RSOCIAL_NOME") or row.get("PES_FANTASIA_APELIDO") or "").strip()

    return {
        "pes_id": pes_id,
        "col_pessoa": pes_id,
        "usuario_id": None,
        "login": None,
        "nome": nome or "Funcionario sem nome",
        "cpf": row.get("PES_CNPJ_CPF"),
        "email": row.get("PES_EMAIL"),
        "telefone": row.get("PES_TELEFONE"),
        "celular": row.get("PES_CELULAR"),
        "cargo_oficial": str(row.get("COL_FUNCAO") or row.get("PES_PROFISSAO") or "").strip() or "Nao informado",
        "status": str(row.get("COL_STATUS") or row.get("PES_STATUS") or "Sem status").strip() or "Sem status",
        "salario": float(row["COL_SALARIO_VALOR"]) if row.get("COL_SALARIO_VALOR") is not None else None,
        "data_admissao": str(row.get("COL_DATA_ADMISSAO")) if row.get("COL_DATA_ADMISSAO") else None,
        "data_afastamento": str(row.get("COL_DATA_AFASTAMENTO")) if row.get("COL_DATA_AFASTAMENTO") else None,
        "departamento_id": None,
        "departamento_nome": None,
        "vendedor": str(row.get("PES_VENDEDOR") or "").strip().upper() == "S",
        "origem": "colaborador",
    }


def _normalizar_usuario_erp(row: dict[str, Any]) -> dict[str, Any]:
    usuario_id = row.get("USU_ID")
    nome = str(row.get("USU_NOME") or row.get("USU_LOGIN") or "").strip()
    administrador = str(row.get("USU_ADMINISTRADOR") or "").strip().upper()

    return {
        "pes_id": usuario_id,
        "col_pessoa": usuario_id,
        "usuario_id": usuario_id,
        "login": row.get("USU_LOGIN"),
        "nome": nome or "Usuario sem nome",
        "cpf": None,
        "email": None,
        "telefone": None,
        "celular": None,
        "cargo_oficial": "Administrador ERP" if administrador in {"S", "SIM", "1", "TRUE", "T"} else "Usuario ERP",
        "status": "Ativo",
        "salario": None,
        "data_admissao": None,
        "data_afastamento": None,
        "departamento_id": None,
        "departamento_nome": None,
        "vendedor": False,
        "origem": "usuario_erp",
    }


@router.get("")
@router.get("/")
def listar_funcionarios(
    nome: str = "",
    status_filtro: str = Query(default="", alias="status"),
    cargo: str = "",
    empresa_id: int | None = Query(default=None),
):
    erp = ERPQueryService()
    logger.info(
        "Listando funcionarios endpoint=/funcionarios empresa_id=%s filtros=%s",
        empresa_id,
        {"nome": nome, "status": status_filtro, "cargo": cargo},
    )

    query_erp = """
        SELECT
            c.COL_PESSOA,
            c.COL_FUNCAO,
            c.COL_STATUS,
            c.COL_SALARIO_VALOR,
            c.COL_DATA_ADMISSAO,
            c.COL_DATA_AFASTAMENTO,
            p.PES_RSOCIAL_NOME,
            p.PES_CNPJ_CPF,
            p.PES_EMAIL,
            p.PES_TELEFONE,
            p.PES_CELULAR,
            p.PES_VENDEDOR
        FROM TB_COLABORADOR c
        LEFT JOIN TB_PESSOA p
          ON p.PES_ID = c.COL_PESSOA
        ORDER BY p.PES_RSOCIAL_NOME
        """

    colaboradores = erp.fetch_all(query_erp)
    logger.info(
        "Consulta funcionarios por TB_COLABORADOR retornou %s registros",
        len(colaboradores),
    )

    resultado = [_normalizar_funcionario_erp(row) for row in colaboradores]

    if not resultado:
        query_usuarios = """
            SELECT
                u.USU_ID,
                u.USU_LOGIN,
                u.USU_NOME,
                u.USU_ADMINISTRADOR,
                COUNT(a.AUD_ID_REGISTRO) AS TOTAL_ACOES
            FROM TB_USUARIO u
            LEFT JOIN TB_AUDITORIA a
              ON a.AUD_USUARIO = u.USU_ID
             AND a.tenant_id = u.tenant_id
            GROUP BY
                u.USU_ID,
                u.USU_LOGIN,
                u.USU_NOME,
                u.USU_ADMINISTRADOR
            ORDER BY u.USU_NOME
        """
        usuarios = erp.fetch_all(query_usuarios)
        logger.info(
            "Fallback funcionarios por TB_USUARIO/TB_AUDITORIA retornou %s registros",
            len(usuarios),
        )
        resultado = [_normalizar_usuario_erp(row) for row in usuarios]

    filtrado = []
    nome_limpo = (nome or "").strip().lower()
    cargo_limpo = (cargo or "").strip().lower()
    status_limpo = (status_filtro or "").strip().lower()

    for funcionario in resultado:
        nome_erp = str(funcionario.get("nome") or "")
        cargo_erp = str(funcionario.get("cargo_oficial") or "")
        status_erp = str(funcionario.get("status") or "")

        if nome_limpo and nome_limpo not in nome_erp.lower():
            continue

        if cargo_limpo and cargo_limpo not in cargo_erp.lower():
            continue

        if status_limpo and status_limpo not in status_erp.lower():
            continue

        filtrado.append(funcionario)

    logger.info(
        "Endpoint /funcionarios retornando %s registros. estrutura=%s",
        len(filtrado),
        list(filtrado[0].keys()) if filtrado else [],
    )
    return filtrado


@router.get("/{pes_id}/auditoria")
def listar_auditoria_funcionario(
    pes_id: int,
    tipo: str = Query(default=""),
    data_inicial: str = Query(default=""),
    data_final: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=5000),
    empresa_id: int | None = Query(default=None),
):
    logger.info(
        "Endpoint /funcionarios/%s/auditoria chamado. params=%s",
        pes_id,
        {
            "tipo": tipo,
            "data_inicial": data_inicial,
            "data_final": data_final,
            "limit": limit,
            "empresa_id": empresa_id,
        },
    )

    service = ERPQueryService()
    col_pessoa = pes_id
    limit = min(max(int(limit), 1), 5000)

    usuario = service.fetch_one(
        """
        SELECT
            U.USU_ID,
            U.USU_LOGIN,
            U.USU_NOME,
            U.USU_ADMINISTRADOR
        FROM TB_USUARIO U
        WHERE CAST(U.USU_ID AS VARCHAR(30)) = :funcionario_id
        """,
        {"funcionario_id": str(col_pessoa)},
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Funcionario nao encontrado no ERP sincronizado.",
        )

    filtros = ["CAST(A.AUD_USUARIO AS VARCHAR(30)) = :funcionario_id"]
    params: dict[str, Any] = {"funcionario_id": str(col_pessoa)}

    tipo_limpo = (tipo or "").strip()
    if tipo_limpo:
        filtros.append(
            """
            (
                UPPER(COALESCE(A.AUD_TABELA_DESC, '')) LIKE :tipo_like
                OR UPPER(COALESCE(A.AUD_TABELA, '')) LIKE :tipo_like
                OR UPPER(COALESCE(A.AUD_DESC_REGISTRO, '')) LIKE :tipo_like
                OR UPPER(COALESCE(A.AUD_ACAO, '')) = :tipo_acao
            )
            """
        )
        params["tipo_like"] = f"%{tipo_limpo.upper()}%"
        params["tipo_acao"] = tipo_limpo.upper()[:1]

    data_inicial_limpa = (data_inicial or "").strip()
    if data_inicial_limpa:
        filtros.append("CAST(A.AUD_DT_LANCAMENTO AS DATE) >= CAST(:data_inicial AS DATE)")
        params["data_inicial"] = data_inicial_limpa

    data_final_limpa = (data_final or "").strip()
    if data_final_limpa:
        filtros.append("CAST(A.AUD_DT_LANCAMENTO AS DATE) <= CAST(:data_final AS DATE)")
        params["data_final"] = data_final_limpa

    if empresa_id is not None:
        filtros.append("CAST(A.AUD_EMPRESA AS VARCHAR(30)) = :empresa_id")
        params["empresa_id"] = str(empresa_id)

    where_sql = " AND ".join(filtros)
    sql_auditoria = f"""
        SELECT FIRST {limit}
            A.AUD_USUARIO,
            A.AUD_ACAO,
            A.AUD_TABELA_DESC,
            A.AUD_DESC_REGISTRO,
            A.AUD_DT_ACAO,
            A.AUD_DT_LANCAMENTO,
            A.AUD_SEQUENCIA,
            A.AUD_ID_REGISTRO,
            A.AUD_TABELA
        FROM TB_AUDITORIA A
        WHERE {where_sql}
        ORDER BY A.AUD_DT_LANCAMENTO DESC, A.AUD_SEQUENCIA DESC
    """

    logger.info(
        "SQL auditoria funcionario preparado. funcionario_id=%s sql=%s params=%s",
        col_pessoa,
        sql_auditoria,
        params,
    )
    registros = service.fetch_all(sql_auditoria, params)

    def traduzir_acao(sigla: str | None) -> str:
        valor = str(sigla or "").strip().upper()
        mapa = {
            "I": "Inclusão",
            "A": "Alteração",
            "E": "Exclusão",
            "C": "Cancelamento",
        }
        return mapa.get(valor, valor or "Não informado")

    resultado = []
    for registro in registros:
        resultado.append(
            {
                "aud_usuario": registro.get("AUD_USUARIO"),
                "acao_sigla": registro.get("AUD_ACAO"),
                "acao": traduzir_acao(registro.get("AUD_ACAO")),
                "tabela_desc": registro.get("AUD_TABELA_DESC"),
                "campo_desc": None,
                "descricao_registro": registro.get("AUD_DESC_REGISTRO"),
                "data_hora": str(registro.get("AUD_DT_ACAO")) if registro.get("AUD_DT_ACAO") else None,
                "data_lancamento": str(registro.get("AUD_DT_LANCAMENTO")) if registro.get("AUD_DT_LANCAMENTO") else None,
                "aud_sequencia": registro.get("AUD_SEQUENCIA"),
                "aud_id_registro": registro.get("AUD_ID_REGISTRO"),
                "aud_tabela": registro.get("AUD_TABELA"),
                "aud_vendedor": None,
                "valor_antigo": None,
                "valor_novo": None,
            }
        )

    logger.info(
        "Endpoint /funcionarios/%s/auditoria retornando %s registros. estrutura=%s",
        col_pessoa,
        len(resultado),
        list(resultado[0].keys()) if resultado else [],
    )

    return {
        "pes_id": col_pessoa,
        "col_pessoa": col_pessoa,
        "usuario_ids_relacionados": [str(col_pessoa)],
        "tipo_filtro": tipo_limpo if tipo_limpo else None,
        "data_inicial": data_inicial_limpa if data_inicial_limpa else None,
        "data_final": data_final_limpa if data_final_limpa else None,
        "limit": limit,
        "total": len(resultado),
        "registros": resultado,
    }

    col_pessoa = pes_id

    query_colaborador = text(
        """
        SELECT COL_PESSOA
        FROM TB_COLABORADOR
        WHERE COL_PESSOA = :col_pessoa
        """
    )

    colaborador = erp_db.execute(
        query_colaborador,
        {"col_pessoa": col_pessoa},
    ).fetchone()

    if not colaborador:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado no ERP.")

    query_usuarios = text(
        """
        SELECT
            U.USU_ID,
            U.USU_NOME,
            U.USU_LOGIN
        FROM TB_COLABORADOR C
        INNER JOIN TB_PESSOA P
            ON P.PES_ID = C.COL_PESSOA
        INNER JOIN TB_USUARIO U
            ON U.USU_VENDEDOR = P.PES_ID
        WHERE C.COL_PESSOA = :col_pessoa
        """
    )

    usuarios = erp_db.execute(
        query_usuarios,
        {"col_pessoa": col_pessoa},
    ).fetchall()

    usuario_ids = []
    for usuario in usuarios:
        usu_id = usuario[0]
        if usu_id is not None:
            usuario_ids.append(str(usu_id).strip())

    usuario_ids = list(dict.fromkeys(usuario_ids))
    limit = min(max(int(limit), 1), 5000)

    filtros = []
    params: dict[str, Any] = {"col_pessoa": col_pessoa}

    bloco_principal = ["A.AUD_VENDEDOR = :col_pessoa"]

    for idx, usuario_id in enumerate(usuario_ids):
        chave = f"usuario_id_{idx}"
        bloco_principal.append(f"CAST(A.AUD_USUARIO AS VARCHAR(30)) = :{chave}")
        params[chave] = usuario_id

    filtros.append("(" + " OR ".join(bloco_principal) + ")")

    tipo_limpo = (tipo or "").strip()
    if tipo_limpo:
        filtros.append(
            """
            (
                UPPER(COALESCE(A.AUD_TABELA_DESC, '')) LIKE :tipo_like
                OR UPPER(COALESCE(AI.AUDI_CAMPO_DESC, '')) LIKE :tipo_like
                OR UPPER(COALESCE(A.AUD_DESC_REGISTRO, '')) LIKE :tipo_like
            )
            """
        )
        params["tipo_like"] = f"%{tipo_limpo.upper()}%"

    data_inicial_limpa = (data_inicial or "").strip()
    if data_inicial_limpa:
        filtros.append("CAST(A.AUD_DT_ACAO AS DATE) >= CAST(:data_inicial AS DATE)")
        params["data_inicial"] = data_inicial_limpa

    data_final_limpa = (data_final or "").strip()
    if data_final_limpa:
        filtros.append("CAST(A.AUD_DT_ACAO AS DATE) <= CAST(:data_final AS DATE)")
        params["data_final"] = data_final_limpa

    where_sql = " AND ".join(filtros)

    query_auditoria = text(
        f"""
        SELECT FIRST {limit}
            A.AUD_USUARIO,
            A.AUD_ACAO,
            A.AUD_TABELA_DESC,
            AI.AUDI_CAMPO_DESC,
            A.AUD_DESC_REGISTRO,
            A.AUD_DT_ACAO,
            A.AUD_DT_LANCAMENTO,
            A.AUD_SEQUENCIA,
            A.AUD_ID_REGISTRO,
            A.AUD_TABELA,
            A.AUD_VENDEDOR,
            AI.AUDI_VALOR_ANTIGO,
            AI.AUDI_VALOR_NOVO
        FROM TB_AUDITORIA A
        LEFT JOIN TB_AUDITORIA_ITEM AI
          ON AI.AUDI_ID_REGISTRO = A.AUD_ID_REGISTRO
        WHERE {where_sql}
        ORDER BY
            SUBSTRING(A.AUD_DT_LANCAMENTO FROM 7 FOR 4) ||
            SUBSTRING(A.AUD_DT_LANCAMENTO FROM 4 FOR 2) ||
            SUBSTRING(A.AUD_DT_LANCAMENTO FROM 1 FOR 2) ||
            SUBSTRING(A.AUD_DT_LANCAMENTO FROM 12 FOR 5) DESC,
            A.AUD_SEQUENCIA DESC
        """
    )

    registros = erp_db.execute(query_auditoria, params).fetchall()

    def traduzir_acao(sigla: str | None) -> str:
        valor = str(sigla or "").strip().upper()
        mapa = {
            "I": "Inclusão",
            "A": "Alteração",
            "E": "Exclusão",
            "C": "Cancelamento",
        }
        return mapa.get(valor, valor or "Não informado")

    resultado = []

    for registro in registros:
        resultado.append(
            {
                "aud_usuario": registro[0],
                "acao_sigla": registro[1],
                "acao": traduzir_acao(registro[1]),
                "tabela_desc": registro[2],
                "campo_desc": registro[3],
                "descricao_registro": registro[4],
                "data_hora": str(registro[5]) if registro[5] else None,
                "data_lancamento": str(registro[6]) if registro[6] else None,
                "aud_sequencia": registro[7],
                "aud_id_registro": registro[8],
                "aud_tabela": registro[9],
                "aud_vendedor": registro[10],
                "valor_antigo": registro[11],
                "valor_novo": registro[12],
            }
        )

    return {
        "pes_id": col_pessoa,
        "col_pessoa": col_pessoa,
        "usuario_ids_relacionados": usuario_ids,
        "tipo_filtro": tipo_limpo if tipo_limpo else None,
        "data_inicial": data_inicial_limpa if data_inicial_limpa else None,
        "data_final": data_final_limpa if data_final_limpa else None,
        "limit": limit,
        "total": len(resultado),
        "registros": resultado,
    }


@router.get("/{pes_id}")
def detalhar_funcionario(
    pes_id: int,
    empresa_id: int | None = Query(default=None),
):
    logger.info(
        "Endpoint /funcionarios/%s chamado. params=%s",
        pes_id,
        {"empresa_id": empresa_id},
    )

    service = ERPQueryService()
    col_pessoa = pes_id

    usuario = service.fetch_one(
        """
        SELECT
            U.USU_ID,
            U.USU_LOGIN,
            U.USU_NOME,
            U.USU_ADMINISTRADOR
        FROM TB_USUARIO U
        WHERE CAST(U.USU_ID AS VARCHAR(30)) = :funcionario_id
        """,
        {"funcionario_id": str(col_pessoa)},
    )

    if usuario:
        detalhe = _normalizar_usuario_erp(usuario)
        detalhe.update(
            {
                "departamento_id": None,
                "departamento_nome": None,
                "data_admissao_oficial": None,
                "salario_oficial": None,
                "status_oficial": detalhe.get("status"),
                "erp_colaborador": None,
                "erp_pessoa": None,
                "erp_usuario": {
                    "USU_ID": usuario.get("USU_ID"),
                    "USU_LOGIN": usuario.get("USU_LOGIN"),
                    "USU_NOME": usuario.get("USU_NOME"),
                    "USU_ADMINISTRADOR": usuario.get("USU_ADMINISTRADOR"),
                },
            }
        )
        logger.info(
            "Endpoint /funcionarios/%s retornando usuario ERP sincronizado. estrutura=%s",
            col_pessoa,
            list(detalhe.keys()),
        )
        return detalhe

    colaborador = service.fetch_one(
        """
        SELECT
            C.COL_PESSOA,
            C.COL_EMPRESA,
            C.COL_STATUS,
            P.PES_ID,
            P.PES_RSOCIAL_NOME,
            P.PES_FANTASIA_APELIDO,
            P.PES_EMAIL,
            P.PES_TELEFONE,
            P.PES_CELULAR,
            P.PES_VENDEDOR
        FROM TB_COLABORADOR C
        LEFT JOIN TB_PESSOA P
          ON P.PES_ID = C.COL_PESSOA
        WHERE CAST(C.COL_PESSOA AS VARCHAR(30)) = :funcionario_id
        """,
        {"funcionario_id": str(col_pessoa)},
    )

    if not colaborador:
        raise HTTPException(
            status_code=404,
            detail="Funcionario nao encontrado no ERP sincronizado.",
        )

    detalhe = _normalizar_funcionario_erp(colaborador)
    detalhe.update(
        {
            "data_admissao_oficial": detalhe.get("data_admissao"),
            "salario_oficial": detalhe.get("salario"),
            "status_oficial": detalhe.get("status"),
            "erp_colaborador": {
                "COL_PESSOA": colaborador.get("COL_PESSOA"),
                "COL_EMPRESA": colaborador.get("COL_EMPRESA"),
                "COL_STATUS": colaborador.get("COL_STATUS"),
            },
            "erp_pessoa": {
                "PES_ID": colaborador.get("PES_ID"),
                "PES_RSOCIAL_NOME": colaborador.get("PES_RSOCIAL_NOME"),
                "PES_FANTASIA_APELIDO": colaborador.get("PES_FANTASIA_APELIDO"),
                "PES_EMAIL": colaborador.get("PES_EMAIL"),
                "PES_TELEFONE": colaborador.get("PES_TELEFONE"),
                "PES_CELULAR": colaborador.get("PES_CELULAR"),
                "PES_VENDEDOR": colaborador.get("PES_VENDEDOR"),
            },
            "erp_usuario": None,
        }
    )

    logger.info(
        "Endpoint /funcionarios/%s retornando colaborador ERP sincronizado. estrutura=%s",
        col_pessoa,
        list(detalhe.keys()),
    )
    return detalhe

    col_pessoa = pes_id

    query_erp = text(
        """
        SELECT
            c.COL_EMPRESA,
            c.COL_FUNCAO,
            c.COL_SALARIO,
            c.COL_STATUS,
            c.COL_PROFISSAO,
            c.COL_CPF,
            c.COL_RG,
            c.COL_ESTADO_CIVIL,
            c.COL_DT_CADASTRO,
            c.COL_EDITADO,
            c.COL_CARTEIRA_TRABALHO,
            c.COL_SERIE,
            c.COL_TITULO_ELEITOR,
            c.COL_TITULO_ZONA,
            c.COL_PIS,
            c.COL_DATA_ADMISSAO,
            c.COL_DATA_AFASTAMENTO,
            c.COL_HORARIO_ENTRADA,
            c.COL_INTERVALO_INCIAIL,
            c.COL_INTERVALO_FINAL,
            c.COL_HORARIO_SAIDA,
            c.COL_RAZAO_SOCIAL_REGISTRADA,
            c.COL_CARTAO_PONTO,
            c.COL_TITULO_SECAO,
            c.COL_SALARIO_VALOR,
            c.COL_PESSOA,

            p.PES_ID,
            p.PES_TIPO_PESSOA,
            p.PES_RSOCIAL_NOME,
            p.PES_FANTASIA_APELIDO,
            p.PES_CNPJ_CPF,
            p.PES_IE_RG,
            p.PES_ENDERECO,
            p.PES_COMPLEMENTO,
            p.PES_NUMERO,
            p.PES_BAIRRO,
            p.PES_CIDADE,
            p.PES_CEP,
            p.PES_TELEFONE,
            p.PES_FAX,
            p.PES_CELULAR,
            p.PES_EMAIL,
            p.PES_CONTATO,
            p.PES_OBSERVACAO,
            p.PES_DT_CADASTRO,
            p.PES_DT_NASCIMENTO,
            p.PES_STATUS,
            p.PES_CLIENTE,
            p.PES_FORNECEDOR,
            p.PES_VENDEDOR,
            p.PES_COLABORADOR,
            p.PES_TRANSPORTADOR,
            p.PES_SEXO,
            p.PES_PROFISSAO,
            p.PES_ULTIMA_ALTERACAO,
            p.PES_GUID
        FROM TB_COLABORADOR c
        JOIN TB_PESSOA p
          ON p.PES_ID = c.COL_PESSOA
        WHERE c.COL_PESSOA = :col_pessoa
        """
    )

    colaborador = erp_db.execute(
        query_erp,
        {"col_pessoa": col_pessoa},
    ).fetchone()

    if not colaborador:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado no ERP.")

    return {
        "pes_id": col_pessoa,
        "col_pessoa": col_pessoa,
        "departamento_id": None,
        "departamento_nome": None,
        "cargo_oficial": colaborador[1],
        "data_admissao_oficial": str(colaborador[15]) if colaborador[15] else None,
        "salario_oficial": float(colaborador[24]) if colaborador[24] is not None else None,
        "status_oficial": colaborador[3],
        "erp_colaborador": {
            "COL_EMPRESA": colaborador[0],
            "COL_FUNCAO": colaborador[1],
            "COL_SALARIO": colaborador[2],
            "COL_STATUS": colaborador[3],
            "COL_PROFISSAO": colaborador[4],
            "COL_CPF": colaborador[5],
            "COL_RG": colaborador[6],
            "COL_ESTADO_CIVIL": colaborador[7],
            "COL_DT_CADASTRO": str(colaborador[8]) if colaborador[8] else None,
            "COL_EDITADO": colaborador[9],
            "COL_CARTEIRA_TRABALHO": colaborador[10],
            "COL_SERIE": colaborador[11],
            "COL_TITULO_ELEITOR": colaborador[12],
            "COL_TITULO_ZONA": colaborador[13],
            "COL_PIS": colaborador[14],
            "COL_DATA_ADMISSAO": str(colaborador[15]) if colaborador[15] else None,
            "COL_DATA_AFASTAMENTO": str(colaborador[16]) if colaborador[16] else None,
            "COL_HORARIO_ENTRADA": str(colaborador[17]) if colaborador[17] else None,
            "COL_INTERVALO_INCIAIL": str(colaborador[18]) if colaborador[18] else None,
            "COL_INTERVALO_FINAL": str(colaborador[19]) if colaborador[19] else None,
            "COL_HORARIO_SAIDA": str(colaborador[20]) if colaborador[20] else None,
            "COL_RAZAO_SOCIAL_REGISTRADA": colaborador[21],
            "COL_CARTAO_PONTO": colaborador[22],
            "COL_TITULO_SECAO": colaborador[23],
            "COL_SALARIO_VALOR": float(colaborador[24]) if colaborador[24] is not None else None,
            "COL_PESSOA": colaborador[25],
        },
        "erp_pessoa": {
            "PES_ID": colaborador[26],
            "PES_TIPO_PESSOA": colaborador[27],
            "PES_RSOCIAL_NOME": colaborador[28],
            "PES_FANTASIA_APELIDO": colaborador[29],
            "PES_CNPJ_CPF": colaborador[30],
            "PES_IE_RG": colaborador[31],
            "PES_ENDERECO": colaborador[32],
            "PES_COMPLEMENTO": colaborador[33],
            "PES_NUMERO": colaborador[34],
            "PES_BAIRRO": colaborador[35],
            "PES_CIDADE": colaborador[36],
            "PES_CEP": colaborador[37],
            "PES_TELEFONE": colaborador[38],
            "PES_FAX": colaborador[39],
            "PES_CELULAR": colaborador[40],
            "PES_EMAIL": colaborador[41],
            "PES_CONTATO": colaborador[42],
            "PES_OBSERVACAO": colaborador[43],
            "PES_DT_CADASTRO": str(colaborador[44]) if colaborador[44] else None,
            "PES_DT_NASCIMENTO": str(colaborador[45]) if colaborador[45] else None,
            "PES_STATUS": colaborador[46],
            "PES_CLIENTE": colaborador[47],
            "PES_FORNECEDOR": colaborador[48],
            "PES_VENDEDOR": colaborador[49],
            "PES_COLABORADOR": colaborador[50],
            "PES_TRANSPORTADOR": colaborador[51],
            "PES_SEXO": colaborador[52],
            "PES_PROFISSAO": colaborador[53],
            "PES_ULTIMA_ALTERACAO": str(colaborador[54]) if colaborador[54] else None,
            "PES_GUID": colaborador[55],
        },
    }
