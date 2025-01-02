from pydantic import BaseModel
from typing import Dict, List

class JobDescription(BaseModel):
    title: str
    description: str
    skills: List[str]
    experienceRequired: str

class CandidateProfile(BaseModel):
    skills: Dict[str, str]
    experience: str
    resumeUrl: str
    noticePeriod: str
    expectedSalary: float

class JobMatchRequest(BaseModel):
    jobDescription: JobDescription
    candidateProfile: CandidateProfile

class RequirementMatch(BaseModel):
    requirement: str
    expectation: str
    candidateProfile: str
    matchPercentage: float

class JobMatchResponse(BaseModel):
    overallMatch: float
    requirements: List[RequirementMatch]