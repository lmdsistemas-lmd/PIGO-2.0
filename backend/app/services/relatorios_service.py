from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.relatorio_fastreport_parser import parse_fastreport_xml


PARAM_REGEX = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


class RelatoriosService:
    def __init__(self, db: Session):
        self.db = db

    def _categoria_valida(self, categoria: str) -> str:
        categoria = (categoria or "").strip().lower()
        validas = {"vendas", "financeiro", "consultoria", "diversos"}

        if categoria not in validas:
            raise HTTPException(status_code=400, detail="Categoria inválida")

        return categoria

    def _normalizar(self, valor: Optional[str]) -> str:
        return (valor or "").strip().upper()

    def _categorizar(self, pasta: Optional[str], pasta_pai: Optional[str]) -> str:
        texto = f"{self._normalizar(pasta)} {self._normalizar(pasta_pai)}"

        if any(x in texto for x in ["VEND", "PEDIDO", "COMERCIAL", "FATUR"]):
            return "vendas"

        if any(x in texto for x in ["FINANC", "CAIXA", "RECEBER", "PAGAR"]):
            return "financeiro"

        if any(
            x in texto
            for x in ["CONTAB", "CONSULT", "FISCAL", "TRIBUT", "RESULTADO"]
        ):
            return "consultoria"

        return "diversos"

    def listar_relatorios(self, categoria: str) -> List[Dict[str, Any]]:
        categoria = self._categoria_valida(categoria)

        sql = text(
            """
            SELECT
                ra.cdarquivo,
                ra.cdpastamae,
                ra.nome,
                ra.descricao,
                ra.exportar,
                ra.periodo_app,
                ra.vendedor_app,
                ra.cliente_app,
                ra.empresa_app,
                ra.ultima_alteracao,
                p.nome AS pasta_nome,
                pm.nome AS pasta_pai_nome
            FROM RELATORIOARQUIVO ra
            LEFT JOIN RELATORIOPASTA p
                ON p.cdpasta = ra.cdpastamae
            LEFT JOIN RELATORIOPASTA pm
                ON pm.cdpasta = p.cdpastamae
            WHERE COALESCE(ra.exportar, 'N') = 'S'
            ORDER BY p.nome, ra.nome
            """
        )

        rows = self.db.execute(sql).mappings().all()

        resultado: List[Dict[str, Any]] = []

        for row in rows:
            pasta = row.get("pasta_nome")
            pasta_pai = row.get("pasta_pai_nome")
            categoria_item = self._categorizar(pasta, pasta_pai)

            if categoria_item != categoria:
                continue

            resultado.append(
                {
                    "cdarquivo": row.get("cdarquivo"),
                    "nome": row.get("nome"),
                    "descricao": row.get("descricao"),
                    "pasta": pasta,
                    "pasta_pai": pasta_pai,
                    "ultima_alteracao": str(row.get("ultima_alteracao"))
                    if row.get("ultima_alteracao")
                    else None,
                    "categoria": categoria_item,
                    "flags": {
                        "periodo_app": row.get("periodo_app"),
                        "vendedor_app": row.get("vendedor_app"),
                        "cliente_app": row.get("cliente_app"),
                        "empresa_app": row.get("empresa_app"),
                    },
                }
            )

        return resultado

    def _obter_relatorio_base(self, cdarquivo: int) -> Dict[str, Any]:
        sql = text(
            """
            SELECT
                ra.cdarquivo,
                ra.cdpastamae,
                ra.nome,
                ra.descricao,
                ra.arquivo,
                ra.exportar,
                ra.periodo_app,
                ra.vendedor_app,
                ra.cliente_app,
                ra.empresa_app,
                ra.ultima_alteracao,
                p.nome AS pasta_nome,
                pm.nome AS pasta_pai_nome
            FROM RELATORIOARQUIVO ra
            LEFT JOIN RELATORIOPASTA p
                ON p.cdpasta = ra.cdpastamae
            LEFT JOIN RELATORIOPASTA pm
                ON pm.cdpasta = p.cdpastamae
            WHERE ra.cdarquivo = :cdarquivo
            """
        )

        row = self.db.execute(sql, {"cdarquivo": cdarquivo}).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Relatório não encontrado")

        return dict(row)

    def _blob_para_texto(self, blob_data: Any) -> str:
        if blob_data is None:
            raise HTTPException(
                status_code=400,
                detail="Relatório sem conteúdo no campo ARQUIVO",
            )

        if hasattr(blob_data, "read"):
            try:
                content = blob_data.read()
            finally:
                try:
                    blob_data.close()
                except Exception:
                    pass

            if isinstance(content, bytes):
                try:
                    return content.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        return content.decode("latin-1")
                    except UnicodeDecodeError:
                        return content.decode("utf-8", errors="ignore")

            return str(content)

        if isinstance(blob_data, bytes):
            try:
                return blob_data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return blob_data.decode("latin-1")
                except UnicodeDecodeError:
                    return blob_data.decode("utf-8", errors="ignore")

        return str(blob_data)

    def _inferir_parametros_detectados(
        self,
        queries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hoje = date.today()
        primeiro_dia = hoje.replace(day=1)

        unicos: Dict[str, Dict[str, Any]] = {}

        for query in queries:
            parametros = query.get("parametros", []) or []

            for param in parametros:
                original_name = str(param.get("name") or "").strip()
                datatype = str(param.get("datatype") or "").strip().lower()

                if not original_name:
                    continue

                chave = original_name.upper()

                if chave in unicos:
                    continue

                inferred_type = "str"
                semantic_key = chave.lower()
                default_value: Any = ""

                if "date" in datatype:
                    inferred_type = "date"

                    if "INICIAL" in chave or "INICIO" in chave or "INI" in chave:
                        semantic_key = "data_inicial"
                        default_value = primeiro_dia
                    elif "FINAL" in chave or "FIM" in chave:
                        semantic_key = "data_final"
                        default_value = hoje
                    else:
                        semantic_key = "data"
                        default_value = hoje

                elif any(
                    item in datatype for item in ["integer", "smallint", "bigint", "int"]
                ):
                    inferred_type = "int"
                    default_value = 0

                    if "EMPRESA" in chave:
                        semantic_key = "empresa"
                        default_value = 1
                    elif "VENDEDOR" in chave:
                        semantic_key = "vendedor"
                    elif "CLIENTE" in chave:
                        semantic_key = "cliente"
                    elif "NATUREZA" in chave:
                        semantic_key = "natureza"
                    elif "GRUPO" in chave:
                        semantic_key = "grupo"
                    elif "MARCA" in chave:
                        semantic_key = "marca"
                    elif "CIDADE" in chave:
                        semantic_key = "cidade"
                    elif "REGIAO" in chave or "REGIÃO" in chave:
                        semantic_key = "regiao"
                    elif "FORNECEDOR" in chave:
                        semantic_key = "fornecedor"

                elif any(item in datatype for item in ["numeric", "float", "double", "decimal"]):
                    inferred_type = "number"
                    default_value = 0

                if chave in {"PANALISE", "PTIPO"}:
                    semantic_key = "analise"
                    inferred_type = "str"
                    default_value = "GRUPO"

                if chave == "TIPODATA":
                    semantic_key = "tipo_data"
                    inferred_type = "str"
                    default_value = "EMISSAO"

                unicos[chave] = {
                    "original_name": original_name,
                    "inferred_type": inferred_type,
                    "semantic_key": semantic_key,
                    "default_value": default_value,
                }

        return list(unicos.values())

    def _parse_relatorio(self, cdarquivo: int) -> Dict[str, Any]:
        relatorio = self._obter_relatorio_base(cdarquivo)
        xml_text = self._blob_para_texto(relatorio.get("arquivo"))
        categoria = self._categorizar(
            relatorio.get("pasta_nome"),
            relatorio.get("pasta_pai_nome"),
        )

        try:
            parsed = parse_fastreport_xml(xml_text)
            xml_valido = True
        except Exception as exc:
            parsed = {
                "datasets": [],
                "variables": [],
                "queries": [],
                "layout_visual": None,
                "observacoes": [f"Falha ao interpretar XML FastReport: {str(exc)}"],
            }
            xml_valido = False

        queries = parsed.get("queries", []) or []
        parameters_detected = parsed.get("parameters_detected")

        if not isinstance(parameters_detected, list):
            parameters_detected = self._inferir_parametros_detectados(queries)

        return {
            "relatorio": relatorio,
            "categoria": categoria,
            "xml_valido": xml_valido,
            "parsed": {
                **parsed,
                "parameters_detected": parameters_detected,
            },
        }

    def inspecionar_relatorio(self, cdarquivo: int) -> Dict[str, Any]:
        info = self._parse_relatorio(cdarquivo)
        relatorio = info["relatorio"]
        parsed = info["parsed"]

        return {
            "cdarquivo": relatorio.get("cdarquivo"),
            "nome": relatorio.get("nome"),
            "descricao": relatorio.get("descricao"),
            "pasta_nome": relatorio.get("pasta_nome"),
            "pasta_pai_nome": relatorio.get("pasta_pai_nome"),
            "categoria": info["categoria"],
            "xml_valido": info["xml_valido"],
            "datasets": parsed.get("datasets", []),
            "variables": parsed.get("variables", []),
            "queries": parsed.get("queries", []),
            "parameters_detected": parsed.get("parameters_detected", []),
            "layout_visual": parsed.get("layout_visual"),
            "observacoes": parsed.get("observacoes", []),
        }

    def obter_xml_bruto(self, cdarquivo: int) -> str:
        relatorio = self._obter_relatorio_base(cdarquivo)
        return self._blob_para_texto(relatorio.get("arquivo"))

    def _resolver_empresa_id(self, payload: Dict[str, Any]) -> int:
        candidatas = [
            payload.get("empresa"),
            payload.get("EMPRESA"),
            payload.get("empresa_id"),
            payload.get("EMPRESA_ID"),
            payload.get("pempresa"),
            payload.get("PEMPRESA"),
            payload.get("EMPRESA_PADRAO"),
            payload.get("empresa_padrao"),
        ]

        for valor in candidatas:
            if valor in (None, "", "0", 0):
                continue
            try:
                return int(valor)
            except (TypeError, ValueError):
                continue

        return 1

    def _modo_preferido_por_relatorio(self, cdarquivo: int) -> Optional[str]:
        mapa = {
            12140306: "dre_composto",
        }
        return mapa.get(int(cdarquivo))

    def _query_dre_topo_por_empresa(self, empresa_id: int) -> List[str]:
        mapa = {
            1: ["RJ"],
            2: ["TOTAL"],
            3: ["VISCONDE"],
        }
        return mapa.get(int(empresa_id), ["RJ"])

    def _query_dre_detalhe_por_empresa(self, empresa_id: int) -> List[str]:
        mapa = {
            1: ["RJPAI"],
            2: ["TOTALPAI"],
            3: ["VISCONDEPAI"],
        }
        return mapa.get(int(empresa_id), ["RJPAI"])

    def _query_dre_indicadores_por_empresa(self, empresa_id: int) -> List[str]:
        mapa = {
            1: ["RJPLC"],
            2: ["TOTALPLC"],
            3: ["VISCONDEPLC"],
        }
        return mapa.get(int(empresa_id), ["RJPLC"])

    def _escolher_query_principal(
        self,
        cdarquivo: int,
        queries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not queries:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma query encontrada no relatório",
            )

        for query in queries:
            sql_text = str(query.get("sql_text") or query.get("sql") or "").strip().lower()

            if (
                sql_text.startswith("select")
                or sql_text.startswith("with")
                or sql_text.startswith("/*")
            ):
                return query

        principal = queries[0]

        if not (principal.get("sql_text") or principal.get("sql")):
            raise HTTPException(
                status_code=400,
                detail="A query principal não possui SQL utilizável",
            )

        return principal

    def _buscar_parametro_payload(self, payload: Dict[str, Any], nome_parametro: str) -> Any:
        if nome_parametro in payload:
            return payload[nome_parametro]

        nome_normalizado = str(nome_parametro).strip().upper()

        for chave, valor in payload.items():
            if str(chave).strip().upper() == nome_normalizado:
                return valor

        return None

    def _parse_date_value(self, raw_value: Any) -> date:
        if isinstance(raw_value, datetime):
            return raw_value.date()

        if isinstance(raw_value, date):
            return raw_value

        if isinstance(raw_value, str):
            texto = raw_value.strip()
            if not texto:
                raise ValueError("Data vazia")

            formatos = (
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%d/%m/%Y",
            )

            for fmt in formatos:
                try:
                    return datetime.strptime(texto, fmt).date()
                except ValueError:
                    continue

        raise ValueError(f"Data inválida: {raw_value}")

    def _coerce_param_value(self, raw_value: Any, inferred_type: Optional[str]) -> Any:
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()

        if raw_value == "":
            return None

        if raw_value is None:
            return None

        inferred_type = (inferred_type or "str").strip().lower()

        if inferred_type == "date":
            return self._parse_date_value(raw_value)

        if inferred_type == "int":
            try:
                if isinstance(raw_value, bool):
                    return int(raw_value)

                if isinstance(raw_value, (int, float, Decimal)):
                    return int(raw_value)

                return int(str(raw_value).strip())
            except (TypeError, ValueError):
                raise ValueError(f"Valor inteiro inválido: {raw_value}")

        if inferred_type in ("number", "float", "decimal"):
            try:
                if isinstance(raw_value, bool):
                    return float(int(raw_value))

                if isinstance(raw_value, (int, float, Decimal)):
                    return float(raw_value)

                texto = str(raw_value).strip()

                if "," in texto:
                    texto = texto.replace(".", "").replace(",", ".")

                return float(texto)
            except (TypeError, ValueError):
                raise ValueError(f"Valor numérico inválido: {raw_value}")

        return str(raw_value).strip() if isinstance(raw_value, str) else raw_value

    def _parametros_unicos_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        unicos: Dict[str, Dict[str, Any]] = {}

        for parametro in query.get("parametros", []) or []:
            nome = str(parametro.get("name") or "").strip().upper()
            if nome and nome not in unicos:
                unicos[nome] = parametro

        return list(unicos.values())

    def _limpar_sql_execucao(self, sql: str) -> str:
        sql = (sql or "").strip()

        while sql.endswith(";"):
            sql = sql[:-1].strip()

        return sql

    def _strip_sql_comments(self, sql: str) -> str:
        sql = self._limpar_sql_execucao(sql)

        sql = re.sub(r"--.*?(\n|$)", " ", sql)
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        sql = re.sub(r"\n{3,}", "\n\n", sql)

        return sql.strip()

    def _extract_sql_param_names(self, sql: str) -> List[str]:
        sql = self._strip_sql_comments(sql)
        encontrados = PARAM_REGEX.findall(sql)

        unicos: List[str] = []
        vistos = set()

        for nome in encontrados:
            if nome not in vistos:
                vistos.add(nome)
                unicos.append(nome)

        return unicos

    def _primeiro_dia_mes_atual(self) -> date:
        hoje = date.today()
        return hoje.replace(day=1)

    def _valor_default_por_nome_sql(
        self,
        nome_parametro_sql: str,
        payload: Dict[str, Any],
    ) -> Any:
        nome = str(nome_parametro_sql or "").strip().upper()
        empresa_id = self._resolver_empresa_id(payload)

        if "EMPRESA" in nome:
            return empresa_id

        if "VENDEDOR" in nome:
            return 0

        if "CLIENTE" in nome:
            return 0

        if "NATUREZA" in nome:
            return 0

        if "GRUPO" in nome:
            return 0

        if "MARCA" in nome:
            return 0

        if "CIDADE" in nome:
            return 0

        if "REGIAO" in nome or "REGIÃO" in nome:
            return 0

        if "FORNECEDOR" in nome:
            return 0

        if nome in {"PTIPO", "PANALISE"} or ("TIPO" in nome and "DATA" not in nome):
            return (
                payload.get("analise")
                or payload.get("ANALISE")
                or payload.get("ptipo")
                or payload.get("PTIPO")
                or "GRUPO"
            )

        if "TIPODATA" in nome or ("TIPO" in nome and "DATA" in nome):
            return (
                payload.get("tipo_data")
                or payload.get("TIPO_DATA")
                or "EMISSAO"
            )

        if ("DATA" in nome or nome.startswith("PDT")) and (
            "INI" in nome or "INICIAL" in nome
        ):
            valor = (
                payload.get("data_inicial")
                or payload.get("DATA_INICIAL")
                or payload.get("datainicial")
                or payload.get("DATAINICIAL")
                or payload.get("pdata_inicial")
                or payload.get("PDATA_INICIAL")
            )
            return self._parse_date_value(valor) if valor else self._primeiro_dia_mes_atual()

        if ("DATA" in nome or nome.startswith("PDT")) and (
            "FIM" in nome or "FINAL" in nome
        ):
            valor = (
                payload.get("data_final")
                or payload.get("DATA_FINAL")
                or payload.get("datafinal")
                or payload.get("DATAFINAL")
                or payload.get("pdata_final")
                or payload.get("PDATA_FINAL")
            )
            return self._parse_date_value(valor) if valor else date.today()

        return None

    def _expandir_binds_para_sql(
        self,
        binds_base: Dict[str, Any],
        sql: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        binds_expandidos = dict(binds_base)
        nomes_sql = self._extract_sql_param_names(sql)

        mapa_case_insensitive = {
            str(chave).strip().upper(): valor
            for chave, valor in binds_base.items()
        }

        for nome_sql in nomes_sql:
            nome_upper = str(nome_sql).strip().upper()

            if nome_sql not in binds_expandidos and nome_upper in mapa_case_insensitive:
                binds_expandidos[nome_sql] = mapa_case_insensitive[nome_upper]
                continue

            if nome_sql not in binds_expandidos:
                valor_default = self._valor_default_por_nome_sql(nome_sql, payload)
                if valor_default is not None:
                    binds_expandidos[nome_sql] = valor_default

        return binds_expandidos

    def _montar_parametros_execucao(
        self,
        parametros_detectados: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = payload or {}
        binds: Dict[str, Any] = {}

        for parametro in parametros_detectados:
            original_name = str(parametro.get("original_name") or "").strip()
            inferred_type = parametro.get("inferred_type")
            default_value = parametro.get("default_value")

            if not original_name:
                continue

            valor = self._buscar_parametro_payload(payload, original_name)

            if valor in (None, ""):
                semantic_key = str(parametro.get("semantic_key") or "").strip()
                if semantic_key and semantic_key in payload:
                    valor = payload.get(semantic_key)

            if valor in (None, ""):
                valor = default_value

            valor_final = self._coerce_param_value(valor, inferred_type)

            if valor_final is not None:
                binds[original_name] = valor_final

        empresa_id = self._resolver_empresa_id(payload)

        aliases = {
            "empresa": empresa_id,
            "EMPRESA": empresa_id,
            "empresa_id": empresa_id,
            "EMPRESA_ID": empresa_id,
            "pempresa": empresa_id,
            "PEMPRESA": empresa_id,
            "pvendedor": 0,
            "PVENDEDOR": 0,
            "ptipo": payload.get("analise") or payload.get("ANALISE") or "GRUPO",
            "PTIPO": payload.get("analise") or payload.get("ANALISE") or "GRUPO",
            "tipodata": payload.get("tipo_data") or payload.get("TIPO_DATA") or "EMISSAO",
            "TIPODATA": payload.get("tipo_data") or payload.get("TIPO_DATA") or "EMISSAO",
        }

        data_inicial = (
            payload.get("data_inicial")
            or payload.get("DATA_INICIAL")
            or payload.get("datainicial")
            or payload.get("DATAINICIAL")
        )
        data_final = (
            payload.get("data_final")
            or payload.get("DATA_FINAL")
            or payload.get("datafinal")
            or payload.get("DATAFINAL")
        )

        if data_inicial:
            aliases["pdata_inicial"] = self._parse_date_value(data_inicial)
            aliases["PDATA_INICIAL"] = self._parse_date_value(data_inicial)

        if data_final:
            aliases["pdata_final"] = self._parse_date_value(data_final)
            aliases["PDATA_FINAL"] = self._parse_date_value(data_final)

        for chave, valor in aliases.items():
            if chave not in binds and valor is not None:
                binds[chave] = valor

        return binds

    def _normalizar_linha_resultado(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalizada: Dict[str, Any] = {}

        for chave, valor in row.items():
            if isinstance(valor, Decimal):
                normalizada[chave] = float(valor)
            elif isinstance(valor, datetime):
                normalizada[chave] = valor.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(valor, date):
                normalizada[chave] = valor.strftime("%Y-%m-%d")
            else:
                normalizada[chave] = valor

        return normalizada

    def _serializar_default_value(self, valor: Any) -> Any:
        if isinstance(valor, date) and not isinstance(valor, datetime):
            return valor.isoformat()
        return valor

    def _serializar_binds_para_json(self, binds: Dict[str, Any]) -> Dict[str, Any]:
        return {
            k: v.isoformat() if isinstance(v, date) and not isinstance(v, datetime) else v
            for k, v in binds.items()
        }

    def _indexar_queries(self, queries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        mapa: Dict[str, Dict[str, Any]] = {}

        for query in queries:
            nome = str(query.get("name") or "").strip().upper()
            user_name = str(query.get("user_name") or "").strip().upper()

            if nome:
                mapa[nome] = query
            if user_name:
                mapa[user_name] = query

        return mapa

    def _obter_query_por_nomes(
        self,
        queries_index: Dict[str, Dict[str, Any]],
        nomes: List[str],
    ) -> Optional[Dict[str, Any]]:
        for nome in nomes:
            chave = str(nome).strip().upper()
            if chave in queries_index:
                query = queries_index[chave]
                sql_text = str(query.get("sql_text") or query.get("sql") or "").strip()
                if sql_text:
                    return query
        return None

    def _executar_query_dict(
        self,
        query: Dict[str, Any],
        binds_base: Dict[str, Any],
        payload: Dict[str, Any],
        limit: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        sql_text = self._strip_sql_comments(
            str(query.get("sql_text") or query.get("sql") or "")
        )

        if not sql_text:
            raise HTTPException(status_code=400, detail="Query sem SQL utilizável.")

        binds = self._expandir_binds_para_sql(binds_base, sql_text, payload)
        result = self.db.execute(text(sql_text), binds)
        rows = result.mappings().all()

        if limit and int(limit) > 0:
            rows = rows[: int(limit)]

        linhas = [self._normalizar_linha_resultado(dict(row)) for row in rows]
        colunas = list(linhas[0].keys()) if linhas else []

        return linhas, colunas

    def _to_float(self, valor: Any) -> float:
        if valor is None:
            return 0.0

        if isinstance(valor, Decimal):
            return float(valor)

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = str(valor).strip()
        if not texto:
            return 0.0

        try:
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            return float(texto)
        except (TypeError, ValueError):
            return 0.0

    def _montar_resumo_dre(
        self,
        linhas_topo: List[Dict[str, Any]],
        linhas_detalhe: List[Dict[str, Any]],
        linhas_indicadores: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        linha_topo = linhas_topo[0] if linhas_topo else {}
        linha_ind = linhas_indicadores[0] if linhas_indicadores else {}

        faturamento_bruto = 0.0
        devolucoes = 0.0
        custo_mercadoria_devolvida = 0.0
        custo_mercadoria_vendida = 0.0
        lucro_bruto = 0.0

        for chave, valor in linha_topo.items():
            chave_norm = str(chave).strip().lower()

            if "faturamento" in chave_norm or "venda_revenda" in chave_norm:
                faturamento_bruto = self._to_float(valor)
            elif "devolu" in chave_norm:
                devolucoes = self._to_float(valor)
            elif "custo" in chave_norm and "devolv" in chave_norm:
                custo_mercadoria_devolvida = self._to_float(valor)
            elif (
                "custo" in chave_norm
                and "devolv" not in chave_norm
                and ("vendida" in chave_norm or "mercadoria" in chave_norm)
            ):
                custo_mercadoria_vendida = self._to_float(valor)
            elif "lucro" in chave_norm and "bruto" in chave_norm:
                lucro_bruto = self._to_float(valor)

        grupos_unicos: Dict[str, float] = {}
        for linha in linhas_detalhe:
            codigo = str(linha.get("plano_conta_principal") or "").strip()
            total_grupo = self._to_float(linha.get("total_por_grupo"))

            if codigo and codigo not in grupos_unicos:
                grupos_unicos[codigo] = total_grupo

        despesas_totais = sum(grupos_unicos.values())
        lucro_liquido = lucro_bruto - despesas_totais

        rel_desp_x_receita = 0.0
        rentabilidade_sobre_vendas = 0.0

        for chave, valor in linha_ind.items():
            chave_norm = str(chave).strip().lower()

            if "rel" in chave_norm and "desp" in chave_norm and "receita" in chave_norm:
                rel_desp_x_receita = self._to_float(valor)

            if "rent" in chave_norm and "venda" in chave_norm:
                rentabilidade_sobre_vendas = self._to_float(valor)

        if rel_desp_x_receita == 0 and faturamento_bruto > 0:
            rel_desp_x_receita = (despesas_totais / faturamento_bruto) * 100

        if rentabilidade_sobre_vendas == 0 and faturamento_bruto > 0:
            rentabilidade_sobre_vendas = (lucro_liquido / faturamento_bruto) * 100

        return {
            "faturamento_bruto": round(faturamento_bruto, 2),
            "devolucoes": round(devolucoes, 2),
            "custo_mercadoria_devolvida": round(custo_mercadoria_devolvida, 2),
            "custo_mercadoria_vendida": round(custo_mercadoria_vendida, 2),
            "lucro_bruto": round(lucro_bruto, 2),
            "despesas_totais": round(despesas_totais, 2),
            "lucro_liquido_prejuizo": round(lucro_liquido, 2),
            "relacao_despesa_receita": round(rel_desp_x_receita, 2),
            "rentabilidade_sobre_vendas": round(rentabilidade_sobre_vendas, 2),
            "grupos_analiticos": len(grupos_unicos),
        }

    def _preview_dre_composto(
        self,
        cdarquivo: int,
        parsed: Dict[str, Any],
        payload: Dict[str, Any],
        parametros_detectados: List[Dict[str, Any]],
        limit: int,
    ) -> Dict[str, Any]:
        queries = parsed.get("queries", []) or []
        queries_index = self._indexar_queries(queries)

        binds_base = self._montar_parametros_execucao(parametros_detectados, payload)
        empresa_id = self._resolver_empresa_id(payload)

        query_topo = self._obter_query_por_nomes(
            queries_index,
            self._query_dre_topo_por_empresa(empresa_id),
        )
        query_detalhe = self._obter_query_por_nomes(
            queries_index,
            self._query_dre_detalhe_por_empresa(empresa_id),
        )
        query_indicadores = self._obter_query_por_nomes(
            queries_index,
            self._query_dre_indicadores_por_empresa(empresa_id),
        )

        if not query_topo:
            raise HTTPException(
                status_code=400,
                detail="Query do topo do DRE não encontrada.",
            )

        if not query_detalhe:
            raise HTTPException(
                status_code=400,
                detail="Query analítica do DRE não encontrada.",
            )

        if not query_indicadores:
            raise HTTPException(
                status_code=400,
                detail="Query de indicadores do DRE não encontrada.",
            )

        linhas_topo, colunas_topo = self._executar_query_dict(
            query=query_topo,
            binds_base=binds_base,
            payload=payload,
            limit=1,
        )

        linhas_detalhe, colunas_detalhe = self._executar_query_dict(
            query=query_detalhe,
            binds_base=binds_base,
            payload=payload,
            limit=limit,
        )

        linhas_indicadores, colunas_indicadores = self._executar_query_dict(
            query=query_indicadores,
            binds_base=binds_base,
            payload=payload,
            limit=1,
        )

        resumo = self._montar_resumo_dre(
            linhas_topo=linhas_topo,
            linhas_detalhe=linhas_detalhe,
            linhas_indicadores=linhas_indicadores,
        )

        return {
            "cdarquivo": cdarquivo,
            "nome_query": query_detalhe.get("name") or query_detalhe.get("user_name"),
            "nome_query_resumo": query_topo.get("name") or query_topo.get("user_name"),
            "nome_query_indicadores": query_indicadores.get("name") or query_indicadores.get("user_name"),
            "empresa_id_resolvida": empresa_id,
            "modo_relatorio": "dre_composto",
            "colunas": colunas_detalhe,
            "linhas": linhas_detalhe,
            "total_registros": len(linhas_detalhe),
            "parametros_usados": self._serializar_binds_para_json(binds_base),
            "parametros_detectados": [
                {
                    **param,
                    "default_value": self._serializar_default_value(param.get("default_value")),
                }
                for param in parametros_detectados
            ],
            "observacoes": parsed.get("observacoes", []),
            "resumo": resumo,
            "resumo_origem": {
                "colunas": colunas_topo,
                "linhas": linhas_topo,
            },
            "indicadores_origem": {
                "colunas": colunas_indicadores,
                "linhas": linhas_indicadores,
            },
            "analitico": {
                "colunas": colunas_detalhe,
                "linhas": linhas_detalhe,
            },
        }

    def preview_relatorio(
        self,
        cdarquivo: int,
        payload: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        payload = payload or {}

        info = self._parse_relatorio(cdarquivo)
        parsed = info["parsed"]
        queries = parsed.get("queries", []) or []
        parametros_detectados = parsed.get("parameters_detected", []) or []

        if int(cdarquivo) == 12140306:
            try:
                return self._preview_dre_composto(
                    cdarquivo=cdarquivo,
                    parsed=parsed,
                    payload=payload,
                    parametros_detectados=parametros_detectados,
                    limit=limit,
                )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Erro ao executar preview do relatório: {str(exc)}",
                )

        query_principal = self._escolher_query_principal(cdarquivo, queries)
        sql_text = self._strip_sql_comments(
            str(query_principal.get("sql_text") or query_principal.get("sql") or "")
        )

        if not sql_text:
            raise HTTPException(
                status_code=400,
                detail="A query principal do relatório está vazia",
            )

        binds_base = self._montar_parametros_execucao(parametros_detectados, payload)
        binds = self._expandir_binds_para_sql(binds_base, sql_text, payload)

        try:
            result = self.db.execute(text(sql_text), binds)
            rows = result.mappings().all()

            if limit and int(limit) > 0:
                rows = rows[: int(limit)]

            linhas = [self._normalizar_linha_resultado(dict(row)) for row in rows]
            colunas = list(linhas[0].keys()) if linhas else []

            return {
                "cdarquivo": cdarquivo,
                "nome_query": query_principal.get("name") or query_principal.get("user_name"),
                "modo_relatorio": self._modo_preferido_por_relatorio(cdarquivo),
                "colunas": colunas,
                "linhas": linhas,
                "total_registros": len(linhas),
                "parametros_usados": self._serializar_binds_para_json(binds),
                "parametros_detectados": [
                    {
                        **param,
                        "default_value": self._serializar_default_value(param.get("default_value")),
                    }
                    for param in parametros_detectados
                ],
                "observacoes": parsed.get("observacoes", []),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao executar preview do relatório: {str(exc)}",
            )

    def opcoes_relatorio(
        self,
        cdarquivo: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}

        info = self._parse_relatorio(cdarquivo)
        parsed = info["parsed"]
        queries = parsed.get("queries", []) or []
        parametros_detectados = parsed.get("parameters_detected", []) or []

        binds_base = self._montar_parametros_execucao(parametros_detectados, payload)

        opcoes: Dict[str, Any] = {
            "modo_relatorio": self._modo_preferido_por_relatorio(cdarquivo),
            "parametros_detectados": [
                {
                    **param,
                    "default_value": self._serializar_default_value(param.get("default_value")),
                }
                for param in parametros_detectados
            ],
            "defaults": self._serializar_binds_para_json(binds_base),
            "queries_opcoes": {},
            "erros": [],
        }

        for query in queries:
            nome_query = str(query.get("name") or query.get("user_name") or "").strip()
            sql_text = self._strip_sql_comments(
                str(query.get("sql_text") or query.get("sql") or "")
            )

            if not nome_query or not sql_text:
                continue

            try:
                binds_query = self._expandir_binds_para_sql(
                    binds_base,
                    sql_text,
                    payload,
                )
                result = self.db.execute(text(sql_text), binds_query)
                rows = result.mappings().all()[:200]
                linhas = [self._normalizar_linha_resultado(dict(row)) for row in rows]

                opcoes["queries_opcoes"][nome_query] = {
                    "colunas": list(linhas[0].keys()) if linhas else [],
                    "linhas": linhas,
                    "total_registros": len(linhas),
                    "parametros": self._parametros_unicos_query(query),
                }

            except Exception as exc:
                opcoes["erros"].append(
                    {
                        "query": nome_query,
                        "erro": str(exc),
                    }
                )
                continue

        return opcoes