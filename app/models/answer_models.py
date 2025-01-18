from pydantic import BaseModel
from typing import List

class AnswerPair(BaseModel):
    question: str
    answer: str

class AnswerScore(BaseModel):
    question: str
    answer: str
    score: int
    comment: str

class AnswerScoringResponse(BaseModel):
    scores: List[AnswerScore]
    overall_score: int