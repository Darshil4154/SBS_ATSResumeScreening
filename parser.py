import pdfplumber
from docx import Document
import os


def extract_text(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return extract_pdf(filepath)
    elif ext == '.docx':
        return extract_docx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_pdf(filepath):
    text = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return '\n'.join(text)


def extract_docx(filepath):
    doc = Document(filepath)
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
