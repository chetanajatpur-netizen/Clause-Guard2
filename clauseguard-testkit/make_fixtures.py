"""Generate DOC-01_freelance_agreement.pdf and DOC-05_saas_msa.docx test fixtures."""
from pathlib import Path
import docx
import pypdf

CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"


def create_docx() -> Path:
    """Create DOC-05_saas_msa.docx from vendor MSA text."""
    doc = docx.Document()
    doc.add_heading("SAAS MASTER SERVICES AGREEMENT", 0)

    doc5_txt = (CONTRACTS_DIR / "DOC-05_vendor_msa.txt").read_text(encoding="utf-8")
    for para in doc5_txt.split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())

    docx_path = CONTRACTS_DIR / "DOC-05_saas_msa.docx"
    doc.save(docx_path)
    print(f"Created {docx_path} ({docx_path.stat().st_size} bytes)")
    return docx_path


def create_pdf() -> Path:
    """Create valid DOC-01_freelance_agreement.pdf from freelance agreement text."""
    doc1_txt = (CONTRACTS_DIR / "DOC-01_freelance_agreement.txt").read_text(encoding="utf-8")

    lines = []
    for line in doc1_txt.split("\n"):
        clean_line = line.strip()
        escaped = clean_line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines.append(f"({escaped}) ' ")

    stream_content = "BT /F1 10 Tf 40 760 Td 13 TL\n" + "\n".join(lines) + "\nET\n"
    stream_bytes = stream_content.encode("latin-1", errors="replace")
    stream_len = len(stream_bytes)

    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        + f"4 0 obj << /Length {stream_len} >> stream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n500\n%%EOF\n"
    )

    pdf_path = CONTRACTS_DIR / "DOC-01_freelance_agreement.pdf"
    pdf_path.write_bytes(pdf_bytes)
    print(f"Created {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return pdf_path


def main():
    docx_path = create_docx()
    pdf_path = create_pdf()

    # Validate with pypdf and python-docx
    reader = pypdf.PdfReader(pdf_path)
    text_pdf = "".join(p.extract_text() or "" for p in reader.pages)
    print(f"Verified PDF readable: {len(text_pdf)} chars extracted")

    doc = docx.Document(docx_path)
    text_docx = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    print(f"Verified DOCX readable: {len(text_docx)} chars extracted")


if __name__ == "__main__":
    main()
