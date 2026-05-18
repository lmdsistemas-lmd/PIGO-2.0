from sqlalchemy import Column, Integer, ForeignKey
from app.database.base import Base


class Funcionario(Base):
    __tablename__ = "rh_funcionarios"

    id = Column(Integer, primary_key=True, index=True)

    col_pessoa = Column(Integer, nullable=False, unique=True)

    departamento_id = Column(
        Integer,
        ForeignKey("rh_departamentos.id"),
        nullable=False
    )

    cargo_id = Column(
        Integer,
        ForeignKey("rh_cargos.id"),
        nullable=True
    )