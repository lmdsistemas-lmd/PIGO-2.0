from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    for table in ['TB_PEDIDO_VENDA_ITEM', 'TB_PEDIDO_VENDA_FIN', 'TB_PEDIDO_VENDA', 'TB_PESSOA', 'TB_ESPECIE_MOEDA']:
        rows = db.execute(text(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}' 
            ORDER BY ordinal_position
        """)).fetchall()
        print(f"\n=== {table} ({len(rows)} colunas) ===")
        for r in rows:
            print(f"  {r[0]:40s} {r[1]}")
finally:
    db.close()
