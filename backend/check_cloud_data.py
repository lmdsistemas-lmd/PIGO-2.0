
import os
import sqlalchemy
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres"

engine = create_engine(DATABASE_URL)

def check_data():
    with engine.connect() as conn:
        print("--- Tenants ---")
        try:
            result = conn.execute(text("SELECT id, cnpj, razao_social FROM tenants"))
            for row in result:
                print(row)
        except Exception as e:
            print(f"Error reading tenants: {e}")

        print("\n--- Sales Orders (First 5) ---")
        try:
            # Note: Checking if TB_PEDIDO_VENDA exists and has data
            result = conn.execute(text('SELECT "tenant_id", COUNT(*) FROM "TB_PEDIDO_VENDA" GROUP BY "tenant_id"'))
            for row in result:
                print(row)
        except Exception as e:
            print(f"Error reading TB_PEDIDO_VENDA: {e}")

if __name__ == "__main__":
    check_data()
