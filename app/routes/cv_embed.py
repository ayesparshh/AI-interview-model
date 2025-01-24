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
    resumeText: str
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
                            Return ONLY a JSON object with these exact fields:
                            - experience: total years of experience as number
                            - skills: array of ALL skills (languages, frameworks, tools, etc)
                            - qualifications: array of education details
                            - responsibilities: array of work achievements"""
                        },
                        {
                            "role": "user",
                            "content": f"""Extract these details from the resume:
                            1. Total years of experience 
                            2. ALL skills as a flat array (combine programming, frameworks, tools etc)
                            3. Education qualifications with CGPAs
                            4. Key responsibilities and achievements

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
                
                # Normalize the data structure
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
        structured_data = extract_structured_resume_data(request.resumeText)
        
        formatted_resume_text = f"""{structured_data.title} {structured_data.experience} {format_skills(structured_data.skills)} {format_qualifications(structured_data.qualifications)} {structured_data.location} {format_responsibilities(structured_data.responsibilities)}""".strip()
        
        logger.info(f"Formatted resume text: {formatted_resume_text}")

        if not formatted_resume_text:
            raise ValueError("No valid text generated for embedding")

        # Generate embeddings
        embedding_gen = EmbeddingGenerator("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")
        embeddings = embedding_gen.generate_embeddings([(formatted_resume_text, request.userId)])
        embedding_vector = embeddings.drop(['document_id', 'timestamp'], axis=1).values[0].tolist()

        # Store in database
        candidate = Candidate(
            user_id=request.userId,
            resume_text=formatted_resume_text,
            embedding=embedding_vector
        )
        db.add(candidate)
        db.commit()

        return EmbeddingResponse(
            userId=request.userId,
            embeddings=embedding_vector,
            status="success"
        )
    except Exception as e:
        logger.error(f"Error in process_resume: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))