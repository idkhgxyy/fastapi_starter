import io
from typing import NamedTuple, Optional


class ParsedFile(NamedTuple):
    filename: str
    file_type: str
    plain_text: str


# Office 2003 老格式：没有任何纯 Python 解析方案，LibreOffice 又太大（400MB+），
# 所以识别到后直接给出可操作的提示，而不是笼统的 "Unsupported file type"。
LEGACY_OFFICE_HINTS = {
    ".doc": ".docx",
    ".ppt": ".pptx",
}


def legacy_office_error_message(filename: str) -> Optional[str]:
    """是老格式就返回可操作的提示文案，否则返回 None。

    上传接口和 parse_file 共用：接口层用它在白名单校验之前拦截，否则用户只会
    看到笼统的 "Unsupported file type"，根本不知道该另存为什么格式。
    """
    name_lower = filename.lower()
    for legacy_ext, target_ext in LEGACY_OFFICE_HINTS.items():
        if name_lower.endswith(legacy_ext):
            return (
                f"{legacy_ext} 是 Office 2003 老格式，纯 Python 无法解析（需要 LibreOffice，"
                f"体积过大不适合本项目）。请用 Office/WPS 另存为 {target_ext} 后重新上传。"
            )
    return None


def parse_txt(filename: str, raw_bytes: bytes) -> ParsedFile:
    text = raw_bytes.decode("utf-8")
    return ParsedFile(filename=filename, file_type="txt", plain_text=text)


def parse_md(filename: str, raw_bytes: bytes) -> ParsedFile:
    text = raw_bytes.decode("utf-8")
    return ParsedFile(filename=filename, file_type="md", plain_text=text)


def parse_pdf(filename: str, raw_bytes: bytes) -> ParsedFile:
    from pypdf import PdfReader

    pdf_file = io.BytesIO(raw_bytes)
    reader = PdfReader(pdf_file)

    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text.strip())

    text = "\n\n".join(pages)
    return ParsedFile(filename=filename, file_type="pdf", plain_text=text)


def parse_docx(filename: str, raw_bytes: bytes) -> ParsedFile:
    """提取段落与表格文本，保持它们在正文中出现的顺序。

    python-docx 的 `doc.paragraphs` 不包含表格里的文字，必须单独遍历表格；
    但如果先输出全部段落再输出表格，原文顺序会被打乱（备考资料这类层级
    结构明显的内容尤其明显），所以这里按 body 子元素顺序迭代。
    """
    from docx import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = DocxDocument(io.BytesIO(raw_bytes))
    parts: list[str] = []

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, document).text.strip()
            if text:
                parts.append(text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, document).rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))

    return ParsedFile(filename=filename, file_type="docx", plain_text="\n\n".join(parts))


def parse_pptx(filename: str, raw_bytes: bytes) -> ParsedFile:
    """按页提取文本框、表格与演讲者备注，页标题保留为 Markdown 小标题。"""
    from pptx import Presentation

    presentation = Presentation(io.BytesIO(raw_bytes))
    slides: list[str] = []

    for index, slide in enumerate(presentation.slides, 1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    parts.append(text)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        parts.append(" | ".join(cells))

        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"[备注] {notes}")

        if parts:
            slides.append(f"## 第 {index} 页\n" + "\n".join(parts))

    return ParsedFile(filename=filename, file_type="pptx", plain_text="\n\n".join(slides))


def parse_file(filename: str, raw_bytes: bytes) -> ParsedFile:
    name_lower = filename.lower()

    if name_lower.endswith(".txt"):
        return parse_txt(filename, raw_bytes)
    elif name_lower.endswith((".md", ".markdown")):
        return parse_md(filename, raw_bytes)
    elif name_lower.endswith(".pdf"):
        return parse_pdf(filename, raw_bytes)
    elif name_lower.endswith(".docx"):
        return parse_docx(filename, raw_bytes)
    elif name_lower.endswith(".pptx"):
        return parse_pptx(filename, raw_bytes)

    legacy_message = legacy_office_error_message(filename)
    if legacy_message:
        raise ValueError(legacy_message)

    supported = ", ".join(get_supported_extensions())
    raise ValueError(f"Unsupported file type: {filename}. Supported: {supported}")


def get_supported_extensions() -> list[str]:
    return [".txt", ".md", ".markdown", ".pdf", ".docx", ".pptx"]
