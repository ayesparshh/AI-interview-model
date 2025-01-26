from pydantic import BaseModel
from typing import List, Dict
from sqlalchemy import Column, Integer, String, DateTime
from pgvector.sqlalchemy import Vector
from ..db.database import Base
import datetime

class EmbeddingResponse(BaseModel):
    userId: str
    embedding: List[float]

class EmbeddingResponseJob(BaseModel):
    jobId: str
    embedding: List[float]

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    resume_text = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    jd_text = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

class MatchResponse(BaseModel):
    jobId: str
    candidates: List[Dict]