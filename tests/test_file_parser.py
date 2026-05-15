import io

import pytest

from app.utils.file_parser import (
    get_supported_extensions,
    parse_file,
    parse_md,
    parse_pdf,
    parse_txt,
)


class TestParseTxt:
    def test_parse_txt_basic(self):
        result = parse_txt("notes.txt", b"hello world")
        assert result.filename == "notes.txt"
        assert result.file_type == "txt"
        assert result.plain_text == "hello world"

    def test_parse_txt_chinese(self):
        result = parse_txt("doc.txt", "你好，世界！".encode("utf-8"))
        assert result.plain_text == "你好，世界！"


class TestParseMd:
    def test_parse_md_basic(self):
        result = parse_md("readme.md", b"# Title\n\nSome text.")
        assert result.filename == "readme.md"
        assert result.file_type == "md"
        assert "# Title" in result.plain_text

    def test_parse_md_markdown_extension(self):
        result = parse_md("notes.markdown", b"content")
        assert result.file_type == "md"


class TestParsePdf:
    def test_parse_pdf_extracts_text(self):
        from fpdf import FPDF

        buf = io.BytesIO()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, text="Project Orion Secret", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(200, 10, text="Code: Aegis-2026-Omega", new_x="LMARGIN", new_y="NEXT")
        pdf.output(buf)
        raw_bytes = buf.getvalue()

        result = parse_pdf("secret.pdf", raw_bytes)
        assert result.file_type == "pdf"
        assert "Project Orion Secret" in result.plain_text
        assert "Aegis-2026-Omega" in result.plain_text


class TestParseFileDispatch:
    def test_dispatch_txt(self):
        result = parse_file("doc.txt", b"hi")
        assert result.file_type == "txt"

    def test_dispatch_md(self):
        result = parse_file("doc.md", b"# hi")
        assert result.file_type == "md"

    def test_dispatch_markdown(self):
        result = parse_file("doc.markdown", b"hi")
        assert result.file_type == "md"

    def test_dispatch_pdf(self):
        from fpdf import FPDF

        buf = io.BytesIO()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, text="test", new_x="LMARGIN", new_y="NEXT")
        pdf.output(buf)

        result = parse_file("doc.pdf", buf.getvalue())
        assert result.file_type == "pdf"
        assert "test" in result.plain_text

    def test_dispatch_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            parse_file("image.png", b"data")

    def test_dispatch_case_insensitive(self):
        result = parse_file("DOC.TXT", b"hi")
        assert result.file_type == "txt"


class TestGetSupportedExtensions:
    def test_includes_txt(self):
        assert ".txt" in get_supported_extensions()

    def test_includes_md(self):
        assert ".md" in get_supported_extensions()

    def test_includes_pdf(self):
        assert ".pdf" in get_supported_extensions()
