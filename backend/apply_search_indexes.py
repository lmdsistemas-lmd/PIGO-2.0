from app.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Aplicando Índices de Busca Textual ===")
    
    # Índices para buscas por nome/fantasia/descrição
    indices = [
        ('TB_PESSOA', ['tenant_id', 'PES_RSOCIAL_NOME']),
        ('TB_PESSOA', ['tenant_id', 'PES_FANTASIA_APELIDO']),
        ('TB_PRODUTO', ['tenant_id', 'PRD_DESCRICAO']),
    ]
    
    for table, cols in indices:
        idx_name = f"idx_{table.lower()}_search_{cols[-1].lower()}"
        cols_sql = ", ".join([f'"{c}"' for c in cols])
        
        # Usamos btree para busca exata e prefixo, ou poderíamos usar gin/trgm para busca parcial (LIKE %...%)
        # Para simplificar agora, btree resolve o tenant_id + prefixo do nome.
        sql = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON public."{table}" ({cols_sql});'
        print(f"Criando índice {idx_name}...")
        db.execute(text(sql))
    
    db.commit()
    print("=== Índices de Busca Aplicados! ===")
finally:
    db.close()
