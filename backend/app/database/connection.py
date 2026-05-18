import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import urllib.parse

# Senha com caracteres especiais tratada
raw_password = "asd1254&%$#asd123"
encoded_password = urllib.parse.quote_plus(raw_password)

DATABASE_URL = f"postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:{encoded_password}@aws-1-us-west-1.pooler.supabase.com:5432/postgres"






# Otimização do Engine para ambiente SaaS (Supabase Pooler)
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Mantém mais conexões prontas
    max_overflow=10,      # Permite expandir se necessário
    pool_pre_ping=True,   # Testa a conexão antes de usar (evita timeouts)
    pool_recycle=3600     # Recicla conexões a cada 1 hora
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependência do DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()