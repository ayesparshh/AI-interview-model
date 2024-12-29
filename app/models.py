from pydantic import BaseModel
from typing import List

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class AnalysisDetails(BaseModel):
    match_percentage: str
    key_matches: list[str]
    missing_skills: list[str]
    recommendations: list[str]

class JobRequirement(BaseModel):
    requirement: str
    expectation: str
    match_status: str

class StructuredJobDescription(BaseModel):
    title: str
    objective: str
    goals: str
    address: str
    work_model: str
    job_type: str
    salary_range: str
    mandatory_skills: list[dict]
    skills_experience: dict
    location_details: dict

class TabularAnalysis(BaseModel):
    requirements: list[JobRequirement]
    candidate_distance: str
    travel_time: str

class JobMatchResponse(BaseModel):
    match_score: str
    tabular_analysis: TabularAnalysis
    analysis: AnalysisDetails

class JobMatch(BaseModel):
    job_id: str
    job_title: str
    match_score: str

class MultipleJobMatchResponse(BaseModel):
    matches: list[JobMatch]

class JobDescription(BaseModel):
    job_id: str
    title: str
    description: str

class JobApplicationForm(BaseModel):
    mandatory_skill_1: str
    mandatory_skill_2: str
    mandatory_skill_3: str
    mandatory_skill_4: str
    mandatory_skill_5: str
    preferred_skills: str
    current_address: str
    expected_salary: str
    notice_period: int

class QuestionWithTime(BaseModel):
    question: str
    estimated_time_minutes: int

class QuestionGenerationResponse(BaseModel):
    questions: List[QuestionWithTime]

class AnswerPair(BaseModel):
    question: str
    answer: str

class AnswerScore(BaseModel):
    question: str
    answer: str
    score: int
    feedback: str

class AnswerScoringResponse(BaseModel):
    scores: List[AnswerScore]

class CandidateMatch(BaseModel):
    candidate_id: str
    candidate_name: str
    match_score: str
    cv_filename: str

class MultipleCandidateMatchResponse(BaseModel):
    matches: list[CandidateMatch]

class QuestionGenerateRequest(BaseModel):
    cv: str
    jobDescription: str
    count: int = 3    