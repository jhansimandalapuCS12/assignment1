# app/services/parser.py

from io import BytesIO

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


def extract_text_from_bytes(file_bytes: bytes, file_type: str) -> str:
    """
    Extract text from uploaded file bytes based on the file type.
    Supports: PDF, DOCX, and plain text.
    Always returns a clean string (never None) and never crashes.
    """
    if not file_bytes:
        return ""

    file_type = (file_type or "").lower()

    # ----- PDF -----
    if "pdf" in file_type and PdfReader is not None:
        try:
            reader = PdfReader(BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                try:
                    pages_text.append(page.extract_text() or "")
                except Exception:
                    pages_text.append("")
            return "\n".join(pages_text)
        except Exception:
            return ""

    # ----- DOCX (Word) -----
    if ("word" in file_type or "docx" in file_type) and Document is not None:
        try:
            doc = Document(BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""

    # ----- Fallback: Treat as plain text -----
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""
