from fastapi import APIRouter

from app.api.v1.routes import admin, auth, bookings, chat, contracts, favorites, geocoding, health, images, imports, map_routes, notifications, payments, pois, properties, users, wechat

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(images.router, prefix="/properties", tags=["images"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(imports.router, prefix="/import", tags=["import"])
api_router.include_router(wechat.router, tags=["wechat"])
api_router.include_router(geocoding.router, tags=["geo"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(pois.router, prefix="/pois", tags=["pois"])
api_router.include_router(map_routes.router, prefix="/map", tags=["map"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
