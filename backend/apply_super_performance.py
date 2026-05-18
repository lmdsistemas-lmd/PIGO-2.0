from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Aplicando Índices de Cobertura (Performance Máxima) ===")
    
    # Índices compostos para acelerar agrupamentos e filtros do dashboard
    queries = [
        # Vendas: Tenant + Empresa + Data + Valor (Índice de Cobertura)
        'CREATE INDEX IF NOT EXISTS "idx_pev_perf_faturamento" ON public."TB_PEDIDO_VENDA" ("tenant_id", "PEV_EMPRESA", "PEV_DT_FATURAMENTO", "PEV_STATUS", "PEV_VALOR_TOTAL");',
        'CREATE INDEX IF NOT EXISTS "idx_pev_perf_lancamento" ON public."TB_PEDIDO_VENDA" ("tenant_id", "PEV_EMPRESA", "PEV_DT_LANCAMENTO", "PEV_STATUS", "PEV_VALOR_TOTAL");',
        'CREATE INDEX IF NOT EXISTS "idx_pev_perf_emissao" ON public."TB_PEDIDO_VENDA" ("tenant_id", "PEV_EMPRESA", "PEV_DT_EMISSAO", "PEV_STATUS", "PEV_VALOR_TOTAL");',
        
        # Itens: Tenant + Empresa + Pedido (Join rápido)
        'CREATE INDEX IF NOT EXISTS "idx_pevi_perf_pedido" ON public."TB_PEDIDO_VENDA_ITEM" ("tenant_id", "PEVI_PEDIDO_VENDA", "PEVI_EMPRESA");',
        
        # Financeiro: Tenant + Empresa + Vencimento + Valor
        'CREATE INDEX IF NOT EXISTS "idx_rec_perf_vencimento" ON public."TB_RECEBIMENTO" ("tenant_id", "REC_EMPRESA", "REC_DT_VENCIMENTO", "REC_ABERTO", "REC_VALOR");',
        'CREATE INDEX IF NOT EXISTS "idx_pag_perf_vencimento" ON public."TB_PAGAMENTO" ("tenant_id", "PAG_EMPRESA", "PAG_DT_VENCIMENTO", "PAG_ABERTO", "PAG_VALOR");'
    ]
    
    for sql in queries:
        print(f"Executando: {sql[:50]}...")
        db.execute(text(sql))
    
    db.commit()
    print("=== Super-Índices Aplicados! ===")
finally:
    db.close()
