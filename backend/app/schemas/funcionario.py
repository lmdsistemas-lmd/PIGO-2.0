from pydantic import BaseModel


class FuncionarioCreate(BaseModel):
    col_pessoa: int
    departamento_id: int
    cargo_id: int | None = None


class FuncionarioUpdate(BaseModel):
    departamento_id: int | None = None
    cargo_id: int | None = None