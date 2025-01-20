from pydantic import BaseModel, RootModel
from typing import List

class AnswerPair(BaseModel):
    id: str
    question: str
    answer: str

class AnswerScore(BaseModel):
    id: str
    question: str
    answer: str
    score: int
    comment: str

class AnswerScoringResponse(RootModel):
    root: List[AnswerScore]