from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Any, List, Dict
import logging
from app.models.saas import SyncJob, Tenant

logger = logging.getLogger(__name__)

class SyncService:
    # Mapeamento de tabelas e suas chaves primárias (além do tenant_id)
    # Isso é usado para o ON CONFLICT no PostgreSQL
    TABLE_PK_MAP = {
        "TB_EMPRESA": ["EMP_ID"],
        "TB_PESSOA": ["PES_ID"],
        "TB_CLIENTE": ["CLI_PESSOA"],
        "TB_VENDEDOR": ["VDR_PESSOA"],
        "TB_CIDADE": ["CID_ID"],
        "TB_PEDIDO_VENDA": ["PEV_ID"],
        "TB_PEDIDO_VENDA_ITEM": ["PEVI_ID"],
        "TB_PRODUTO": ["PRD_ID"],
        "TB_PRODUTO_ESTOQUE": ["PRDE_PRODUTO", "PRDE_EMPRESA"], # Estoque costuma ser por empresa
        "TB_RECEBIMENTO": ["REC_ID"],
        "TB_PAGAMENTO": ["PAG_ID"],
        "TB_AUDITORIA": ["AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA"],
        "TB_USUARIO": ["USU_ID"],
        "TB_COLABORADOR": ["COL_PESSOA"],
        "TB_PROD_GRUPO": ["PGRU_ID"],
        "TB_PROD_MARCA": ["PMAR_ID"],
        "TB_ESPECIE_MOEDA": ["ESP_ID"],
        "TB_PEDIDO_VENDA_FIN": ["PEVF_PEDIDO_VENDA", "PEVF_ID"]
    }

    @staticmethod
    def process_sync_data(db: Session, cnpj: str, data_type: str, content: Any):
        """
        Processa os dados recebidos do agente e salva no PostgreSQL de forma genérica.
        """
        tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj).first()
        if not tenant:
            logger.error(f"Tenant não encontrado para o CNPJ: {cnpj}")
            return False

        job = SyncJob(
            tenant_id=tenant.id,
            status="RUNNING",
            table_name=data_type,
            started_at=datetime.now()
        )
        db.add(job)
        db.commit()

        try:
            # Se for uma das tabelas do ERP Mirror
            if data_type in SyncService.TABLE_PK_MAP:
                SyncService._sync_generic_table(db, tenant.id, data_type, content)
            
            # Legado: Suporte aos tipos antigos se necessário
            elif data_type == "VENDAS" and isinstance(content, dict):
                vendas = content.get("vendas_diarias", [])
                SyncService._sync_generic_table(db, tenant.id, "sync_vendas_diarias", vendas, legacy_pk=["data_venda"])
            
            elif data_type == "USUARIOS" and isinstance(content, list):
                # Converte o formato do agente para o formato da nova TB_USUARIO se necessário
                SyncService._sync_generic_table(db, tenant.id, "TB_USUARIO", content)
                
            else:
                # Tenta processar como tabela genérica mesmo que não esteja no mapa (usando ID como default)
                logger.info(f"Processando tipo desconhecido {data_type} como tabela genérica")
                SyncService._sync_generic_table(db, tenant.id, data_type, content)

            job.status = "COMPLETED"
            job.finished_at = datetime.now()
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            # Tenta pegar o ID se o objeto tenant existir
            t_id = tenant.id if 'tenant' in locals() and tenant else "DESCONHECIDO"
            logger.error(f"Erro ao processar sync {data_type} para o tenant {t_id}: {e}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(error_trace)
            
            with open("sync_error.txt", "a", encoding="utf-8") as f:
                f.write(f"\\n--- ERRO EM {data_type} ---\\n{error_trace}\\n")
            
            job.status = "FAILED"
            job.error_message = str(e)
            job.finished_at = datetime.now()
            db.commit()
            return False

    @staticmethod
    def _sync_generic_table(db: Session, tenant_id: str, table_name: str, rows: List[Dict], legacy_pk: List[str] = None):
        """
        Executa um UPSERT genérico em qualquer tabela.
        """
        if not rows or not isinstance(rows, list):
            return

        # Identifica as colunas do primeiro registro
        sample_row = rows[0]
        columns = list(sample_row.keys())
        if "tenant_id" not in columns:
            columns.append("tenant_id")

        # Identifica PKs para o ON CONFLICT
        pks = legacy_pk or SyncService.TABLE_PK_MAP.get(table_name, ["ID"])
        pks_with_tenant = ["tenant_id"] + pks
        
        # Deduplica o lote antes de inserir para evitar "ON CONFLICT ... cannot affect row a second time"
        unique_rows = []
        seen_pks = set()
        for row in rows:
            # Garante que tenant_id esteja presente
            if "tenant_id" not in row:
                row["tenant_id"] = tenant_id
            
            # Cria uma tupla com os valores da PK para identificar duplicatas
            pk_values = tuple(row.get(pk) for pk in pks_with_tenant)
            if pk_values not in seen_pks:
                unique_rows.append(row)
                seen_pks.add(pk_values)
        
        rows = unique_rows
        if not rows:
            return
        
        # Garante a existência da tabela (Dynamic Schema)
        field_defs = []
        for col in columns:
            col_upper = col.upper()
            if col == "tenant_id":
                field_defs.append(f'"{col}" TEXT NOT NULL')
            elif any(suffix in col_upper for suffix in ["VALOR", "TOTAL", "QUANTIDADE", "PRECO", "ESTOQUE", "CUSTO"]):
                field_defs.append(f'"{col}" NUMERIC(18,4)')
            elif any(suffix in col_upper for suffix in ["_DT_", "DATA"]):
                field_defs.append(f'"{col}" TIMESTAMP')
            else:
                field_defs.append(f'"{col}" TEXT')
                
        pk_cols = ", ".join([f'"{c}"' for c in pks_with_tenant])
        fields_sql = ",\n            ".join(field_defs)
        
        create_sql = text(f"""
        CREATE TABLE IF NOT EXISTS public."{table_name}" (
            {fields_sql},
            PRIMARY KEY ({pk_cols})
        );
        """)
        
        # Como o bulk insert é muito rápido, precisamos criar a tabela e fazer commit isolado primeiro
        db.execute(create_sql)
        db.commit()
        
        # Constrói o SQL do INSERT
        col_names = ", ".join([f'"{c}"' for c in columns])
        placeholders = ", ".join([f":{c}" for c in columns])
        
        # Constrói o SET do UPDATE (todas as colunas menos as PKs)
        update_cols = [c for c in columns if c not in pks_with_tenant]
        if not update_cols: # Se todas as colunas forem PKs, apenas faz o insert ou ignora
            set_clause = f'"{columns[0]}" = EXCLUDED."{columns[0]}"'
        else:
            set_clause = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in update_cols])
            
        conflict_cols = ", ".join([f'"{c}"' for c in pks_with_tenant])

        sql = text(f"""
            INSERT INTO public."{table_name}" ({col_names})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols}) 
            DO UPDATE SET {set_clause};
        """)

        # O pg8000 executa executemany linha a linha, o que causa timeout na nuvem.
        # Vamos construir uma string SQL de Bulk Insert (Fast Insert).
        
        chunk_size = 500
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            
            # Constrói os placeholders múltiplos: (:col_0, :col_1), (:col_2, :col_3)...
            values_clauses = []
            flat_params = {}
            
            for row_idx, row in enumerate(chunk):
                row_placeholders = []
                for col in columns:
                    param_key = f"{col}_{row_idx}"
                    row_placeholders.append(f":{param_key}")
                    
                    if col == "tenant_id":
                        val = str(tenant_id)
                    else:
                        val = row.get(col)
                        # Sanitização Robusta
                        if isinstance(val, str) and val.strip() == "":
                            val = None
                        elif isinstance(val, float) and val.is_integer():
                            val = int(val)
                            
                    flat_params[param_key] = val
                    
                values_clauses.append(f"({', '.join(row_placeholders)})")
                
            all_values_sql = ", ".join(values_clauses)
            
            bulk_sql = text(f"""
                INSERT INTO public."{table_name}" ({col_names})
                VALUES {all_values_sql}
                ON CONFLICT ({conflict_cols}) 
                DO UPDATE SET {set_clause};
            """)
            
            db.execute(bulk_sql, flat_params)
            db.commit()

        logger.info(f"[SYNC] {table_name}: {len(rows)} registros sincronizados.")



