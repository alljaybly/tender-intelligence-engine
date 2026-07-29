from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get('/health')
def health():
    return JSONResponse({'status': 'ok', 'services': ['extract', 'validate', 'price', 'doc']})


@router.get('/health')
def root_health():
    return JSONResponse({'status': 'ok', 'services': ['extract', 'validate', 'price', 'doc']})
