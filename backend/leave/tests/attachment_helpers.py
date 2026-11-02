from io import BytesIO

from pypdf import PdfWriter


def valid_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    return content.getvalue()
