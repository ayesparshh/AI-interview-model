import datetime
import json
import logging
from pydoc import text
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, List
from ..models.embedding_models import Candidate, EmbeddingResponseJob, JobDescription as JobDescriptionDB, MatchResponse
from ..embeddings import EmbeddingGenerator
from ..db.database import get_db
from app.config import client, model

router = APIRouter()
logger = logging.getLogger(__name__)

class JobDescription(BaseModel):
    title: str
    objective: str
    goals: str
    description: str = Field(..., alias="jobDescription")
    skills: List[str]
    experienceRequired: int

class JobDescriptionRequest(BaseModel):
    job: JobDescription
    jobId: str

def format_job_data_for_embedding(job_data: JobDescription) -> str:
    """Format structured job data for embedding generation"""
    try:
        completion = client.chat.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": """Output format must be exactly:
                    [role] [number] years [keywords from objective] [keywords from goals] [keywords from description] [skills]
                    Extract only technical terms and numbers. Do not include any punctuation, symbols, or unnecessary formatting. Remove all common words and descriptive phrases. Ensure the output is concise and contains only essential technical details."""
                },
                {
                    "role": "user",
                    "content": f"{job_data.title} {job_data.experienceRequired} {job_data.objective} {job_data.goals} {job_data.description} {' '.join(job_data.skills)}"
                }
            ],
            temperature=0,
            max_tokens=100
        )
        
        formatted_text = completion.choices[0].message.content.strip()
        return ' '.join(word for word in formatted_text.split())
        
    except Exception as e:
        logger.error(f"Error formatting job data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to format job description"
        )

@router.post("/process-jd", response_model=EmbeddingResponseJob)
async def process_job_description(
    request: JobDescriptionRequest,
    db: Session = Depends(get_db)
):
    try:
        formatted_job_text = format_job_data_for_embedding(request.job)
        
        logger.info("Text used for embeddings:")
        logger.info(formatted_job_text)

        embedding_gen = EmbeddingGenerator("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")
        embeddings = embedding_gen.generate_embeddings([(formatted_job_text, request.jobId)])
        embedding_vector = embeddings.drop(['document_id', 'timestamp'], axis=1).values[0].tolist()

        # Check if job already exists
        existing_job = db.query(JobDescriptionDB).filter(JobDescriptionDB.job_id == request.jobId).first()
        
        if existing_job:
            existing_job.jd_text = formatted_job_text
            existing_job.embedding = embedding_vector
            existing_job.created_at = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"Updated existing job: {request.jobId}")
        else:
            job = JobDescriptionDB(
                job_id=request.jobId,
                jd_text=formatted_job_text,
                embedding=embedding_vector
            )
            db.add(job)
            logger.info(f"Created new job: {request.jobId}")

        db.commit()

        return EmbeddingResponseJob(
            jobId=request.jobId,
            embedding=embedding_vector,
        )
    except Exception as e:
        logger.error(f"Error in process_job_description: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/match/{job_id}", response_model=MatchResponse)
async def match_candidates(
    job_id: str, 
    threshold: float = 0.5,
    db: Session = Depends(get_db)
):
    try:
        job = db.query(JobDescriptionDB).filter(JobDescriptionDB.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        candidate_count = db.query(Candidate).count()
        logger.info(f"Found {candidate_count} candidates in database")
        
        from sqlalchemy import text
        
        query = text("""
            SELECT 
                c.user_id,
                c.resume_text,
                1 - (c.embedding <=> j.embedding) as similarity
            FROM candidates c
            CROSS JOIN job_descriptions j
            WHERE j.job_id = :job_id
            AND (1 - (c.embedding <=> j.embedding)) > :threshold
            ORDER BY similarity DESC
        """)
        
        results = db.execute(
            query, 
            {
                "job_id": job_id, 
                "threshold": threshold
            }
        ).fetchall()

        candidates = [{
            "userId": row[0],
            "resumeText": row[1],
            "similarity": float(row[2]) 
        } for row in results]

        logger.info(f"Found {len(candidates)} matching candidates")
        
        return MatchResponse(
            jobId=job_id,
            candidates=candidates
        )

    except Exception as e:
        logger.error(f"Error in match_candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))