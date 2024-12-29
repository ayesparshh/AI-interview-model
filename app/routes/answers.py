from fastapi import APIRouter, HTTPException, Body
from typing import List, Tuple
from pydantic import BaseModel
from ..models import AnswerPair, AnswerScore, AnswerScoringResponse
from ..prompts import ANSWER_SCORING_PROMPT
from app.config import client
# uvicorn app.main:app --reload
# python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
router = APIRouter()

class ScoringRequest(BaseModel):
    answers: List[AnswerPair]
    job_description: str

@router.post("/score-answers", response_model=AnswerScoringResponse)
async def score_answers(
    request: ScoringRequest = Body(...)
):
    try:
        scores = []
        for answer_pair in request.answers:
            completion = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert technical interviewer. Score answers based on completeness, accuracy, clarity, and practical application."
                    },
                    {
                        "role": "user", 
                        "content": ANSWER_SCORING_PROMPT.format(
                            question=answer_pair.question,
                            answer=answer_pair.answer,
                            job_description=request.job_description
                        )
                    }
                ],
                temperature=0.7
            )
            
            response_text = completion.choices[0].message.content
            score, feedback = parse_scoring_response(response_text)
            
            scores.append(AnswerScore(
                question=answer_pair.question,
                answer=answer_pair.answer,
                score=score,
                feedback=feedback
            ))
            
        return AnswerScoringResponse(scores=scores)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def parse_scoring_response(response_text: str) -> Tuple[int, str]:
    score = 0
    feedback = ""
    
    for line in response_text.split('\n'):
        line = line.strip()
        if line.startswith('SCORE:'):
            try:
                score_str = line.replace('SCORE:', '').strip()
                score = int(float(score_str))
                score = max(0, min(10, score))
            except ValueError:
                score = 0
        elif line.startswith('FEEDBACK:'):
            feedback = line.replace('FEEDBACK:', '').strip()
            
    return score, feedback