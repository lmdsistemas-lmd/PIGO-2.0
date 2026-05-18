from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Verificando Índices Atuais no Postgres ===")
    tables = [
        'TB_PEDIDO_VENDA', 'TB_PEDIDO_VENDA_ITEM', 'TB_RECEBIMENTO', 
        'TB_PAGAMENTO', 'TB_PRODUTO_ESTOQUE', 'TB_PRODUTO'
    ]
    for table in tables:
        rows = db.execute(text(f"""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = '{table}'
        """)).fetchall()
        print(f"\n--- {table} ---")
        for r in rows:
            print(f"  {r[0]}")
finally:
    db.close()
