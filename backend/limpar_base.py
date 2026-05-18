import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# URL do banco - Mesma que usamos no backend
DATABASE_URL = "postgresql+pg8000://postgres.jnzagndbpkddfbbwjbal:asd1254%26%25%24%23asd123@aws-1-us-west-1.pooler.supabase.com:5432/postgres"
CNPJ_PARA_LIMPAR = "58253989000125"

def limpar():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Busca o ID da empresa pelo CNPJ
        res = session.execute(text("SELECT id FROM tenants WHERE cnpj = :cnpj"), {"cnpj": CNPJ_PARA_LIMPAR}).fetchone()
        if not res:
            print(f"❌ Empresa com CNPJ {CNPJ_PARA_LIMPAR} não encontrada.")
            return
        
        tenant_id = res[0]
        print(f"✅ Localizado Tenant ID: {tenant_id}")

        # 2. Limpa as tabelas de sincronismo para este tenant
        print("🧹 Limpando dados sincronizados...")
        session.execute(text("DELETE FROM sync_vendas_diarias WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM sync_erp_users WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM sync_financeiro_stats WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM sync_jobs WHERE tenant_id = :tid"), {"tid": tenant_id})
        
        session.commit()
        print(f"🚀 LIMPEZA CONCLUÍDA! O CNPJ {CNPJ_PARA_LIMPAR} está zerado.")

    except Exception as e:
        print(f"💥 Erro ao limpar: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    limpar()
