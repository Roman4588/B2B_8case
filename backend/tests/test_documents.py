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


@pytest.mark.parametrize("extension", [".txt", ".md", ".pdf", ".docx"])
def test_separate_if_then_rules_without_markdown_headings(extension):
    records = parse_runbooks(
        "Если заполнен диск → Проверить место; Согласовать очистку\n"
        "Если упал Nginx → Проверить upstream\nПроверить логи",
        extension,
    )
    assert len(records) == 2
    assert records[0]["steps"] == ["Проверить место", "Согласовать очистку"]
    assert records[1]["condition"] == "упал Nginx"
    assert records[1]["steps"] == ["Проверить upstream", "Проверить логи"]


def test_numbered_english_rules_keep_multiline_actions():
    records = parse_runbooks(
        "1. If disk is full then Check df -h\n2. Archive agreed files\n2. If API is down -> Check upstream",
        ".txt",
    )
    assert len(records) == 2
    assert records[0]["steps"] == ["Check df -h", "Archive agreed files"]
