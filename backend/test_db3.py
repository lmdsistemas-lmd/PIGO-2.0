import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres'))
cur = engine.connect()

sql = text('SELECT "PEV_STATUS", "PEV_DT_FATURAMENTO", COUNT(*) FROM public."TB_PEDIDO_VENDA" WHERE "PEV_STATUS" <> \'C\' GROUP BY 1, 2 LIMIT 20')
print(cur.execute(sql).fetchall())
