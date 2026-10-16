from fastapi import APIRouter, Depends, HTTPException, status

from app.routes.auth import get_current_user


router = APIRouter(prefix="/rh", tags=["RH Integracao"])


@router.post("/vincular-funcionario")
def vincular_funcionario_erp(
    col_pessoa: int,
    departamento_id: int,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Integracao RH local desativada para evitar gravacao sem tenant_id. "
            "Recriar esta funcionalidade com tabelas multi-tenant antes de usar."
        ),
    )
