from fastapi import APIRouter, HTTPException, Body
from typing import List, Tuple
from pydantic import BaseModel
from ..models import AnswerPair, AnswerScore, AnswerScoringResponse
from ..prompts import ANSWER_SCORING_PROMPT
from app.config import client, model

router = APIRouter()

class ScoringRequest(BaseModel):
    answers: List[AnswerPair]

def parse_scoring_response(response_text: str) -> Tuple[int, str]:
    """Parse the scoring response from the LLM to extract score and comment"""
    try:
        import re
        score_match = re.search(r'(?:score:?\s*)?(\d{1,2})(?:/10)?', response_text.lower())
        if not score_match:
            return 0, "Could not parse score from response"
            
        score = int(score_match.group(1))
        score = max(0, min(score, 10))
        
        comment_match = re.search(r'comment:\s*(.*)', response_text.lower())
        if comment_match:
            comment = ' '.join(comment_match.group(1).split()[:6])
        else:
            comment = "No comment provided"
            
        return score, comment
        
    except Exception as e:
        return 0, f"Error parsing response: {str(e)}"

@router.post("/score-answers", response_model=AnswerScoringResponse)
async def score_answers(request: ScoringRequest = Body(...)):
    try:
        scores = []
        total_score = 0
        
        for answer_pair in request.answers:
            completion = client.chat.complete(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert technical interviewer. Score answers between 0-10."
                    },
                    {
                        "role": "user",
                        "content": ANSWER_SCORING_PROMPT.format(
                            question=answer_pair.question,
                            answer=answer_pair.answer
                        )
                    }
                ]
            )
            
            response_text = completion.choices[0].message.content
            score, comment = parse_scoring_response(response_text)
            total_score += score
            
            scores.append(AnswerScore(
                id=answer_pair.id,
                question=answer_pair.question,
                answer=answer_pair.answer, 
                score=score,
                comment=comment
            ))
        
        avg_score = total_score // len(request.answers)
        
        return AnswerScoringResponse(
            scores=scores,
            overall_score=avg_score
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))