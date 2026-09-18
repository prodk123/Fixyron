import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class RepositoryAnalysis(Base):
    __tablename__ = "repository_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_url = Column(String, nullable=False)
    repository_name = Column(String, nullable=True)
    bug_description = Column(Text, nullable=True)
    
    primary_language = Column(String, nullable=True)
    framework = Column(String, nullable=True)
    test_framework = Column(String, nullable=True)
    test_file_count = Column(Integer, default=0)
    
    file_count = Column(Integer, default=0)
    estimated_loc = Column(Integer, default=0)
    has_readme = Column(Boolean, default=False)
    
    important_directories = Column(JSON, nullable=True)
    relevant_files = Column(JSON, nullable=True)
    
    status = Column(String, default="pending")  # pending, cloning, analyzing, completed, failed
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
