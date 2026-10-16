from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Aplicando Índices Funcionais (Gráficos Instantâneos) ===")
    
    queries = [
        # Índice para o Histórico de Vendas (Agrupamento por Ano e Mês)
        'CREATE INDEX IF NOT EXISTS "idx_pev_func_mes" ON public."TB_PEDIDO_VENDA" (EXTRACT(YEAR FROM "PEV_DT_LANCAMENTO"), EXTRACT(MONTH FROM "PEV_DT_LANCAMENTO"));',
        
        # Índice para o Gráfico de Faixa Horária
        'CREATE INDEX IF NOT EXISTS "idx_pev_func_hora" ON public."TB_PEDIDO_VENDA" (EXTRACT(HOUR FROM "PEV_DT_LANCAMENTO"));',
        
        # Índice para o Gráfico de Dia da Semana
        'CREATE INDEX IF NOT EXISTS "idx_pev_func_dow" ON public."TB_PEDIDO_VENDA" (EXTRACT(WEEKDAY FROM "PEV_DT_LANCAMENTO"));',
        
        # Otimização adicional para buscas por CNPJ/Tenant nas tabelas principais
        'CREATE INDEX IF NOT EXISTS "idx_tenant_generic" ON public."SyncJob" ("tenant_id", "status");'
    ]
    
    for sql in queries:
        try:
            print(f"Executando: {sql[:60]}...")
            db.execute(text(sql))
        except Exception as e:
            print(f"Aviso ao criar índice (pode ser sintaxe específica): {e}")
    
    db.commit()
    print("=== Índices Funcionais Aplicados! ===")
finally:
    db.close()
