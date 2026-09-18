import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("repository_analyses.id"), nullable=False)
    reproduction_id = Column(String, ForeignKey("reproduction_attempts.id"), nullable=False)

    # Diagnosis content
    summary = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    failure_mechanism = Column(Text, nullable=True)

    # Structured fields (JSON)
    affected_files = Column(JSON, nullable=True)
    affected_functions = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    alternative_causes = Column(JSON, nullable=True)
    code_context = Column(JSON, nullable=True)  # Source snippets used for diagnosis

    # Confidence
    confidence = Column(Float, nullable=True)
    confidence_level = Column(String, nullable=True)  # HIGH, MEDIUM, LOW

    # Status tracking
    status = Column(String, nullable=False, default="pending")
    # Valid: pending, collecting_context, analyzing, validating, completed, failed, inconclusive

    # LLM metadata
    model = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
