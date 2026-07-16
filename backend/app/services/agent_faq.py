"""租房 FAQ 工作流知识库 —— 固定问答 + 规则匹配

设计（chips 兜确定性，LLM 分类兜灵活性，弱命中反问兜边界）：
- 每个工作流一条 FaqEntry：chip 文案、同义说法、强/弱匹配正则、答案、页面深链、后续 chips。
- 答案为【占位文案】，上线前必须替换为平台真实政策；未覆盖的政策问题一律引导联系客服，
  绝不让 LLM 编造退款时限/金额等具体规则。
- match_faq() 只做无 LLM 的规则匹配：
    strong  —— 明确问法（点 chip / 同义句 / 强正则）→ 直接走工作流
    weak    —— 只出现主题词（如单独一个"押金"）→ 返回候选，交上层反问确认
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FaqLink:
    label: str
    to: str  # 前端路由路径


@dataclass(frozen=True)
class FaqEntry:
    id: str
    chip: str                      # 快捷按钮文案（点击即精确命中）
    canonical: list[str]           # 同义说法（等价于点 chip）
    strong: re.Pattern             # 强命中：明确在问这件事
    weak: re.Pattern | None        # 弱命中：仅出现主题词，需反问确认
    answer: str                    # 占位答案
    links: list[FaqLink] = field(default_factory=list)
    next_chips: list[str] = field(default_factory=list)  # 答完后追加的建议 chips


_PLACEHOLDER = "（以下为占位说明，正式政策以平台最新规则与合同条款为准；如有疑问请联系客服。）"

FAQ_ENTRIES: list[FaqEntry] = [
    FaqEntry(
        id="find_house",
        chip="如何找房",
        canonical=["怎么找房", "怎么租房", "租房流程", "找房流程"],
        strong=re.compile(r"(如何|怎么|怎样|咋).{0,4}(找房|租房)|((租房|找房).{0,2}(流程|步骤))"),
        weak=None,
        answer=(
            f"{_PLACEHOLDER}\n"
            "在本平台找房有三种方式：\n"
            "1. 搜索房源：按区域、价格、户型直接筛选；\n"
            "2. AI 找房：用一句话描述需求，AI 帮你解析并检索；\n"
            "3. 推荐管家（当前页面）：直接告诉我你的地区、预算和户型，我来推荐并帮你对比。\n"
            "看中的房源可以点「加入购物车」存进候选清单，凑够两套就能一键对比。"
        ),
        links=[FaqLink("去搜索房源", "/search"), FaqLink("试试 AI 找房", "/ai-search")],
        next_chips=["预订流程", "有哪些费用"],
    ),
    FaqEntry(
        id="booking",
        chip="预订流程",
        canonical=["怎么预订", "如何预订", "怎么预约看房", "下单流程"],
        strong=re.compile(r"(如何|怎么|怎样|咋).{0,4}(预订|预约|下单|订房)|((预订|预约|下单).{0,2}(流程|步骤))"),
        weak=re.compile(r"预订|预约"),
        answer=(
            f"{_PLACEHOLDER}\n"
            "预订流程大致是：\n"
            "1. 在房源详情页选择入住日期并提交预订申请；\n"
            "2. 房东确认后，按提示支付押金完成锁房；\n"
            "3. 双方在线签署租赁合同；\n"
            "4. 到「我的预订」可随时查看预订状态和后续步骤。"
        ),
        links=[FaqLink("查看我的预订", "/bookings/tenant")],
        next_chips=["押金怎么退", "合同怎么签"],
    ),
    FaqEntry(
        id="contract",
        chip="合同怎么签",
        canonical=["合同怎么样", "怎么签合同", "如何签约", "合同流程", "合同条款"],
        strong=re.compile(r"(如何|怎么|怎样|咋).{0,4}(签|签约|签合同)|合同.{0,4}(怎么|如何|流程|条款|内容|注意|签)"),
        weak=re.compile(r"合同|签约"),
        answer=(
            f"{_PLACEHOLDER}\n"
            "平台采用在线电子合同：\n"
            "1. 押金支付完成后，系统生成租赁合同草案；\n"
            "2. 请务必核对租期、租金、押金、费用分担等关键条款；\n"
            "3. 双方在线确认签署后合同生效，可随时在「我的预订」中查看合同文本；\n"
            "4. 对条款有疑问时，先与房东沟通或联系平台客服，不要线下另签口头协议。"
        ),
        links=[FaqLink("在我的预订中查看合同", "/bookings/tenant")],
        next_chips=["押金怎么退", "退款政策"],
    ),
    FaqEntry(
        id="deposit",
        chip="押金怎么退",
        canonical=["退押金", "押金退还", "押金什么时候退"],
        strong=re.compile(r"押金.{0,6}(退|返|拿回|回来)|退.{0,2}押金"),
        weak=re.compile(r"押金"),
        answer=(
            f"{_PLACEHOLDER}\n"
            "关于押金退还：\n"
            "1. 租期正常结束、房源验收无损坏后，押金按合同约定原路退回；\n"
            "2. 具体退还时限与扣减规则以你签署的合同条款为准；\n"
            "3. 押金支付与状态可在「我的预订」对应订单中查看；\n"
            "4. 如与房东就扣减金额有争议，请联系平台客服介入。"
        ),
        links=[FaqLink("查看我的预订", "/bookings/tenant")],
        next_chips=["退款政策", "合同怎么签"],
    ),
    FaqEntry(
        id="refund",
        chip="退款政策",
        canonical=["如何退款", "怎么退款", "退款流程", "取消订单退钱吗"],
        strong=re.compile(r"退款|退钱|(取消.{0,6}(订单|预订).{0,6}(退|钱|款))|退租.{0,4}(钱|款)"),
        weak=None,
        answer=(
            f"{_PLACEHOLDER}\n"
            "关于退款：\n"
            "1. 预订被房东拒绝或超时未确认时，已支付款项将原路全额退回；\n"
            "2. 你主动取消预订的，退款比例取决于取消时间与合同/平台规则；\n"
            "3. 退款进度可在「我的预订」订单详情中查看；\n"
            "4. 具体时限和比例以平台正式规则为准，特殊情况请联系客服处理。"
        ),
        links=[FaqLink("查看我的预订", "/bookings/tenant")],
        next_chips=["押金怎么退", "预订流程"],
    ),
    FaqEntry(
        id="fees",
        chip="有哪些费用",
        canonical=["费用明细", "要交什么费用", "服务费怎么收"],
        strong=re.compile(r"(有哪些|要交|收取?|什么|多少).{0,4}费用|费用.{0,2}(明细|构成|标准)|服务费|中介费"),
        weak=re.compile(r"费用"),
        answer=(
            f"{_PLACEHOLDER}\n"
            "常见费用构成：\n"
            "1. 月租金：房源标价，按月支付；\n"
            "2. 押金：锁房与履约保证，退租后按合同退还；\n"
            "3. 服务费：按订单金额的一定比例收取（具体费率见下单页明示）；\n"
            "4. 水电网等生活费用：以房源描述和合同约定为准。\n"
            "所有应付费用都会在支付前明示，不会有隐藏收费。"
        ),
        links=[FaqLink("去看看房源", "/search")],
        next_chips=["预订流程", "退款政策"],
    ),
]

_BY_ID = {e.id: e for e in FAQ_ENTRIES}


def get_faq(faq_id: str) -> FaqEntry | None:
    return _BY_ID.get(faq_id)


def list_faq_chips() -> list[dict]:
    return [{"id": e.id, "chip": e.chip} for e in FAQ_ENTRIES]


def match_faq(message: str) -> tuple[str, list[FaqEntry]]:
    """规则匹配（无 LLM）。

    返回 (强度, 候选列表)：
    - ("strong", [entry])   明确命中单个工作流 → 直接回答
    - ("weak",   entries)   只出现主题词/多个候选 → 上层反问确认
    - ("none",   [])        与 FAQ 无关
    """
    text = message.strip()

    # 1) 点 chip / 同义句 → 精确命中
    for e in FAQ_ENTRIES:
        if text == e.chip or text in e.canonical:
            return "strong", [e]

    # 2) 强正则：明确在问这件事
    strong_hits = [e for e in FAQ_ENTRIES if e.strong.search(text)]
    if len(strong_hits) == 1:
        return "strong", strong_hits
    if len(strong_hits) > 1:
        return "weak", strong_hits  # 同时像多个 → 交上层用 LLM 定夺

    # 3) 弱正则：出现了主题词但问法不在强正则里（如"定房子要哪些费用"）。
    #    注意这里只是"疑似 FAQ"信号，**不代表要反问**——上层会交给 LLM 判断并作答，
    #    只有真正的孤立主题词（见 is_bare_topic）才反问。
    weak_hits = [e for e in FAQ_ENTRIES if e.weak is not None and e.weak.search(text)]
    if weak_hits:
        return "weak", weak_hits

    return "none", []


# 疑问/动词信号：出现任一即说明用户在问一个完整的问题，而不是只丢了个主题词
_QUESTION_SIGNAL = re.compile(
    r"[?？]|怎么|如何|怎样|咋|什么|啥|哪些|哪个|多少|几|能否|可以|能不能|是否|要不要|"
    r"退|交|付|收|签|订|租|办|走|流程|规则|政策|说明|介绍|解释|讲讲|告诉"
)


def is_bare_topic(message: str) -> bool:
    """是否只是一个孤立的主题词（如光打"押金""费用"两个字）。

    只有这种情况才值得反问确认；只要用户带了疑问词/动词（"定房子要哪些费用"），
    就说明问题是明确的，应该直接用 LLM + 知识库作答，而不是机械地让他再点一次按钮。
    """
    text = message.strip().strip("？?。.! ！")
    if len(text) > 6:
        return False
    return not _QUESTION_SIGNAL.search(text)


def faq_kb_text(entry: FaqEntry) -> str:
    """把一条 FAQ 的知识库内容拼成给 LLM 的上下文（答案 + 可跳转页面）"""
    lines = [f"【{entry.chip}】", entry.answer]
    if entry.links:
        lines.append("可引导用户前往的页面：" + "、".join(f"{l.label}({l.to})" for l in entry.links))
    return "\n".join(lines)
