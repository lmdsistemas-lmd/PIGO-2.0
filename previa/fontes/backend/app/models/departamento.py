from sqlalchemy import Column, Integer, String
from app.database.base import Base

class Departamento(Base):
    __tablename__ = "rh_departamentos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(255), nullable=True)