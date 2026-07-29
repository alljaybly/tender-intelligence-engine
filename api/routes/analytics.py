from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..routes.auth import get_current_user

from ..services.analytics_service import (
    get_analytics_summary,
    get_analytics_dashboard,
    get_extraction_scorecard,
    get_performance_metrics,
    get_trends,
    export_analytics_csv,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def analytics_summary(days: int = Query(30, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    return await get_analytics_summary(days)


@router.get("/dashboard")
async def analytics_dashboard(days: int = Query(30, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    return await get_analytics_dashboard(days)


@router.get("/extraction-scorecard")
async def analytics_extraction_scorecard(days: int = Query(30, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    return await get_extraction_scorecard(days)


@router.get("/performance")
async def analytics_performance(days: int = Query(30, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    return await get_performance_metrics(days)


@router.get("/trends")
async def analytics_trends(days: int = Query(365, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    return await get_trends(days)


@router.get("/export/csv")
async def analytics_export_csv(days: int = Query(30, ge=1, le=3650), current_user: dict = Depends(get_current_user)):
    csv_data = await export_analytics_csv(days)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=platform_analytics_{days}d.csv"},
    )
