from fastapi import APIRouter, Header, Body, HTTPException, Depends
from typing import Any
import logging
from datetime import datetime
import json
import os
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Sincronismo"])
logger = logging.getLogger(__name__)

# Dependência do Banco de Dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from pydantic import BaseModel

class SyncData(BaseModel):
    cnpj: str
    type: str
    content: Any
    timestamp: str

@router.post("")
async def receive_sync_data(
    data: SyncData,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Recebe dados sincronizados do agente remoto e salva no PostgreSQL Cloud.
    """
    # Log básico
    logger.info(f"[SYNC] Recebendo dados do CNPJ: {data.cnpj} | Tipo: {data.type}")

    # Validação simples do Token (opcional, pode ser expandido)
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"[SYNC] Chamada sem token de autorização do CNPJ: {data.cnpj}")
    
    try:
        # Chama o serviço para processar e salvar no banco
        success = SyncService.process_sync_data(
            db=db,
            cnpj=data.cnpj,
            data_type=data.type,
            content=data.content
        )

        if success:
            logger.info(f"[SYNC] Dados de {data.type} persistidos no Postgres para o CNPJ {data.cnpj}")
            return {
                "success": True, 
                "message": f"Dados de {data.type} processados com sucesso no Cloud",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise Exception("Falha ao persistir dados no banco de dados")
            
    except Exception as e:
        logger.error(f"[SYNC] Erro ao processar sincronismo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

