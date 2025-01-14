from pydantic import BaseModel
from typing import Dict, List

class JobDescription(BaseModel):
    title: str
    objective: str
    goals: str
    description: str
    skills: List[str]
    experienceRequired: int

class CandidateProfile(BaseModel):
    skills: Dict[str, str]
    experience: str
    resumeUrl: str
    noticePeriod: str
    expectedSalary: float

class JobMatchRequest(BaseModel):
    jobDescription: JobDescription
    cvData: str
    skillDescriptionMap: Dict[str, str] | None = None

class RequirementMatch(BaseModel):
    requirement: str
    expectation: str
    candidateProfile: str
    matchPercentage: float
    comment: str

class JobMatchResponse(BaseModel):
    overallMatch: float
    requirements: List[RequirementMatch]