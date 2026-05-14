import io
from typing import NamedTuple


class ParsedFile(NamedTuple):
    filename: str
    file_type: str
    plain_text: str


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


def parse_file(filename: str, raw_bytes: bytes) -> ParsedFile:
    name_lower = filename.lower()

    if name_lower.endswith(".txt"):
        return parse_txt(filename, raw_bytes)
    elif name_lower.endswith((".md", ".markdown")):
        return parse_md(filename, raw_bytes)
    elif name_lower.endswith(".pdf"):
        return parse_pdf(filename, raw_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}. Supported: .txt, .md, .pdf")


def get_supported_extensions() -> list[str]:
    return [".txt", ".md", ".markdown", ".pdf"]
