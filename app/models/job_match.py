from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class JobDescription(BaseModel):
    title: str
    objective: str
    goals: str
    description: str = Field(..., alias="jobDescription")
    skills: List[str]
    experienceRequired: int

class CandidateProfile(BaseModel):
    skills: Dict[str, str]
    experience: str
    resumeUrl: str
    noticePeriod: str
    expectedSalary: float

class JobMatchRequest(BaseModel):
    job: JobDescription = Field(..., alias="job")
    cv_data: str = Field(..., alias="cv_data")
    skill_description_map: Optional[List[Dict[str, str]]] = Field(default=None)

    class Config:
        allow_population_by_field_name = True

class RequirementMatch(BaseModel):
        requirement: str
        expectation: str
        candidateProfile: str
        matchPercentage: float
        comment: str

class JobMatchResponse(BaseModel):
    overallMatch: float
    overallComment: str
    requirements: List[RequirementMatch]