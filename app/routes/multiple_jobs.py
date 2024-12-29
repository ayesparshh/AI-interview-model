from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import json
import re
from ..models import (
    MultipleJobMatchResponse, 
    JobDescription, 
    JobMatch,
    MultipleCandidateMatchResponse,
    CandidateMatch
)
from ..prompts import MULTIPLE_JOBS_ANALYSIS_PROMPT, MULTIPLE_CANDIDATES_ANALYSIS_PROMPT
from app.config import client
from .cv_matching import extract_pdf_text

router = APIRouter()

@router.post("/match-multiple-jobs", response_model=MultipleJobMatchResponse)
async def match_multiple_jobs(
    cv_file: UploadFile = File(...),
    job_descriptions: str = Form(...)
):
    try:
        job_descriptions_data = json.loads(job_descriptions)
        job_descriptions_parsed = [JobDescription(**job) for job in job_descriptions_data]
        
        pdf_content = await cv_file.read()
        cv_text = extract_pdf_text(pdf_content)
        
        matches = []
        for job in job_descriptions_parsed:
            completion = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": "You are a professional CV analyzer."},
                    {"role": "user", "content": MULTIPLE_JOBS_ANALYSIS_PROMPT.format(
                        cv_text=cv_text,
                        job_description=job.description,
                        job_title=job.title
                    )},
                ],
            )
            
            match_percentage = parse_match_percentage(completion.choices[0].message.content)
            matches.append(JobMatch(
                job_id=job.job_id,
                job_title=job.title,
                match_score=match_percentage
            ))
            
        matches.sort(key=lambda x: float(x.match_score.strip('%')), reverse=True)
        return MultipleJobMatchResponse(matches=matches)
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON format in job_descriptions")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_candidate_name(cv_text: str) -> str:
    """Extract candidate name from CV text"""
    try:
        cleaned_text = cv_text.replace("Last Updated on", "").replace("Last Upda ted on", "")
        
        lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
       
        for line in lines[:3]:
            
            if not any(x in line.lower() for x in ['updated', 'date:', '202']):
                return line[:50]
        return "Unknown Candidate"
    except:
        return "Unknown Candidate"

def parse_match_percentage(response_text: str) -> str:
    """Parse and validate match percentage"""
    try:
        for line in response_text.split('\n'):
            if 'MATCH_PERCENTAGE:' in line:
                number = ''.join(c for c in line.split(':')[1].strip() if c.isdigit())
                if number:
                    percentage = int(number)
                    if 0 <= percentage <= 100:
                        return f"{percentage}%"
        raise ValueError("Invalid percentage format")
    except Exception as e:
        print(f"Percentage parsing error: {str(e)}")
        return "0%"

def extract_email(cv_text: str) -> str:
    """Extract email from CV text"""
    try:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(email_pattern, cv_text.replace(' ', ''))
        return matches[0] if matches else "No email found"
    except:
        return "No email found"

@router.post("/match-multiple-candidates", response_model=MultipleCandidateMatchResponse)
async def match_multiple_candidates(
    cv_files: list[UploadFile] = File(...),
    job_description: str = Form(...)
):
    try:
        candidates_matches = []
        
        for cv_file in cv_files:
            pdf_content = await cv_file.read()
            cv_text = extract_pdf_text(pdf_content)
            candidate_email = extract_email(cv_text)
            
            completion = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": "You are a professional CV analyzer."},
                    {"role": "user", "content": MULTIPLE_CANDIDATES_ANALYSIS_PROMPT.format(
                        cv_text=cv_text,
                        job_description=job_description
                    )},
                ],
                temperature=0.3
            )
            
            match_percentage = parse_match_percentage(completion.choices[0].message.content)
            candidates_matches.append(CandidateMatch(
                candidate_id=str(len(candidates_matches) + 1),
                candidate_name=candidate_email,
                match_score=match_percentage,
                cv_filename=cv_file.filename
            ))
        
        candidates_matches.sort(key=lambda x: float(x.match_score.strip('%')), reverse=True)
        return MultipleCandidateMatchResponse(matches=candidates_matches)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))