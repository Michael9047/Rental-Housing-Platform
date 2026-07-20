"""评价系统 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin, require_tenant
from app.models.review import ReviewStatus
from app.models.user import User, UserRole
from app.schemas.review import (
    ReviewAggregation,
    ReviewCreate,
    ReviewPublic,
    ReviewRead,
    ReviewUpdate,
)
from app.services.review_service import ReviewService

router = APIRouter()


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_in: ReviewCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
):
    """租客创建评价"""
    svc = ReviewService(session)
    try:
        review = await svc.create(current_user.id, review_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return review


@router.get("/property/{property_id}", response_model=list[ReviewPublic])
async def list_property_reviews(
    property_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """房源评价列表（公开）"""
    svc = ReviewService(session)
    return await svc.get_by_property(property_id, skip=skip, limit=limit)


@router.get("/property/{property_id}/stats", response_model=ReviewAggregation)
async def property_review_stats(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """房源评价聚合统计"""
    svc = ReviewService(session)
    return await svc.aggregate_by_property(property_id)


@router.get("/landlord/{landlord_id}", response_model=list[ReviewPublic])
async def list_landlord_reviews(
    landlord_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """个人房东评价列表（公开）"""
    svc = ReviewService(session)
    return await svc.get_by_landlord(landlord_id, skip=skip, limit=limit)


@router.get("/landlord/{landlord_id}/stats", response_model=ReviewAggregation)
async def landlord_review_stats(
    landlord_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """个人房东评价聚合统计"""
    svc = ReviewService(session)
    return await svc.aggregate_by_landlord(landlord_id)


@router.get("/my", response_model=list[ReviewRead])
async def my_reviews(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
):
    """我的评价历史"""
    svc = ReviewService(session)
    return await svc.get_my_reviews(current_user.id, skip=skip, limit=limit)


@router.get("/{review_id}", response_model=ReviewRead)
async def get_review(
    review_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """查看单条评价详情"""
    svc = ReviewService(session)
    review = await svc.get(review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    # 只有本人或管理员可查看非公开状态的评价
    if review.status != ReviewStatus.approved:
        if current_user.id != review.tenant_id and current_user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return review


@router.patch("/{review_id}/status", response_model=ReviewRead)
async def moderate_review(
    review_id: int,
    body: ReviewUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    """管理员审核评价"""
    svc = ReviewService(session)
    review = await svc.update_status(review_id, body.status)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review
