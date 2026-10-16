"""Reconstrói somente TB_PEDIDO_VENDA_FIN e preserva o espelho anterior."""

from sqlalchemy import inspect, text

from app.database.connection import SessionLocal


SOURCE = "TB_PEDIDO_VENDA_FIN"
BACKUP = "TB_PEDIDO_VENDA_FIN_BACKUP_20260810"


def rebuild() -> None:
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        if inspector.has_table(BACKUP, schema="public"):
            raise RuntimeError(f'O backup public."{BACKUP}" já existe; operação cancelada.')
        if not inspector.has_table(SOURCE, schema="public"):
            raise RuntimeError(f'O espelho public."{SOURCE}" não existe.')
        old_count = db.execute(text(f'SELECT COUNT(*) FROM public."{SOURCE}"')).scalar_one()
        db.execute(text(f'ALTER TABLE public."{SOURCE}" RENAME CONSTRAINT "{SOURCE}_pkey" TO "{BACKUP}_pkey"'))
        db.execute(text(f'ALTER TABLE public."{SOURCE}" RENAME TO "{BACKUP}"'))
        db.execute(text(f'''
            CREATE TABLE public."{SOURCE}" (
                "tenant_id" TEXT NOT NULL,
                "PEVF_EMPRESA" TEXT NOT NULL,
                "PEVF_PEDIDO_VENDA" TEXT NOT NULL,
                "PEVF_SEQUENCIA" TEXT NOT NULL,
                "PEVF_ESPECIE_MOEDA" TEXT,
                "PEVF_VALOR" NUMERIC(18,4),
                "PEVF_TROCO" NUMERIC(18,4),
                "PEVF_VALOR_VENDA" NUMERIC(18,4),
                "PEVF_DT_EMISSAO" TIMESTAMP,
                "PEVF_DT_VECTO" TIMESTAMP,
                "PEVF_USUARIO" TEXT,
                "PEVF_DT_LANCAMENTO" TIMESTAMP,
                "PEVF_MOVIMENTAR" TEXT,
                "PEVF_CAIXA" TEXT,
                "PEVF_FECHAMENTO" TEXT,
                PRIMARY KEY (
                    "tenant_id", "PEVF_EMPRESA",
                    "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA"
                )
            )
        '''))
        db.commit()
        backup_count = db.execute(text(f'SELECT COUNT(*) FROM public."{BACKUP}"')).scalar_one()
        new_count = db.execute(text(f'SELECT COUNT(*) FROM public."{SOURCE}"')).scalar_one()
        if backup_count != old_count or new_count != 0:
            raise RuntimeError(f"Validação falhou: anterior={old_count}, backup={backup_count}, novo={new_count}")
        print(f"old_count={old_count} backup_count={backup_count} new_count={new_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rebuild()
