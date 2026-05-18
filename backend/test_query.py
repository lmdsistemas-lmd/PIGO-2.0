import os
import datetime
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres'))
cur = engine.connect()

start_date = datetime.date(2026, 1, 1)
end_date = datetime.date(2026, 12, 31)
empresa_id = 1
tenant_id = '8291b2d4-c9e0-4b35-85b9-ab6d3a0bbf50'

sql = text("""
SELECT CAST(SUM(PV."PEV_VALOR_TOTAL") AS NUMERIC(18,2)) AS TOTAL
FROM "TB_PEDIDO_VENDA" PV
WHERE PV.tenant_id = :tenant_id
  AND PV."PEV_DT_FATURAMENTO" BETWEEN :start_date AND :end_date
  AND PV."PEV_STATUS" <> 'C'
  AND PV."PEV_EMPRESA" = :empresa_id
""")

try:
    print("QUERY RESULT:", cur.execute(sql, {
        "tenant_id": tenant_id,
        "start_date": start_date,
        "end_date": end_date,
        "empresa_id": str(empresa_id)
    }).fetchone())
except Exception as e:
    print("QUERY ERROR:", e)
