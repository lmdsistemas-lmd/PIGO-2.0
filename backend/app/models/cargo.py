from sqlalchemy import Column, Integer, String
from app.database.base import Base

class Cargo(Base):
    __tablename__ = "rh_cargos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(255), nullable=True)