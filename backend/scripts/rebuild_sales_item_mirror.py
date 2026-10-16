"""Reconstrói somente o espelho TB_PEDIDO_VENDA_ITEM, preservando o original."""

from sqlalchemy import inspect, text

from app.database.connection import SessionLocal


SOURCE = "TB_PEDIDO_VENDA_ITEM"
BACKUP = "TB_PEDIDO_VENDA_ITEM_BACKUP_20260810"


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
                "PEVI_EMPRESA" TEXT NOT NULL,
                "PEVI_PEDIDO_VENDA" TEXT NOT NULL,
                "PEVI_SEQUENCIA" TEXT NOT NULL,
                "PEVI_PRODUTO" TEXT,
                "PEVI_QUANTIDADE" NUMERIC(18,4),
                "PEVI_UN_VENDA" TEXT,
                "PEVI_VALOR_UNITARIO" NUMERIC(18,4),
                "PEVI_VALOR_CUSTO_UNITARIO" NUMERIC(18,4),
                "PEVI_VALOR_DESCONTO" NUMERIC(18,4),
                "PEVI_VALOR_TOTAL" NUMERIC(18,4),
                "PEVI_VALOR_ACRESCIMO" NUMERIC(18,4),
                "PEVI_VALOR_FRETE" NUMERIC(18,4),
                "PEVI_DT_LANCAMENTO" TIMESTAMP,
                PRIMARY KEY (
                    "tenant_id", "PEVI_EMPRESA",
                    "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA"
                )
            )
        '''))
        db.commit()

        backup_count = db.execute(text(f'SELECT COUNT(*) FROM public."{BACKUP}"')).scalar_one()
        new_count = db.execute(text(f'SELECT COUNT(*) FROM public."{SOURCE}"')).scalar_one()
        if backup_count != old_count or new_count != 0:
            raise RuntimeError(
                f"Validação posterior falhou: anterior={old_count}, "
                f"backup={backup_count}, novo={new_count}."
            )
        print(f"old_count={old_count} backup_count={backup_count} new_count={new_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rebuild()
