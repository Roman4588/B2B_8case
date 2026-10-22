from io import BytesIO

import pytest
from app.documents import extract, parse_runbooks
from reportlab.pdfgen.canvas import Canvas


def test_extracts_sixty_page_pdf():
    data = BytesIO()
    pdf = Canvas(data)
    for page in range(60):
        pdf.drawString(50, 750, f"If disk is full on host {page}, archive old logs.")
        pdf.showPage()
    pdf.save()
    text = extract(data.getvalue(), ".pdf")
    assert "host 59" in text
    assert text.count("archive old logs") == 60


def test_if_then_instructions_and_json():
    result = parse_runbooks("Если заполнен диск → Проверить место; Архивировать логи", ".txt")
    assert result[0]["condition"] == "заполнен диск"
    assert result[0]["steps"] == ["Проверить место", "Архивировать логи"]
    with pytest.raises(ValueError):
        parse_runbooks('[{"title":"no condition"}]', ".json")


def test_rejects_corrupt_pdf_and_unsupported_format():
    with pytest.raises(ValueError):
        extract(b"not a PDF", ".pdf")
    with pytest.raises(ValueError):
        extract(b"shell", ".exe")
