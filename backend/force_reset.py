import sys
import os
from sqlalchemy import create_engine, text

# Adiciona o diretório atual ao sys.path
sys.path.append(os.getcwd())

from app.database.connection import DATABASE_URL
from app.database.base import Base
# Importar todos os modelos para garantir que o metadata os conheça
from app.models.saas import *

def reset_db():
    engine = create_engine(DATABASE_URL)
    print(f"Conectando ao banco para reset total...")
    
    with engine.connect() as conn:
        print("Limpando todas as tabelas do schema public...")
        # Comando radical para limpar tudo no Postgres
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;"))
        conn.commit()
    
    print("Banco de dados resetado com sucesso!")

if __name__ == "__main__":
    reset_db()
