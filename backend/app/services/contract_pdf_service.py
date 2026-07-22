"""合同 PDF 生成服务。

将合同纯文本内容渲染为 PDF 文件，用于邮件附件发送。
使用 weasyprint 将 HTML 模板转为 PDF，支持中文字体。
"""

import logging
import tempfile
from pathlib import Path

from app.models.contract import Contract

logger = logging.getLogger(__name__)

# 合同 HTML 模板 — 简洁排版适合打印/PDF
CONTRACT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2.5cm 2cm;
    @bottom-center {{
      content: "第 " counter(page) " 页";
      font-size: 10px;
      color: #999;
    }}
  }}
  body {{
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "SimSun", sans-serif;
    font-size: 14px;
    line-height: 2;
    color: #333;
  }}
  h1 {{
    text-align: center;
    font-size: 22px;
    margin-bottom: 24px;
  }}
  h2 {{
    font-size: 16px;
    margin-top: 20px;
    margin-bottom: 8px;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
  }}
  .signature-area {{
    margin-top: 40px;
  }}
  .signature-line {{
    display: inline-block;
    width: 45%;
    margin-top: 20px;
  }}
  .signature-line.right {{
    margin-left: 8%;
  }}
  .stamp {{
    margin-top: 20px;
    color: #666;
    font-size: 12px;
  }}
</style>
</head>
<body>

<h1>租赁合同</h1>

<div class="content">
{content_html}
</div>

<div class="signature-area">
  <div class="signature-line">
    <p>甲方（出租方）签字：____________</p>
    <p>日期：____________</p>
  </div>
  <div class="signature-line right">
    <p>乙方（承租方）签字：____________</p>
    <p>日期：____________</p>
  </div>
  <p class="stamp">（签署完成时间：{signed_at}）</p>
</div>

</body>
</html>"""


class ContractPdfService:
    """将合同内容渲染为 PDF 文件。"""

    async def generate(self, contract: Contract) -> bytes:
        """生成合同 PDF，返回二进制内容。

        将合同的纯文本内容转为 HTML → weasyprint 渲染为 PDF。

        Args:
            contract: Contract ORM 对象（需含 content, signed_at 等字段）

        Returns:
            PDF 二进制内容

        Raises:
            ImportError: weasyprint 未安装
            RuntimeError: PDF 生成失败
        """
        # 纯文本 → HTML（保留换行和段落结构）
        content = contract.content or ""
        paragraphs = content.strip().split("\n")
        html_paragraphs = []
        for line in paragraphs:
            line = line.strip()
            if not line:
                html_paragraphs.append("<br>")
            elif line.startswith("第") and ("条" in line):
                html_paragraphs.append(f"<h2>{line}</h2>")
            else:
                html_paragraphs.append(f"<p>{line}</p>")

        signed_at = ""
        if contract.signed_at:
            signed_at = contract.signed_at.strftime("%Y年%m月%d日 %H:%M")

        html = CONTRACT_HTML_TEMPLATE.format(
            content_html="\n".join(html_paragraphs),
            signed_at=signed_at,
        )

        # 写入临时文件 → weasyprint 渲染 → 返回 bytes
        try:
            from weasyprint import HTML

            with tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                tmp.write(html)
                tmp_path = Path(tmp.name)

            try:
                pdf_bytes = HTML(filename=str(tmp_path)).write_pdf()
                logger.info(
                    "合同 PDF 生成成功 contract_id=%s size=%d",
                    contract.id, len(pdf_bytes),
                )
                return pdf_bytes
            finally:
                tmp_path.unlink(missing_ok=True)
        except ImportError:
            logger.error("weasyprint 未安装，无法生成合同 PDF")
            raise
        except Exception as exc:
            logger.exception("合同 PDF 生成失败 contract_id=%s", contract.id)
            raise RuntimeError(f"PDF 生成失败: {exc}") from exc
