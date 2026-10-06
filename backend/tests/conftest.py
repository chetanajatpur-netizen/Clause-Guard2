"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_text() -> str:
    """Sample contract text for testing."""
    return """
    CONFIDENTIALITY AND NON-COMPETE AGREEMENT

    This Agreement is entered into as of January 1, 2024.

    1. NON-COMPETE CLAUSE
    The Employee agrees not to engage in any business that competes with 
    the Company for a period of two (2) years following termination of 
    employment, within a 50-mile radius of any Company office.

    2. INTELLECTUAL PROPERTY
    All inventions, discoveries, and works of authorship made by the 
    Employee during the term of employment shall be the sole property 
    of the Company.

    3. TERMINATION
    Either party may terminate this agreement with 30 days written notice 
    for any reason or no reason at all.

    4. LIABILITY
    The Company shall have no liability cap for damages arising from 
    breach of this agreement by the Employee.

    5. AUDIT RIGHTS
    The Company reserves the right to audit the Employee's compliance 
    with this agreement at any time during the term and for one year 
    after termination.
    """


@pytest.fixture
def small_pdf_bytes() -> bytes:
    """Create a minimal valid PDF for testing."""
    # Minimal PDF structure
    pdf_content = b"""%%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test contract) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000360 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
434
%%%%EOF"""
    return pdf_content
