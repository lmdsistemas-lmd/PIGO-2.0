import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres'))
cur = engine.connect()

print("STATUS COUNT:", cur.execute(text('SELECT "PEV_STATUS", COUNT(*) FROM public."TB_PEDIDO_VENDA" GROUP BY 1')).fetchall())
