"""API v1 路由注册 — 三层架构"""
from fastapi import APIRouter

from app.api.v1.routes import (
    admin, agent, ai_search, auth, bookings,
    building_staff, buildings, chat, commute, contracts,
    dashboard, favorites, geocoding, health,
    imports, map_routes, ml, notifications, orders,
    payments, pms, pois, repair_workers, repairs,
    properties_compat, rooms, room_transfers, search_suggestions, tenants,
    unit_types, upload, users, wechat,
)

api_router = APIRouter()

# 核心
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

# 三层架构核心
api_router.include_router(buildings.router, tags=["buildings"])

api_router.include_router(unit_types.router, prefix="/unit-types", tags=["unit-types"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(properties_compat.router, tags=["properties-compat"])  # 旧接口兼容

# 配套模块
api_router.include_router(building_staff.router, tags=["building-staff"])
api_router.include_router(tenants.router, tags=["tenants"])
api_router.include_router(orders.router, tags=["orders"])
api_router.include_router(room_transfers.router, tags=["room-transfers"])

# 其他模块
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(imports.router, prefix="/import", tags=["import"])
api_router.include_router(wechat.router, tags=["wechat"])
api_router.include_router(search_suggestions.router, prefix="/search", tags=["search"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(dashboard.router, tags=["dashboard"])

# 以下模块暂不启用（本初版搁置）
# api_router.include_router(ai_search.router, prefix="/ai-search", tags=["ai-search"])
# api_router.include_router(geocoding.router, tags=["geo"])
# api_router.include_router(pois.router, prefix="/pois", tags=["pois"])
api_router.include_router(map_routes.router, prefix="/map", tags=["map"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
# api_router.include_router(ml.router, tags=["ml"])
# api_router.include_router(repairs.router, tags=["repairs"])
# api_router.include_router(repair_workers.router, tags=["repair-workers"])
# api_router.include_router(pms.router, prefix="/pms", tags=["pms"])
# api_router.include_router(commute.router, prefix="/commute", tags=["commute"])
