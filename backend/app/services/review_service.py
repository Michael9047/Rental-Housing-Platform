"""评价服务 — 创建、查询、聚合、审核"""
import logging
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.property import Property
from app.models.review import Review, ReviewStatus
from app.models.user import User
from app.schemas.review import ReviewCreate

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, tenant_id: int, review_in: ReviewCreate) -> Review:
        """租客创建评价。

        规则：
        - 必须与房源有 approved/completed 的 booking
        - 每个 booking 只能评价一次
        - 公寓机构（institute_id 不为空）→ landlord 评分可空
        - 个人房东（institute_id 为空）→ landlord 评分必填
        """
        # 验证 booking 存在且属于该租客
        booking = await self.session.get(Booking, review_in.booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.tenant_id != tenant_id:
            raise ValueError("This booking does not belong to you")
        if booking.status not in (BookingStatus.approved, BookingStatus.completed):
            raise ValueError("评价仅限已确认或已完成的租赁")

        # 检查是否已评价
        existing = await self.session.execute(
            select(Review).where(Review.booking_id == review_in.booking_id)
        )
        if existing.scalars().first():
            raise ValueError("该租赁已评价过，每个 booking 只能评价一次")

        # 获取房源信息，判断房东类型
        property_obj = await self.session.get(Property, booking.property_id)
        if not property_obj:
            raise ValueError("Property not found")

        is_institute = property_obj.institute_id is not None

        # 个人房东必须填写 landlord 评分
        if not is_institute:
            if review_in.landlord_rating is None:
                raise ValueError("个人房东房源需要填写房东评分")
            if review_in.landlord_rating < 1 or review_in.landlord_rating > 5:
                raise ValueError("房东评分需在 1-5 之间")

        review = Review(
            tenant_id=tenant_id,
            property_id=booking.property_id,
            landlord_id=booking.landlord_id,
            booking_id=review_in.booking_id,
            property_rating=review_in.property_rating,
            property_comment=review_in.property_comment,
            property_images=review_in.property_images,
            landlord_rating=review_in.landlord_rating,
            landlord_comment=review_in.landlord_comment,
            landlord_images=review_in.landlord_images,
            status=ReviewStatus.pending,
        )
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def get_by_property(
        self, property_id: int, skip: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取房源已审核评价列表"""
        stmt = (
            select(Review, User.username)
            .join(User, Review.tenant_id == User.id)
            .where(
                Review.property_id == property_id,
                Review.status == ReviewStatus.approved,
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                **self._to_dict(r),
                "tenant_name": username,
                "property_title": None,
            }
            for r, username in result
        ]

    async def get_by_landlord(
        self, landlord_id: int, skip: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取个人房东已审核评价列表（仅返回有 landlord_rating 的评价）"""
        stmt = (
            select(Review, User.username)
            .join(User, Review.tenant_id == User.id)
            .where(
                Review.landlord_id == landlord_id,
                Review.status == ReviewStatus.approved,
                Review.landlord_rating.isnot(None),
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                **self._to_dict(r),
                "tenant_name": username,
                "property_title": None,
            }
            for r, username in result
        ]

    async def get_my_reviews(
        self, tenant_id: int, skip: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取我的评价历史"""
        stmt = (
            select(Review, Property.title)
            .join(Property, Review.property_id == Property.id)
            .where(Review.tenant_id == tenant_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                **self._to_dict(r),
                "tenant_name": None,
                "property_title": title,
            }
            for r, title in result
        ]

    async def get(self, review_id: int) -> Review | None:
        return await self.session.get(Review, review_id)

    async def update_status(self, review_id: int, status: ReviewStatus) -> Review | None:
        review = await self.session.get(Review, review_id)
        if not review:
            return None
        review.status = status
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def aggregate_by_property(self, property_id: int) -> dict[str, Any]:
        """房源评价聚合：平均分 + 评价数"""
        stmt = (
            select(
                func.avg(Review.property_rating).label("avg_rating"),
                func.count(Review.id).label("cnt"),
            )
            .where(
                Review.property_id == property_id,
                Review.status == ReviewStatus.approved,
            )
        )
        result = await self.session.execute(stmt)
        row = result.first()
        avg_rating = float(row.avg_rating) if row and row.avg_rating else None
        cnt = row.cnt if row else 0
        return {
            "property_id": property_id,
            "avg_property_rating": avg_rating,
            "total_reviews": cnt,
        }

    async def aggregate_by_landlord(self, landlord_id: int) -> dict[str, Any]:
        """个人房东评价聚合"""
        stmt = (
            select(
                func.avg(Review.landlord_rating).label("avg_rating"),
                func.count(Review.id).label("cnt"),
            )
            .where(
                Review.landlord_id == landlord_id,
                Review.status == ReviewStatus.approved,
                Review.landlord_rating.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        row = result.first()
        avg_rating = float(row.avg_rating) if row and row.avg_rating else None
        cnt = row.cnt if row else 0
        return {
            "landlord_id": landlord_id,
            "avg_landlord_rating": avg_rating,
            "total_reviews": cnt,
        }

    @staticmethod
    def _to_dict(review: Review) -> dict[str, Any]:
        return {
            "id": review.id,
            "tenant_id": review.tenant_id,
            "property_id": review.property_id,
            "landlord_id": review.landlord_id,
            "booking_id": review.booking_id,
            "property_rating": review.property_rating,
            "property_comment": review.property_comment,
            "property_images": review.property_images,
            "landlord_rating": review.landlord_rating,
            "landlord_comment": review.landlord_comment,
            "landlord_images": review.landlord_images,
            "status": review.status,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }
