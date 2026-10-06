"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base


class Document(Base):
    """Uploaded contract document."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    char_count = Column(Integer, nullable=False)
    overall_risk = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    clauses = relationship("Clause", back_populates="document", cascade="all, delete-orphan")
    search_queries = relationship("SearchQuery", back_populates="document", cascade="all, delete-orphan")


class Clause(Base):
    """Individual clause extracted from a document."""

    __tablename__ = "clauses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    label = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    risk_level = Column(String(10), nullable=True)
    embedding = Column(LargeBinary, nullable=True)

    document = relationship("Document", back_populates="clauses")


class SearchQuery(Base):
    """Logged semantic search query."""

    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    top_result_clause_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="search_queries")
