from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from app.core.security import decode_access_token
from app.services.pigo_access_service import check_permission,live_local_payload


async def pigo_access_middleware(request,call_next):
    authorization=request.headers.get('Authorization','')
    if request.url.path.startswith('/api/') and authorization.startswith('Bearer '):
        try:payload=decode_access_token(authorization[7:].strip())
        except Exception:payload={}
        if payload.get('auth_source')=='pigo':
            try:
                current=await run_in_threadpool(live_local_payload,payload)
                check_permission(current,request.url.path,request.method)
            except HTTPException as error:
                return JSONResponse(status_code=error.status_code,content={'detail':error.detail})
    return await call_next(request)
