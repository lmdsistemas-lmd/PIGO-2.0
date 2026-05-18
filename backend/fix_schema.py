from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Ajustando Esquema do Banco para Multi-Empresa ===")
    
    # 1. Adiciona PEVI_EMPRESA se não existir
    db.execute(text("""
        ALTER TABLE public."TB_PEDIDO_VENDA_ITEM" 
        ADD COLUMN IF NOT EXISTS "PEVI_EMPRESA" TEXT;
    """))
    print("OK: Coluna PEVI_EMPRESA adicionada (ou já existia).")

    # 2. Como mudamos a PK (agora precisa incluir empresa), vamos recriar a PK
    # No Firebird a PK de itens costuma ser (EMPRESA, PEDIDO, PRODUTO...)
    # Vamos simplificar: Se a PK atual não tem empresa, vamos dropar e recriar.
    try:
        db.execute(text("""
            ALTER TABLE public."TB_PEDIDO_VENDA_ITEM" 
            DROP CONSTRAINT IF EXISTS "TB_PEDIDO_VENDA_ITEM_pkey" CASCADE;
            
            ALTER TABLE public."TB_PEDIDO_VENDA_ITEM" 
            ADD PRIMARY KEY ("tenant_id", "PEVI_PEDIDO_VENDA", "PEVI_EMPRESA", "PEVI_PRODUTO", "PEVI_QUANTIDADE", "PEVI_VALOR_UNITARIO");
        """))
        print("OK: PK de TB_PEDIDO_VENDA_ITEM atualizada para incluir Empresa.")
    except Exception as e:
        print(f"Aviso ao atualizar PK: {e}")

    # 3. Ajusta TB_PEDIDO_VENDA_FIN (que estava vazia/sem colunas)
    # Vamos apenas dropar ela para o Agente recriar com o esquema full
    db.execute(text('DROP TABLE IF EXISTS public."TB_PEDIDO_VENDA_FIN" CASCADE;'))
    print("OK: TB_PEDIDO_VENDA_FIN removida para recriação completa pelo Agente.")

    db.commit()
    print("=== Ajustes Finalizados ===")
finally:
    db.close()
