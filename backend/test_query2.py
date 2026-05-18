import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres'))
cur = engine.connect()

sql = text('SELECT COUNT(*) FROM public."TB_PEDIDO_VENDA" PV WHERE PV.tenant_id = :tenant_id AND PV."PEV_EMPRESA" = :empresa_id')

try:
    print('INT:', cur.execute(sql, {'tenant_id': '8291b2d4-c9e0-4b35-85b9-ab6d3a0bbf50', 'empresa_id': 1}).fetchone())
except Exception as e:
    print('INT ERROR:', e)

try:
    print('STR:', cur.execute(sql, {'tenant_id': '8291b2d4-c9e0-4b35-85b9-ab6d3a0bbf50', 'empresa_id': '1'}).fetchone())
except Exception as e:
    print('STR ERROR:', e)
