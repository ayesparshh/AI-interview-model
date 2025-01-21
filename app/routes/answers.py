import logging
import re
from fastapi import APIRouter, HTTPException, Body
from typing import List, Tuple
from pydantic import BaseModel
from ..models import AnswerPair, AnswerScore, AnswerScoringResponse
from ..prompts import ANSWER_SCORING_PROMPT
from app.config import client, model

router = APIRouter()

class ScoringRequest(BaseModel):
    questionAnswerPairs: List[AnswerPair]

def parse_scoring_response(response_text: str) -> Tuple[int, str]:
    try:
        import re
        score_match = re.search(r'(?:score:?\s*)?(\d{1,2})(?:/10)?', response_text.lower())
        if not score_match:
            return 0, "Could not parse score from response"
            
        score = int(score_match.group(1))
        # Enforce 0-10 range
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
        combined_prompt = (
            "Evaluate these question-answer pairs according to:\n"
            "1) Completeness (0-4)\n2) Technical Accuracy (0-3)\n"
            "3) Communication Clarity (0-2)\n4) Practical Application (0-1)\n\n"
        )
        
        for i, qa in enumerate(request.questionAnswerPairs, start=1):
            combined_prompt += f"\nPair {i}:\n" + ANSWER_SCORING_PROMPT.format(
                question=qa.question,
                answer=qa.answer
            )

        completion = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert interviewer."},
                {"role": "user", "content": combined_prompt}
            ]
        )

        response_text = completion.choices[0].message.content.strip()
        scores = []
        total_score = 0

        for i, answer_pair in enumerate(request.questionAnswerPairs, start=1):
            score_pattern = rf"SCORE:\s*(\d+)"
            comment_pattern = rf"COMMENT:\s*(.*)"
            block_pattern = rf"Pair\s*{i}.*?(SCORE:.*?COMMENT:.*?)(?=Pair\s*{i+1}|$)"
            
            block_match = re.search(block_pattern, response_text, re.IGNORECASE|re.DOTALL)
            if block_match:
                block_text = block_match.group(1)
                sm = re.search(score_pattern, block_text, re.IGNORECASE)
                cm = re.search(comment_pattern, block_text, re.IGNORECASE)
                
                raw_score = int(sm.group(1)) if sm else 0
                # Enforce 0-10 range
                raw_score = max(0, min(raw_score, 10))
                
                raw_comment = cm.group(1).strip() if cm else "No comment provided"
                short_comment = ' '.join(raw_comment.split()[:6])
            else:
                raw_score = 0
                short_comment = "No comment provided"

            total_score += raw_score
            scores.append(AnswerScore(
                id=answer_pair.id,
                question=answer_pair.question,
                answer=answer_pair.answer,
                score=raw_score,
                comment=short_comment
            ))

        return AnswerScoringResponse(root=scores)

    except Exception as e:
        logging.error(f"Error in score_answers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))