from pydantic import BaseModel
from typing import List, Optional

class AnswerPair(BaseModel):
    question: str
    answer: str

class AnswerScore(BaseModel):
    question: str
    answer: str
    score: int

class AnswerScoringResponse(BaseModel):
    scores: List[AnswerScore]
    overall_score: int