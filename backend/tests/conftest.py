import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.services.classifier import classifier
from app.services.embedder import embedder

# In-memory SQLite for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the test database once per session."""
    Base.metadata.create_all(bind=test_engine)
    
    # Ensure embedder is loaded for testing
    if not embedder.is_loaded:
        embedder.load("sentence-transformers/all-MiniLM-L6-v2")
        
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a clean database session per test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
def scanned_pdf_bytes() -> bytes:
    """Create an empty/scanned PDF without text stream."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF"
    )


@pytest.fixture
def small_pdf_bytes() -> bytes:
    """Create a minimal valid PDF containing readable text."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 50 >> stream\n"
        b"BT /F1 12 Tf 50 700 Td (1. NON-COMPETE AGREEMENT) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000266 00000 n \n0000000366 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n440\n%%EOF"
    )
    return pdf_content
