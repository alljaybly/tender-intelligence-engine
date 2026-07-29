from fastapi import APIRouter

from .process import router as process_router, process_pipeline_router
from .status import router as status_router
from .health import router as health_router
from .payments import router as payments_router
from .match import router as match_router
from .analyze import router as analyze_router
from .upload import router as upload_router
from .scrape import router as scrape_router
from .download_zip import router as download_zip_router
from .pricing import router as pricing_router
from .auth import router as auth_router
from .boq import router as boq_router
from .leads import router as leads_router
from .analytics import router as analytics_router

router = APIRouter()

router.include_router(process_router)
router.include_router(status_router)
router.include_router(health_router)
router.include_router(payments_router)
router.include_router(match_router)
router.include_router(analyze_router)
router.include_router(upload_router)
router.include_router(scrape_router)
router.include_router(download_zip_router)
router.include_router(pricing_router)
router.include_router(auth_router)
router.include_router(boq_router)
router.include_router(process_pipeline_router)
router.include_router(leads_router)
router.include_router(analytics_router)
