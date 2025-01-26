import datetime
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, List
from ..models.embedding_models import EmbeddingResponse, Candidate
from ..embeddings import EmbeddingGenerator
from ..db.database import get_db
from app.config import client, model
import json
import re

router = APIRouter()
logger = logging.getLogger(__name__)

class StructuredResumeData(BaseModel):
    title: str = Field(default="")
    experience: str = Field(default="")
    skills: str = Field(default="")
    qualifications: str = Field(default="")
    location: str = Field(default="")
    responsibilities: str = Field(default="")

class ResumeRequest(BaseModel):
    cv_text: str
    userId: str

def extract_structured_resume_data(raw_resume: str) -> StructuredResumeData:
    try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                completion = client.chat.complete(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a resume parser. Extract and normalize information into a consistent format.
                            Pay special attention to work experience dates to calculate total years.
                            For each work experience entry, extract start and end dates to calculate duration.
                            Return ONLY a JSON object with these exact fields:
                            - experience: total years of experience as number (calculate from work history dates) or if mentioned in resume
                            - skills: array of ALL skills (languages, frameworks, tools, etc)
                            - qualifications: array of education details  
                            - responsibilities: array of work achievements
                            
                            For experience calculation:
                            - Use actual dates from work history
                            - Sum up all periods of employment
                            - For current roles, calculate up to present date
                            - Round to nearest year"""
                        },
                        {
                            "role": "user", 
                            "content": f"""Carefully analyze the resume and extract:
                            1. Total years of experience (calculate from actual work history dates)
                            2. ALL skills as a flat array (combine programming, frameworks, tools etc)
                            3. Education qualifications with CGPAs
                            4. Key responsibilities and achievements
                            
                            Important: For experience, look for date patterns like MM/YYYY or phrases indicating employment periods.
                            Calculate total years based on start and end dates of each role.

                            Resume text: {raw_resume}"""
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
                data = json.loads(json_str)
                
                return StructuredResumeData(
                    experience=str(data.get("experience", "")) + " years",
                    skills=json.dumps(data.get("skills", [])),
                    qualifications=json.dumps(data.get("qualifications", [])),
                    responsibilities=json.dumps(data.get("responsibilities", []))
                )
                
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error: {je}")
                continue
            except Exception as e:
                logger.error(f"Parsing attempt failed: {e}")
                continue
                
        raise ValueError("Failed to parse resume after all retries")
        
    except Exception as e:
        logger.error(f"Resume extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to parse resume")

def format_skills(skills_array: str) -> str:
    """Convert skills array to space-separated string"""
    try:
        if not skills_array:
            return ""
        skills = json.loads(skills_array)
        if isinstance(skills, list):
            return " ".join(str(skill) for skill in skills)
        return str(skills)
    except:
        return str(skills_array)

def format_qualifications(quals_array: str) -> str:
    """Format qualifications as pipe-separated string"""
    try:
        quals = json.loads(quals_array)
        if isinstance(quals, list):
            formatted = []
            for qual in quals:
                if isinstance(qual, dict):
                    parts = []
                    if "degree" in qual:
                        parts.append(qual["degree"])
                    if "major" in qual:
                        parts.append(qual["major"])
                    if "cgpa" in qual:
                        parts.append(f"CGPA {qual['cgpa']}")
                    formatted.append(" ".join(parts))
                else:
                    formatted.append(str(qual))
            return " | ".join(formatted)
        return str(quals)
    except:
        return str(quals_array)

def format_responsibilities(resp_array: str) -> str:
    """Format responsibilities as period-separated string"""
    try:
        resp = json.loads(resp_array)
        if isinstance(resp, list):
            return ". ".join(str(r) for r in resp if r)
        return str(resp)
    except:
        return str(resp_array)

@router.post("/process-resume", response_model=EmbeddingResponse)
async def process_resume(
    request: ResumeRequest,
    db: Session = Depends(get_db)
):
    try:
        structured_data = extract_structured_resume_data(request.cv_text)
        
        formatted_resume_text = f"""{structured_data.title} {structured_data.experience} {format_skills(structured_data.skills)} {format_qualifications(structured_data.qualifications)} {structured_data.location} {format_responsibilities(structured_data.responsibilities)}""".strip()
        
        logger.info(f"Formatted resume text: {formatted_resume_text}")

        if not formatted_resume_text:
            raise ValueError("No valid text generated for embedding")

        embedding_gen = EmbeddingGenerator("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")
        embeddings = embedding_gen.generate_embeddings([(formatted_resume_text, request.userId)])
        embedding_vector = embeddings.drop(['document_id', 'timestamp'], axis=1).values[0].tolist()

        existing_candidate = db.query(Candidate).filter(Candidate.user_id == request.userId).first()
        
        if existing_candidate:
            existing_candidate.resume_text = formatted_resume_text
            existing_candidate.embedding = embedding_vector
            existing_candidate.created_at = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"Updated existing candidate: {request.userId}")
        else:
            candidate = Candidate(
                user_id=request.userId,
                resume_text=formatted_resume_text,
                embedding=embedding_vector
            )
            db.add(candidate)
            logger.info(f"Created new candidate: {request.userId}")

        db.commit()

        return EmbeddingResponse(
            userId=request.userId,
            embedding=embedding_vector,
        )
    except Exception as e:
        logger.error(f"Error in process_resume: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))