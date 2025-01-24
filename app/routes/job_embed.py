import json
import logging
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from ..models.embedding_models import Candidate, EmbeddingResponseJob, JobDescription, MatchResponse
from ..embeddings import EmbeddingGenerator
from ..db.database import get_db
from app.config import client, model

router = APIRouter()
logger = logging.getLogger(__name__)

class StructuredJobData(BaseModel):
    title: str = Field(default="")
    experience: str = Field(default="")
    requirements: str = Field(default="")
    qualifications: str = Field(default="")
    responsibilities: str = Field(default="")
    location: str = Field(default="")

class JobDescriptionRequest(BaseModel):
    jobData: str
    jobId: str

def extract_structured_job_data(raw_job_data: str) -> StructuredJobData:
    try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                completion = client.chat.complete(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a job description parser. Extract information from ANY job posting format. Return ONLY a clean JSON object."
                        },
                        {
                            "role": "user",
                            "content": f"""Extract these details from the job description, if not found return empty string:
                            1. title: Job position title
                            2. experience: Required years of experience
                            3. requirements: Technical or skill requirements
                            4. qualifications: Required education/certifications
                            5. responsibilities: Job duties and responsibilities
                            6. location: Job location

                            Return as clean JSON. Job Description: {raw_job_data}"""
                        }
                    ],
                    temperature=0.1,
                    max_tokens=1000
                )
                
                response_text = completion.choices[0].message.content.strip()
                
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    raise ValueError("Invalid JSON response")
                    
                json_str = json_match.group(0)
                json_str = re.sub(r'[\n\r\t\s]+', ' ', json_str)
                
                structured_data = json.loads(json_str)
                
                structured_data = {k: str(v).strip() if v else "" for k, v in structured_data.items()}
                
                parsed_data = StructuredJobData(**structured_data)
                
                if parsed_data.title or parsed_data.requirements or parsed_data.responsibilities:
                    logger.info("Successfully parsed job description")
                    return parsed_data
                    
                raise ValueError("Essential fields missing in parsed data")
                
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error: {je}")
                continue
            except Exception as e:
                logger.error(f"Parsing attempt failed: {e}")
                continue
                
        raise ValueError("Failed to parse job description after all retries")
        
    except Exception as e:
        logger.error(f"Job data extraction failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to parse job description"
        )

@router.post("/process-jd", response_model=EmbeddingResponseJob)
async def process_job_description(
    request: JobDescriptionRequest,
    db: Session = Depends(get_db)
):
    try:
        structured_data = extract_structured_job_data(request.jobData)
        
        formatted_job_text = f"""{structured_data.title} {structured_data.experience} {structured_data.requirements} {structured_data.qualifications} {structured_data.responsibilities} {structured_data.location}""".strip()
        
        logger.info("Text used for embeddings:")
        logger.info(formatted_job_text)

        logger.info("Data being stored in DB:")
        logger.info(f"Job ID: {request.jobId}")
        logger.info(f"Job Text: {formatted_job_text}")

        embedding_gen = EmbeddingGenerator("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")
        embeddings = embedding_gen.generate_embeddings([(formatted_job_text, request.jobId)])
        embedding_vector = embeddings.drop(['document_id', 'timestamp'], axis=1).values[0].tolist()

        job = JobDescription(
            job_id=request.jobId,
            jd_text=formatted_job_text,
            embedding=embedding_vector
        )
        db.add(job)
        db.commit()

        return EmbeddingResponseJob(
            jobId=request.jobId,
            embeddings=embedding_vector,
            status="success"
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
        job = db.query(JobDescription).filter(JobDescription.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        candidate_count = db.query(Candidate).count()
        logger.info(f"Found {candidate_count} candidates in database")
        
        query = text("""
            SELECT 
                c.user_id,
                c.resume_text,
                1 - (c.embedding <=> j.embedding) as similarity
            FROM job_descriptions j
            CROSS JOIN candidates c
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
            "user_id": row[0],
            "resume_text": row[1].strip(),
            "similarity": float(row[2])
        } for row in results]

        logger.info(f"Found {len(candidates)} matching candidates")
        
        return MatchResponse(
            job_id=job_id,
            candidates=candidates,
        )

    except Exception as e:
        logger.error(f"Error in match_candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))