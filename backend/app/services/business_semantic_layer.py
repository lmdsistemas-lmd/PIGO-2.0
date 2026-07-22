from copy import deepcopy


CONCEPTS = {
    "number": {"name": "Número do documento", "description": "Identificador do documento no sistema de origem.", "format": "identifier", "icon": "hash", "color": "slate", "help": "Use para localizar ou conferir um documento específico."},
    "order_number": {"name": "Número do pedido", "description": "Identificador do pedido de venda relacionado ao item.", "format": "identifier", "icon": "receipt", "color": "blue", "help": "Permite rastrear o item até o pedido original."},
    "date": {"name": "Data da venda", "description": "Data de emissão do pedido de venda.", "format": "date", "icon": "calendar", "color": "blue", "help": "Base para filtros e agrupamentos por período."},
    "issue_date": {"name": "Data de emissão", "description": "Data em que o título financeiro foi emitido.", "format": "date", "icon": "calendar", "color": "cyan", "help": "Use para analisar a origem dos recebimentos por período."},
    "due_date": {"name": "Data de vencimento", "description": "Data prevista para vencimento do título.", "format": "date", "icon": "calendar-clock", "color": "amber", "help": "Permite analisar vencimentos e carteira financeira."},
    "registered_at": {"name": "Data de cadastro", "description": "Data em que o cliente foi cadastrado.", "format": "date", "icon": "user-plus", "color": "cyan", "help": "Use para acompanhar novos clientes por período."},
    "customer_id": {"name": "Cliente", "description": "Identificador comercial do cliente.", "format": "identifier", "icon": "user", "color": "violet", "help": "Pode ser usado para filtrar ou agrupar operações do mesmo cliente."},
    "seller_id": {"name": "Vendedor", "description": "Identificador do vendedor responsável.", "format": "identifier", "icon": "briefcase", "color": "indigo", "help": "Use para análises comerciais por responsável."},
    "product_id": {"name": "Código do produto", "description": "Identificador comercial do produto.", "format": "identifier", "icon": "barcode", "color": "emerald", "help": "Código estável usado pelo ERP para identificar o produto."},
    "product": {"name": "Produto", "description": "Descrição comercial do produto.", "format": "text", "icon": "package", "color": "emerald", "help": "Nome apresentado ao usuário nos relatórios de produtos e itens."},
    "name": {"name": "Nome", "description": "Nome ou razão social do cadastro.", "format": "text", "icon": "text", "color": "slate", "help": "Descrição amigável do registro."},
    "trade_name": {"name": "Nome fantasia", "description": "Nome fantasia ou apelido comercial.", "format": "text", "icon": "store", "color": "violet", "help": "Pode estar vazio quando o cadastro possui apenas razão social."},
    "city": {"name": "Cidade", "description": "Cidade vinculada ao cadastro.", "format": "text", "icon": "map-pin", "color": "sky", "help": "Nome resolvido pelo catálogo de cidades, sem expor seu código interno."},
    "group": {"name": "Grupo de produtos", "description": "Grupo comercial ao qual o produto pertence.", "format": "text", "icon": "layers", "color": "orange", "help": "Use para consolidar produtos de uma mesma família."},
    "brand": {"name": "Marca", "description": "Marca comercial do produto.", "format": "text", "icon": "tag", "color": "pink", "help": "A disponibilidade depende do preenchimento da marca no ERP."},
    "status": {"name": "Status", "description": "Situação atual do registro.", "format": "status", "icon": "activity", "color": "slate", "help": "Os valores disponíveis são obtidos diretamente dos dados sincronizados."},
    "open": {"name": "Em aberto", "description": "Indica se o título ainda possui valor em aberto.", "format": "boolean", "icon": "circle", "color": "amber", "help": "S representa aberto e N representa liquidado/fechado."},
    "quantity": {"name": "Quantidade vendida", "description": "Quantidade comercial registrada no item da venda.", "format": "decimal", "icon": "boxes", "color": "blue", "help": "Pode ser somada para medir volume vendido."},
    "total": {"name": "Valor da venda", "description": "Valor líquido registrado na venda ou no item.", "format": "currency", "icon": "currency", "color": "emerald", "help": "Valor comercial já registrado pelo ERP para o documento."},
    "amount": {"name": "Valor do recebimento", "description": "Valor nominal do título a receber.", "format": "currency", "icon": "currency", "color": "emerald", "help": "Representa o valor registrado no título financeiro."},
    "unit_price": {"name": "Preço unitário", "description": "Preço de venda por unidade do item.", "format": "currency", "icon": "currency", "color": "blue", "help": "Preço praticado no item antes da multiplicação pela quantidade."},
    "unit_cost": {"name": "Custo unitário", "description": "Custo registrado por unidade do item.", "format": "currency", "icon": "calculator", "color": "orange", "help": "Use em análises de custo e rentabilidade autorizadas."},
    "sale_price": {"name": "Preço de venda", "description": "Preço de venda atual do cadastro do produto.", "format": "currency", "icon": "currency", "color": "blue", "help": "É preço cadastral, não necessariamente o preço histórico de cada venda."},
    "cost_price": {"name": "Preço de custo", "description": "Custo atual registrado no cadastro do produto.", "format": "currency", "icon": "calculator", "color": "orange", "help": "É custo cadastral e pode diferir do custo histórico do item."},
    "minimum_stock": {"name": "Estoque mínimo", "description": "Quantidade mínima recomendada para reposição.", "format": "decimal", "icon": "warehouse", "color": "amber", "help": "Parâmetro cadastral utilizado no controle de estoque."},
    "company": {"name": "Empresa", "description": "Empresa ERP à qual o registro pertence.", "format": "identifier", "icon": "building", "color": "slate", "help": "Aplicado automaticamente para garantir isolamento por empresa."},
}


class BusinessSemanticLayer:
    def enrich_source(self, category_key: str, source_key: str, source: dict) -> dict:
        enriched = deepcopy(source)
        filter_fields = {meta["field"] for meta in source.get("filters", {}).values()}
        grouping_fields = set(source.get("groupings", []))
        for field_key, field in enriched["fields"].items():
            concept = deepcopy(CONCEPTS.get(field_key, {}))
            semantic_id = f"{category_key}.{source_key}.{field_key}"
            field.update({
                "semantic_id": semantic_id,
                "label": concept.get("name", field.get("label", field_key.replace("_", " ").title())),
                "description": concept.get("description", f"Campo de negócio {field.get('label', field_key)}."),
                "format": concept.get("format", field.get("type", "text")),
                "icon": concept.get("icon", "field"),
                "color": concept.get("color", "slate"),
                "help": concept.get("help", "Disponível conforme os dados sincronizados para a empresa."),
                "can_group": field_key in grouping_fields,
                "can_filter": field_key in filter_fields,
                "can_sort": True,
                "can_total": bool(field.get("aggregations")),
            })
        return enriched

    def public_dictionary(self, catalog: dict) -> list[dict]:
        entries = []
        for category_key, category in catalog.items():
            for source_key, source in category["sources"].items():
                for field_key, field in source["fields"].items():
                    entries.append({"category": category_key, "source": source_key, "field": field_key, **{key: value for key, value in field.items() if key != "expression"}})
        return entries
