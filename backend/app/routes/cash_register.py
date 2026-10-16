from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.routes.auth import get_current_user
from app.services.cash_register_service import CashRegisterService

router = APIRouter(prefix="/cash-register", tags=["Caixa"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def service(company: str, user: dict, db: Session):
    return CashRegisterService(db, str(user.get("tenant_id") or ""), company)

@router.get("/closings")
def closings(company: str, startDate: date|None=None, endDate: date|None=None, status: str|None=None,
             cashAccount: str|None=None, userId: str|None=None, difference: str|None=None,
             search: str|None=None, page: int=Query(1,ge=1), pageSize: int=Query(25,ge=1,le=100),
             user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).list_closings(start=startDate,end=endDate,status=status,cash_account=cashAccount,
        user=userId,difference=difference,search=search,page=page,page_size=pageSize)

@router.get("/closings/{closing_id}")
def closing(closing_id: str, company: str, user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).get_closing(closing_id)

@router.get("/closings/{closing_id}/movements")
def movements(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(25,ge=1,le=100),
              user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).movements(closing_id,page,pageSize)

@router.get("/closings/{closing_id}/sales")
def sales(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(50,ge=1,le=100),
          user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).sales(closing_id,page,pageSize)

@router.get("/closings/{closing_id}/products")
def products(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(50,ge=1,le=100),
             user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).products(closing_id,page,pageSize)

@router.get("/closings/{closing_id}/receipts")
def receipts(closing_id: str, company: str, user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).unavailable_documents(closing_id,"receipts")

@router.get("/closings/{closing_id}/payments")
def payments(closing_id: str, company: str, user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).unavailable_documents(closing_id,"payments")

@router.get("/closings/{closing_id}/withdrawals")
def withdrawals(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(50,ge=1,le=100),
                user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).movements_by_kind(closing_id,"withdrawals",page,pageSize)

@router.get("/closings/{closing_id}/supplies")
def supplies(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(50,ge=1,le=100),
             user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).movements_by_kind(closing_id,"supplies",page,pageSize)

@router.get("/closings/{closing_id}/cancelled-sales")
def cancelled_sales(closing_id: str, company: str, page: int=Query(1,ge=1), pageSize: int=Query(50,ge=1,le=100),
                    user=Depends(get_current_user), db: Session=Depends(get_db)):
    return service(company,user,db).cancelled_sales(closing_id,page,pageSize)
