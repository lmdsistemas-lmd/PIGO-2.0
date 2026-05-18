from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Aplicando Índices de Alta Performance ===")
    
    # Lista de tabelas e colunas que precisam de índices para filtros rápidos
    indices = [
        # Pedidos (Filtro por Tenant + Empresa + Data)
        ('TB_PEDIDO_VENDA', ['tenant_id', 'PEV_EMPRESA', 'PEV_DT_LANCAMENTO']),
        ('TB_PEDIDO_VENDA_ITEM', ['tenant_id', 'PEVI_PEDIDO_VENDA']),
        
        # Financeiro (Filtro por Tenant + Empresa + Data)
        ('TB_RECEBIMENTO', ['tenant_id', 'REC_EMPRESA', 'REC_DT_VENCIMENTO']),
        ('TB_RECEBIMENTO', ['tenant_id', 'REC_EMPRESA', 'REC_DT_EMISSAO']),
        ('TB_PAGAMENTO', ['tenant_id', 'PAG_EMPRESA', 'PAG_DT_VENCIMENTO']),
        
        # Estoque (Filtro por Tenant + Empresa)
        ('TB_PRODUTO_ESTOQUE', ['tenant_id', 'PRDE_EMPRESA', 'PRDE_PRODUTO']),
        ('TB_PRODUTO', ['tenant_id', 'PRD_EMPRESA', 'PRD_STATUS']),
    ]
    
    for table, cols in indices:
        idx_name = f"idx_{table.lower()}_{cols[-1].lower()}"
        cols_sql = ", ".join([f'"{c}"' for c in cols])
        
        sql = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON public."{table}" ({cols_sql});'
        print(f"Criando índice {idx_name}...")
        db.execute(text(sql))
    
    db.commit()
    print("=== Índices Aplicados com Sucesso! ===")
finally:
    db.close()
