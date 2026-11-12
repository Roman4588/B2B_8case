import json
import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, Field, ValidationError, field_validator

MAX_TEXT_CHARACTERS = 3_000_000
MAX_PDF_PAGE_BYTES = 4 * 1024 * 1024
MAX_PDF_CONTENT_BYTES = 16 * 1024 * 1024


def collect_text(parts, separator="\n"):
    """Enforce the output budget while consuming parts, before joining them."""
    collected, size = [], 0
    for part in parts:
        size += len(part) + (len(separator) if collected else 0)
        if size > MAX_TEXT_CHARACTERS:
            raise ValueError("Документ содержит слишком много текста")
        collected.append(part)
    return separator.join(collected)


def pdf_text(pages):
    decoded_size = 0
    for page in pages:
        stream = page.get_contents()
        size = len(stream.get_data()) if stream is not None else 0
        decoded_size += size
        if size > MAX_PDF_PAGE_BYTES or decoded_size > MAX_PDF_CONTENT_BYTES:
            raise ValueError("Превышен лимит содержимого PDF")
        yield page.extract_text() or ""


def docx_text(document):
    for paragraph in document.paragraphs:
        yield paragraph.text
    for table in document.tables:
        for row in table.rows:
            # Bound cells as well as the document: a table row can be very large.
            yield collect_text((cell.text for cell in row.cells), " | ")


class RunbookInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    condition: str = Field(min_length=3, max_length=30000)
    steps: list[str] = Field(min_length=1, max_length=100)
    cautions: str = Field(default="", max_length=10000)
    category: str = "application"

    @field_validator("title", "condition")
    @classmethod
    def strip_text(cls, value):
        if not value.strip():
            raise ValueError("Поле не должно быть пустым")
        return value.strip()

    @field_validator("steps")
    @classmethod
    def valid_steps(cls, value):
        if any(not step.strip() or len(step) > 10000 for step in value):
            raise ValueError("Шаги должны содержать текст длиной до 10000 символов")
        return [step.strip() for step in value]

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in {"server", "network", "database", "application"}:
            raise ValueError("Неизвестная категория")
        return value


def extract(content: bytes, extension: str) -> str:
    try:
        if extension in {".txt", ".md", ".json"}:
            text = content.decode("utf-8-sig")
        elif extension == ".pdf":
            from pypdf import PdfReader

            if not content.startswith(b"%PDF-"):
                raise ValueError("Файл не является PDF")
            reader = PdfReader(BytesIO(content))
            if len(reader.pages) > 2000:
                raise ValueError("Лимит — 2000 страниц")
            text = collect_text(pdf_text(reader.pages))
        elif extension == ".docx":
            from docx import Document

            with ZipFile(BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 60 * 1024 * 1024:
                    raise ValueError("Слишком большой распакованный DOCX")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Файл не является DOCX")
            doc = Document(BytesIO(content))
            text = collect_text(docx_text(doc))
        else:
            raise ValueError("Поддерживаются JSON, MD, TXT, PDF и DOCX")
        if not text.strip():
            raise ValueError("Нет текстового слоя. Для скана сначала выполните OCR")
        if len(text) > MAX_TEXT_CHARACTERS:
            raise ValueError("Документ содержит слишком много текста")
        return text
    except (ValueError, UnicodeDecodeError, BadZipFile) as exc:
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        raise ValueError("Не удалось прочитать документ: он повреждён или защищён") from exc


def parse_runbooks(text: str, extension: str, filename: str = "Документ") -> list[dict]:
    try:
        if extension == ".json":
            data = json.loads(text)
            records = data if isinstance(data, list) else [data]
        else:
            explicit_rules = re.search(
                r"\b(?:Если|If)\s+.+?\s*(?:→|->|⇒|\bthen\b)\s*.+",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if extension == ".md" and not explicit_rules:
                # Headings describe sections of the same procedure, not independent advice.
                # Chunking for vector search is handled later, without losing cautions.
                title = re.search(r"(?m)^#\s+(.+)$", text)
                return [
                    RunbookInput(
                        title=(title.group(1).strip() if title else filename)[:200],
                        condition=text[:30000],
                        steps=[text[start : start + 10000] for start in range(0, len(text), 10000)],
                    ).model_dump()
                ]
            records = []
            # Each line-start If/Если begins a separate rule, including plain TXT
            # and text extracted from PDF/DOCX without Markdown headings.
            blocks = re.split(r"(?im)^#{1,3}\s+|(?=^[ \t]*(?:[-*]|\d+[.)])?[ \t]*(?:Если|If)\s+)", text)
            for index, block in enumerate(blocks):
                block = block.strip()
                if not block:
                    continue
                match = re.search(
                    r"\b(?:Если|If)\s+(.+?)\s*(?:→|->|⇒|\bthen\b)\s*(.+)",
                    block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if match:
                    condition, action = match.groups()
                    steps = [
                        re.sub(r"^[-*\d.)\s]+", "", s).strip() for s in re.split(r";|\n", action) if s.strip()
                    ]
                    records.append(
                        dict(title=condition.strip()[:200], condition=condition.strip(), steps=steps)
                    )
                else:
                    if explicit_rules:
                        continue
                    # Narrative runbooks remain searchable, with their original text as instruction.
                    for offset in range(0, len(block), 6000):
                        part = block[offset : offset + 6000]
                        records.append(
                            dict(
                                title=f"{filename[:150]} · раздел {index + 1}.{offset // 6000 + 1}",
                                condition=part[:2000],
                                steps=[part],
                            )
                        )
        if not records or len(records) > 2000:
            raise ValueError("Документ должен содержать от 1 до 2000 инструкций")
        return [RunbookInput.model_validate(row).model_dump() for row in records]
    except (ValidationError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Неверный формат: нужны title, condition и непустой массив steps") from exc
