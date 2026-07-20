"""向数据库插入一条「全规则测试房源」，用于验证租房规则板块。"""
import asyncio
from decimal import Decimal

from app.db.session import async_session_maker
from app.models.property import Property, PropertyType, PropertyStatus, RentType, DepositType
from app.models.user import User

ALL_RULES = {
    "cancellation_policy": (
        "预订确认后不可取消。如因签证拒签、入学资格取消等不可抗力因素需取消预订，"
        "请于入住前至少30天提交书面申请及相关证明，经审核通过后可退还已缴押金的50%。"
        "入住前30天内取消，已支付款项不予退还。建议您在预订前仔细确认行程及入学安排。"
    ),
    "check_out_rules": (
        "退房时间为合同到期日中午12:00前。退房时需完成以下事项："
        "（1）将所有个人物品清空并恢复房间原状；"
        "（2）完成基础清洁（地面清扫、台面擦拭、垃圾清运），如需深度清洁请联系公寓管理处安排付费服务；"
        "（3）归还全部钥匙及门禁卡至前台；"
        "（4）填写退房确认表。退房检查通过后，押金将于7个工作日内原路退还。"
    ),
    "pet_policy": (
        "本房源允许饲养小型宠物（猫、兔、仓鼠等笼养宠物），每户限养一只。"
        "饲养宠物需额外缴纳宠物押金¥500，退房时如无损坏全额退还。"
        "禁止饲养大型犬类及具有攻击性的宠物品种。"
        "宠物主人需负责宠物的卫生及噪音管理，不得影响邻里的正常生活。"
    ),
    "payment_rules": (
        "房费于入住登记时一次性缴纳，支持微信支付、支付宝及银联卡。"
        "平台仅代收押金，押金金额为一个月房租。租期内如无欠费及损坏，押金于退房检查通过后全额退还。"
        "租金发票可于缴费后联系公寓管理处开具。"
    ),
    "check_in_rules": (
        "最早入住时间为合同开始日14:00。入住登记时请携带以下证件原件："
        "（1）有效护照或身份证；（2）录取通知书或学生证；"
        "（3）已签署的租赁合同。前台登记后领取钥匙、门禁卡及入住礼包。"
        "如需提前入住或延迟至18:00后登记，请提前联系公寓管理处安排。"
    ),
    "room_change_rules": (
        "入住后如需换房（更换至同一公寓楼内其他空置房间），"
        "可向公寓管理处提交换房申请表，说明换房原因及偏好房型。"
        "换房审批周期为3-5个工作日。换房成功需支付¥200行政手续费。"
        "新房间租金按实际房型价格调整，多退少补。"
        "每份合同期内限换房一次。"
    ),
    "sublet_rules": (
        "本房源不允许承租人擅自转租或分租。"
        "如因个人原因需短期离开（交换学期、实习等），可向公寓管理处申请临时转租许可，"
        "经审批同意后方可转租给公寓管理处认可的在册学生。"
        "未经许可擅自转租的，公寓方有权终止合同并扣留全部押金。"
    ),
    "early_termination_rules": (
        "租期内提前解约需至少提前60天书面通知公寓管理处。"
        "提前解约违约金为剩余租金的50%。"
        "因学校官方交换项目、重大疾病等正当理由提前解约的，"
        "凭学校证明或医院证明可减免违约金至剩余租金的20%。"
        "解约当月已缴租金按实际入住天数结算，剩余部分退还。"
    ),
    "renewal_rules": (
        "到期续租享有优先权。如需续租，请在合同到期前60天内向公寓管理处提交续租申请。"
        "续租租金以届时公寓公示价格为准，涨幅一般不超过上年租金的5%。"
        "逾期未提交续租申请的，视为放弃优先续租权，房间将重新上架出租。"
        "续租合同期限与原合同一致，如需调整请联系管理处协商。"
    ),
    "guest_policy": (
        "访客停留时间为每日08:00至22:00，过夜访客需提前24小时在前台登记。"
        "每位承租人每月过夜访客累计不超过5晚。"
        "访客需在前台出示有效证件并登记。访客在公寓楼内需遵守与承租人相同的住宿规则。"
        "违反访客规定者，公寓方有权限制其访客权限。"
    ),
    "quiet_hours": (
        "安静时间为每日22:00至次日08:00。安静时间内请："
        "降低电视及音响音量、避免在大厅及走廊大声交谈、"
        "推迟洗衣及吸尘等产生噪音的家务活动。"
        "考试周期间（学校官方考试日历），安静时间提前至20:00开始。"
        "多次被投诉噪音扰民的，公寓方有权发出书面警告，累计三次警告可终止合同。"
    ),
    "smoking_policy": (
        "本公寓楼室内全面禁烟，包括房间内、走廊、电梯及公共休息区。"
        "吸烟请至公寓楼外指定吸烟区。室内吸烟触发烟雾报警器将产生罚款¥2000，"
        "并需赔偿由此造成的消防系统维护费用。违反吸烟规定累计两次以上者，公寓方有权终止合同。"
    ),
    "common_area_rules": (
        "公共区域（厨房、洗衣房、健身房、自习室）24小时开放。"
        "厨房使用后请及时清洗餐具及台面，冰箱内食品请标注姓名及日期；"
        "洗衣房每台设备单次使用限时90分钟，请勿长时间占用；"
        "健身房使用后请擦拭器械，22:00后请勿进行举重等产生噪音的运动；"
        "自习室请保持安静，离开时带走个人物品。"
        "公共区域由公寓保洁每日清洁，大型垃圾请自行带至楼下垃圾房。"
    ),
    "maintenance_rules": (
        "设施故障请通过公寓APP或前台报修，报修后24小时内安排维修人员上门。"
        "紧急情况（水管爆裂、电力故障、门锁损坏）可拨打24小时维修热线，1小时内响应。"
        "自然损耗导致的维修费用由公寓方承担；人为损坏的维修费用由承租人承担。"
        "严禁承租人自行拆卸、改装公寓内设施设备，违规造成的损失由承租人全额赔偿。"
    ),
}


async def seed_test_property():
    async with async_session_maker() as db:
        # 找一个已有的 landlord
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.role == "landlord").limit(1))
        landlord = result.scalar_one_or_none()

        if not landlord:
            # 回退：随便找一个用户
            result = await db.execute(select(User).limit(1))
            landlord = result.scalar_one_or_none()

        if not landlord:
            print("❌ 数据库中没有用户，无法创建测试房源")
            return

        prop = Property(
            landlord_id=landlord.id,
            title="【全规则测试】CBD精装两室一厅·独立卫浴·近地铁",
            description=(
                "这是一条用于前端测试的房源，包含全部14条租房规则。"
                "所有规则均已填写完整的自然语言描述。"
                "此房源仅用于验证租房规则板块的前端展示效果。"
            ),
            address="苏州市工业园区苏州大道西1号CBD国际公寓A座1508",
            district="苏州-工业园区",
            country="CN",
            price_monthly=Decimal("3500"),
            area_sqm=Decimal("75"),
            bedrooms=2,
            bathrooms=1,
            property_type=PropertyType.apartment,
            status=PropertyStatus.available,
            latitude=Decimal("31.3158"),
            longitude=Decimal("120.6698"),
            deposit_amount=3500,
            service_fee_rate=0.10,
            min_lease_months=12,
            max_lease_months=24,
            rent_type=RentType.monthly,
            min_stay_months=6,
            deposit_type=DepositType.one_month,
            amenities=["空调", "WiFi", "洗衣机", "冰箱", "电梯", "独立卫浴", "近地铁", "精装修", "可养宠物"],
            rental_rules=ALL_RULES,
        )

        db.add(prop)
        await db.commit()
        await db.refresh(prop)

        print(f"✅ 测试房源已创建: ID={prop.id}")
        print(f"   标题: {prop.title}")
        print(f"   规则数量: {len(ALL_RULES)} 条全部填写")
        print(f"   查看地址: http://localhost:5173/property/{prop.id}")


if __name__ == "__main__":
    asyncio.run(seed_test_property())
