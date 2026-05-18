import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres'))
cur = engine.connect()

print("COUNT PEDIDO:", cur.execute(text('SELECT COUNT(*) FROM public."TB_PEDIDO_VENDA"')).fetchone())
print("ROWS PEDIDO:", cur.execute(text('SELECT tenant_id, "PEV_EMPRESA", "PEV_DT_FATURAMENTO", "PEV_STATUS" FROM public."TB_PEDIDO_VENDA" LIMIT 5')).fetchall())

print("COUNT ITEM:", cur.execute(text('SELECT COUNT(*) FROM public."TB_PEDIDO_VENDA_ITEM"')).fetchone())
print("ROWS ITEM:", cur.execute(text('SELECT * FROM public."TB_PEDIDO_VENDA_ITEM" LIMIT 5')).fetchall())
