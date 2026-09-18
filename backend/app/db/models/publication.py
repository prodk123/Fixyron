import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class Publication(Base):
    __tablename__ = "publications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id = Column(String, ForeignKey("repairs.id"), nullable=False, unique=True)
    
    repository_owner = Column(String, nullable=True)
    repository_name = Column(String, nullable=True)
    baseline_sha = Column(String, nullable=True)
    
    branch_name = Column(String, nullable=True)
    commit_sha = Column(String, nullable=True)
    
    pull_request_number = Column(Integer, nullable=True)
    pull_request_url = Column(String, nullable=True)
    pull_request_state = Column(String, nullable=True)
    
    verified_patch_hash = Column(String, nullable=True)
    published_patch_hash = Column(String, nullable=True)
    
    status = Column(String, default="PENDING")
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
