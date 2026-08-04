"""兼容桥接 — PropertyImage/RoomImage 表已删除，重定向到 BuildingImage。"""
from app.models.building_image import BuildingImage as PropertyImage, BuildingImage as RoomImage
