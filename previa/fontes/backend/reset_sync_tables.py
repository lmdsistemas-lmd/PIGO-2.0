from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Limpando tabelas para otimização de PK ===")
    db.execute(text('DROP TABLE IF EXISTS public."TB_PEDIDO_VENDA_ITEM" CASCADE'))
    db.execute(text('DROP TABLE IF EXISTS public."TB_PEDIDO_VENDA_FIN" CASCADE'))
    db.commit()
    print("Sucesso! O Agente agora pode recriar as tabelas com performance máxima.")
finally:
    db.close()
