import asyncio
import os
from datetime import datetime
from app.database.connection import SessionLocal
from app.models.saas import User, Tenant
from app.database.erp_connection import current_cnpj
from app.services.dashboard_vendas_service import DashboardVendasService

async def main():
    db = SessionLocal()
    tenant = db.query(Tenant).filter_by(cnpj='58253989000125').first()
    current_cnpj.set('58253989000125')
    service = DashboardVendasService()
    try:
        result = service.get_dashboard_vendas(period='este_ano', start=None, end=None, empresa_id=1)
        import json
        print('RESULT:', json.dumps(result, indent=2))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
