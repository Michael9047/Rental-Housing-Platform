"""邮件 HTML 模板渲染。

模板分为两层：
- base.html: 完整 HTML 文档，CSS 样式，用 {{body}} 作为内容占位符
- 各模板: 只有 body 内容 HTML，变量用 {var_name} 格式

渲染流程：先 fill body 模板 → 替换 base 中的 {{body}} → fill base 变量
"""

from datetime import datetime
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent

# 缓存已读取的模板内容
_cache: dict[str, str] = {}


def render(template_name: str, **kwargs) -> str:
    """读取模板文件并填充变量。

    Args:
        template_name: 模板文件名（不含 .html 后缀），如 "welcome"
        **kwargs: 模板变量，常用变量：
            app_name, support_email, current_year（base 层）
            user_name, property_title, ...（业务层）

    Returns:
        渲染后的完整 HTML 字符串
    """
    # 1. 读取 body 模板并填充业务变量
    body_template = _read(template_name + ".html")
    body_html = body_template.format(**kwargs)

    # 2. 读取 base 模板，替换 {{body}} 占位符
    base = _read("base.html")
    html = base.replace("{{body}}", body_html)

    # 3. 填充 base 层变量（提供默认值）
    return html.format(
        app_name=kwargs.get("app_name", "Rental Housing"),
        support_email=kwargs.get("support_email", "support@hengchuanglz.com"),
        current_year=kwargs.get("current_year", str(datetime.utcnow().year)),
    )


def _read(filename: str) -> str:
    """读取模板文件原始内容（带缓存）。"""
    if filename not in _cache:
        path = _TEMPLATE_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"邮件模板不存在: {path}")
        _cache[filename] = path.read_text(encoding="utf-8")
    return _cache[filename]
