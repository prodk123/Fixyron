import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("repository_analyses.id"), nullable=False)
    
    framework = Column(String, nullable=True)
    command = Column(String, nullable=True)
    status = Column(String, nullable=False) # e.g., success, failed, timeout, error
    exit_code = Column(Integer, nullable=True)
    
    tests_total = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_failed = Column(Integer, default=0)
    tests_skipped = Column(Integer, default=0)
    
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    
    duration_ms = Column(Integer, nullable=True)
    timed_out = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReproductionAttempt(Base):
    __tablename__ = "reproduction_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("repository_analyses.id"), nullable=False)
    
    bug_description = Column(Text, nullable=False)
    test_framework = Column(String, nullable=True)
    test_code = Column(Text, nullable=True)
    target_files = Column(JSON, nullable=True)
    
    hypothesis = Column(Text, nullable=True)
    classification = Column(String, nullable=False) # reproduced, not_reproduced, inconclusive
    evidence = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
