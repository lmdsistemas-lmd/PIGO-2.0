from app.schemas.reporting import ReportDefinition
from app.services.report_catalog import ReportCatalog


class ReportQueryBuilder:
    OPERATORS = {"eq": "=", "gte": ">=", "lte": "<="}

    def __init__(self, catalog=None):
        self.catalog = catalog or ReportCatalog()

    def build(self, definition: ReportDefinition, empresa_id: int, limit: int = 50):
        source = self.catalog.source(definition.category, definition.source)
        fields = source["fields"]
        self._validate(definition, source)
        params = {"report_limit": min(limit, 50)}

        if definition.totals:
            selected = [f'{fields[key]["expression"]} AS "{key}"' for key in definition.group_by]
            for total in definition.totals:
                expression = fields[total.field]["expression"]
                selected.append(f'{total.aggregation.upper()}({expression}) AS "{total.field}_{total.aggregation}"')
        else:
            selected = [f'{fields[key]["expression"]} AS "{key}"' for key in definition.fields]

        where = []
        if "company" in fields:
            params["report_company"] = str(empresa_id)
            where.append(f'{fields["company"]["expression"]} = :report_company')
        for index, item in enumerate(definition.filters):
            filter_meta = source["filters"][item.field]
            expression = fields[filter_meta["field"]]["expression"]
            if item.operator == "between":
                if not isinstance(item.value, (list, tuple)) or len(item.value) != 2:
                    raise ValueError(f"Filtro {item.field} exige duas datas/valores.")
                params[f"filter_{index}_start"], params[f"filter_{index}_end"] = item.value
                where.append(f"{expression} BETWEEN :filter_{index}_start AND :filter_{index}_end")
            elif item.operator == "in":
                if not isinstance(item.value, list) or not item.value:
                    raise ValueError(f"Filtro {item.field} exige uma lista não vazia.")
                binds = []
                for value_index, value in enumerate(item.value):
                    key = f"filter_{index}_{value_index}"
                    params[key] = value
                    binds.append(f":{key}")
                where.append(f"{expression} IN ({', '.join(binds)})")
            else:
                params[f"filter_{index}"] = item.value
                where.append(f"{expression} {self.OPERATORS[item.operator]} :filter_{index}")

        joins = " " + " ".join(source.get("joins", [])) if source.get("joins") else ""
        select_keyword = "SELECT DISTINCT" if source.get("distinct") and not definition.totals else "SELECT"
        sql = f'{select_keyword} {", ".join(selected)} FROM {source["table"]} {source["alias"]}{joins}'
        if where:
            sql += f' WHERE {" AND ".join(where)}'
        if definition.totals and definition.group_by:
            sql += " GROUP BY " + ", ".join(fields[key]["expression"] for key in definition.group_by)
        if definition.order_by:
            allowed_aliases = set(definition.fields) | {f"{total.field}_{total.aggregation}" for total in definition.totals}
            orders = []
            for item in definition.order_by:
                if item.field not in allowed_aliases:
                    raise ValueError(f"Ordenação não disponível: {item.field}.")
                orders.append(f'"{item.field}" {item.direction.upper()}')
            sql += " ORDER BY " + ", ".join(orders)
        sql += " LIMIT :report_limit"
        return sql, params

    def validate(self, definition: ReportDefinition) -> None:
        """Valida uma definição sem montar ou executar SQL."""
        source = self.catalog.source(definition.category, definition.source)
        self._validate(definition, source)

    def _validate(self, definition, source):
        fields = source["fields"]
        unknown = set(definition.fields) - set(fields)
        if unknown:
            raise ValueError(f"Campos fora do catálogo: {', '.join(sorted(unknown))}.")
        if set(definition.group_by) - set(source["groupings"]):
            raise ValueError("Agrupamento não permitido para esta fonte.")
        if definition.totals and not definition.group_by:
            pass
        for item in definition.filters:
            meta = source["filters"].get(item.field)
            if not meta or item.operator not in meta["operators"]:
                raise ValueError(f"Filtro não permitido: {item.field}/{item.operator}.")
        for total in definition.totals:
            field = fields.get(total.field)
            if not field or total.aggregation not in field["aggregations"]:
                raise ValueError(f"Total não permitido: {total.field}/{total.aggregation}.")

    def build_filter_options(self, category: str, source_key: str, filter_key: str, empresa_id: int, search: str = ""):
        source = self.catalog.source(category, source_key)
        filter_meta = source["filters"].get(filter_key)
        if not filter_meta or filter_key in {"company", "period"}:
            raise ValueError("Filtro não possui opções dinâmicas.")
        fields = source["fields"]
        value_expression = fields[filter_meta["field"]]["expression"]
        label_expression = fields[filter_meta.get("option_label", filter_meta["field"])]["expression"]
        joins = " " + " ".join(source.get("joins", [])) if source.get("joins") else ""
        params = {"options_limit": 100}
        where = [f"{value_expression} IS NOT NULL"]
        if "company" in fields:
            params["report_company"] = str(empresa_id)
            where.append(f'{fields["company"]["expression"]} = :report_company')
        if search:
            params["options_search"] = f"%{search.strip()}%"
            where.append(f"CAST({label_expression} AS VARCHAR(255)) LIKE :options_search")
        sql = f'SELECT DISTINCT {value_expression} AS "value", {label_expression} AS "label" FROM {source["table"]} {source["alias"]}{joins} WHERE {" AND ".join(where)} ORDER BY "label" LIMIT :options_limit'
        return sql, params
