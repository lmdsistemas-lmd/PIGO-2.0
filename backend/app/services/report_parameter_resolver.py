from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import re


@dataclass
class ReportParameter:
    original_name: str
    normalized_name: str
    semantic_key: str
    inferred_type: str
    required: bool = True
    default_value: Any = None
    aliases: List[str] = field(default_factory=list)


class ParameterResolver:
    """
    Resolve parâmetros detectados no SQL para:
    - nome semântico
    - tipo inferido
    - valor padrão
    - bind final usando o nome ORIGINAL do SQL
    """

    DATE_START_KEYS = {
        "DATAINICIAL",
        "DATAINICIO",
        "DTINICIAL",
        "DTINICIO",
        "DTINI",
        "DINI",
        "INICIO",
        "DATAINI",
    }

    DATE_END_KEYS = {
        "DATAFINAL",
        "DATAFIM",
        "DTFINAL",
        "DTFIM",
        "DTF",
        "DFIM",
        "FIM",
        "DATAFIM",
    }

    PREFIXES = (
        "P_",
        "PAR_",
        "PARAM_",
        "REC_",
        "CD_",
        "ID_",
        "NR_",
    )

    def __init__(self, user_context: Optional[Dict[str, Any]] = None):
        self.user_context = user_context or {}

    def normalize_name(self, name: str) -> str:
        name = (name or "").strip().upper()
        name = re.sub(r"[^A-Z0-9_]", "", name)

        changed = True
        while changed:
            changed = False

            for prefix in self.PREFIXES:
                if name.startswith(prefix) and len(name) > len(prefix):
                    rest = name[len(prefix):].lstrip("_")
                    if rest:
                        name = rest
                        changed = True

        return name

    def semantic_key_for(self, original_name: str) -> str:
        raw = (original_name or "").upper().strip()
        norm = self.normalize_name(raw)

        if raw in self.DATE_START_KEYS or norm in self.DATE_START_KEYS:
            return "data_inicial"

        if raw in self.DATE_END_KEYS or norm in self.DATE_END_KEYS:
            return "data_final"

        mapa = {
            "EMPRESA": "empresa",
            "VENDEDOR": "vendedor",
            "CLIENTE": "cliente",
            "NATUREZA": "natureza",
            "FILIAL": "filial",
            "USUARIO": "usuario",
            "USER": "usuario",
            "ROTA": "rota",
            "PRODUTO": "produto",
            "GRUPO": "grupo",
            "MARCA": "marca",
            "CIDADE": "cidade",
            "REGIAO": "regiao",
            "REGIÃO": "regiao",
            "FORNECEDOR": "fornecedor",
            "TIPO": "tipo",
        }

        for chave, valor in mapa.items():
            if chave in raw or norm == chave:
                return valor

        if raw == "PANALISE" or norm == "ANALISE":
            return "analise"

        if raw == "TIPODATA" or norm == "TIPODATA":
            return "tipo_data"

        return norm.lower()

    def infer_type(self, original_name: str) -> str:
        raw = (original_name or "").upper().strip()

        if raw in ("PANALISE", "TIPODATA"):
            return "str"

        if "DATA" in raw or raw in self.DATE_START_KEYS or raw in self.DATE_END_KEYS:
            return "date"

        if any(
            token in raw
            for token in [
                "EMPRESA",
                "VENDEDOR",
                "CLIENTE",
                "FILIAL",
                "COD",
                "ID",
                "NR",
                "ROTA",
                "PRODUTO",
                "GRUPO",
                "MARCA",
                "CIDADE",
                "REGIAO",
                "REGIÃO",
                "FORNECEDOR",
                "NATUREZA",
            ]
        ):
            return "int"

        return "str"

    def default_for(self, semantic_key: str, inferred_type: str) -> Any:
        today = date.today()
        first_day = today.replace(day=1)

        semantic_defaults = {
            "empresa": self.user_context.get("empresa_padrao", 1),
            "vendedor": self.user_context.get("vendedor_padrao", 0),
            "cliente": self.user_context.get("cliente_padrao", 0),
            "natureza": self.user_context.get("natureza_padrao", 0),
            "filial": self.user_context.get("filial_padrao", 0),
            "usuario": self.user_context.get("usuario_id", 0),
            "rota": self.user_context.get("rota_padrao", 0),
            "produto": self.user_context.get("produto_padrao", 0),
            "grupo": self.user_context.get("grupo_padrao", 0),
            "marca": self.user_context.get("marca_padrao", 0),
            "cidade": self.user_context.get("cidade_padrao", 0),
            "regiao": self.user_context.get("regiao_padrao", 0),
            "fornecedor": self.user_context.get("fornecedor_padrao", 0),
            "tipo": self.user_context.get("tipo_padrao", 0),
            "analise": self.user_context.get("analise_padrao", "GRUPO"),
            "tipo_data": self.user_context.get("tipo_data_padrao", "EMISSAO"),
            "data_inicial": first_day.isoformat(),
            "data_final": today.isoformat(),
        }

        if semantic_key in semantic_defaults:
            return semantic_defaults[semantic_key]

        if inferred_type == "int":
            return 0

        if inferred_type == "number":
            return 0

        if inferred_type == "date":
            return today.isoformat()

        return ""

    def build_aliases(self, original_name: str, normalized_name: str, semantic_key: str) -> List[str]:
        aliases = {
            original_name,
            original_name.upper(),
            original_name.lower(),
            normalized_name,
            normalized_name.upper(),
            normalized_name.lower(),
            semantic_key,
            semantic_key.upper(),
            semantic_key.lower(),
        }

        alias_map = {
            "empresa": {"EMPRESA", "REC_EMPRESA", "CD_EMPRESA", "ID_EMPRESA"},
            "data_inicial": {"DATAINICIAL", "DATAINICIO", "DTINICIAL", "DTINICIO", "DTINI"},
            "data_final": {"DATAFINAL", "DATAFIM", "DTFINAL", "DTFIM"},
            "vendedor": {"VENDEDOR", "PVENDEDOR", "CD_VENDEDOR"},
            "cliente": {"CLIENTE", "PCLIENTE", "CD_CLIENTE"},
            "natureza": {"NATUREZA", "PNATUREZA"},
            "filial": {"FILIAL"},
            "usuario": {"USUARIO", "USER"},
            "rota": {"ROTA", "PROTA"},
            "produto": {"PRODUTO", "PPRODUTO"},
            "grupo": {"GRUPO", "PGRUPO"},
            "marca": {"MARCA", "PMARCA"},
            "cidade": {"CIDADE"},
            "regiao": {"REGIAO", "REGIÃO"},
            "fornecedor": {"FORNECEDOR"},
            "tipo": {"TIPO", "PTIPO"},
            "analise": {"PANALISE", "ANALISE"},
            "tipo_data": {"TIPODATA", "TIPO_DATA"},
        }

        aliases.update(alias_map.get(semantic_key, set()))
        return sorted({a for a in aliases if str(a).strip()})

    def describe(self, param_names: List[str]) -> List[ReportParameter]:
        items: List[ReportParameter] = []

        for original_name in param_names:
            normalized_name = self.normalize_name(original_name)
            semantic_key = self.semantic_key_for(original_name)
            inferred_type = self.infer_type(original_name)
            default_value = self.default_for(semantic_key, inferred_type)
            aliases = self.build_aliases(original_name, normalized_name, semantic_key)

            items.append(
                ReportParameter(
                    original_name=original_name,
                    normalized_name=normalized_name,
                    semantic_key=semantic_key,
                    inferred_type=inferred_type,
                    required=True,
                    default_value=default_value,
                    aliases=aliases,
                )
            )

        return items

    def _parse_date_value(self, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if isinstance(value, str):
            texto = value.strip()
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

        raise ValueError(f"Valor de data inválido: {value}")

    def coerce_value(self, inferred_type: str, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()

        if value is None or value == "":
            return None

        if inferred_type == "date":
            data = self._parse_date_value(value)
            return data.strftime("%Y-%m-%d")

        if inferred_type == "int":
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float, Decimal)):
                return int(value)
            return int(str(value).strip())

        if inferred_type == "number":
            if isinstance(value, bool):
                return float(int(value))
            if isinstance(value, (int, float, Decimal)):
                return float(value)

            texto = str(value).strip()
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            return float(texto)

        return value

    def resolve(
        self,
        report_params: List[ReportParameter],
        incoming_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        incoming_payload = incoming_payload or {}
        indexed_payload: Dict[str, Any] = {}

        for key, value in incoming_payload.items():
            if key is None:
                continue

            chave = str(key)
            indexed_payload[chave] = value
            indexed_payload[chave.upper()] = value
            indexed_payload[chave.lower()] = value
            indexed_payload[self.normalize_name(chave)] = value

        final_params: Dict[str, Any] = {}

        for param in report_params:
            value_found = None

            for alias in param.aliases:
                if alias in indexed_payload:
                    value_found = indexed_payload[alias]
                    break
                if alias.upper() in indexed_payload:
                    value_found = indexed_payload[alias.upper()]
                    break
                if alias.lower() in indexed_payload:
                    value_found = indexed_payload[alias.lower()]
                    break

            if value_found is None:
                value_found = param.default_value

            try:
                value_found = self.coerce_value(param.inferred_type, value_found)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Valor inválido para parâmetro '{param.original_name}': {exc}"
                ) from exc

            if value_found is not None:
                final_params[param.original_name] = value_found

        return final_params