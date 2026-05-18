
import sqlalchemy
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DATABASE_URL)

tables_to_drop = [
    "TB_CLIENTE", "TB_PRODUTO", "TB_PEDIDO_VENDA", "TB_PEDIDO_VENDA_ITEM", 
    "TB_RECEBIMENTO", "TB_PAGAMENTO", "TB_AUDITORIA", "TB_COLABORADOR",
    "TB_PEDIDO_VENDA_FIN", "TB_VENDEDOR", "TB_PESSOA", "TB_CIDADE",
    "TB_PRODUTO_ESTOQUE", "TB_PROD_GRUPO", "TB_PROD_MARCA", "TB_ESPECIE_MOEDA",
    "TB_USUARIO"
]

def drop_all():
    with engine.connect() as conn:
        for table in tables_to_drop:
            print(f"Dropping {table}...")
            conn.execute(text(f'DROP TABLE IF EXISTS public."{table}" CASCADE'))
        conn.commit()
        print("Done.")

if __name__ == "__main__":
    drop_all()
