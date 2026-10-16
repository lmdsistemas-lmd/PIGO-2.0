from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Criando Tabelas Otimizadas Manualmente ===")
    
    # Tabela de Itens com a nova PK PEVI_ID
    db.execute(text("""
    CREATE TABLE IF NOT EXISTS public."TB_PEDIDO_VENDA_ITEM" (
        "PEVI_ID" TEXT NOT NULL,
        "tenant_id" TEXT NOT NULL,
        "PEVI_PEDIDO_VENDA" TEXT,
        "PEVI_EMPRESA" TEXT,
        "PEVI_PRODUTO" TEXT,
        "PEVI_QUANTIDADE" NUMERIC(18,4),
        "PEVI_VALOR_UNITARIO" NUMERIC(18,4),
        "PEVI_VALOR_CUSTO_UNITARIO" NUMERIC(18,4),
        "PEVI_VALOR_TOTAL" NUMERIC(18,4),
        PRIMARY KEY ("tenant_id", "PEVI_ID")
    );
    """))
    
    # Tabela de Financeiro de Pedidos
    db.execute(text("""
    CREATE TABLE IF NOT EXISTS public."TB_PEDIDO_VENDA_FIN" (
        "PEVF_ID" TEXT NOT NULL,
        "tenant_id" TEXT NOT NULL,
        "PEVF_PEDIDO_VENDA" TEXT,
        "PEVF_EMPRESA" TEXT,
        "PEVF_ESPECIE_MOEDA" TEXT,
        "PEVF_VALOR" NUMERIC(18,4),
        PRIMARY KEY ("tenant_id", "PEVF_ID", "PEVF_PEDIDO_VENDA")
    );
    """))
    
    db.commit()
    print("Tabelas criadas! O erro de 'relation does not exist' deve sumir.")
finally:
    db.close()
