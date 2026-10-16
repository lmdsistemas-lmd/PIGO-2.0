from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    table = 'TB_PEDIDO_VENDA_ITEM'
    rows = db.execute(text(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}' 
        ORDER BY ordinal_position
    """)).fetchall()
    print(f"\n=== {table} ===")
    for r in rows:
        print(f"  {r[0]}")
finally:
    db.close()
