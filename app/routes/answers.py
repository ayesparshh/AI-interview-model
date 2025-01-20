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
        qa_pairs = "\n\n".join([
            f"Question {i+1}: {qa.question}\nAnswer {i+1}: {qa.answer}"
            for i, qa in enumerate(request.questionAnswerPairs)
        ])
        
        completion = client.chat.complete(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": """You are an expert technical interviewer. Score multiple answers between 0-10.
                    For each Q&A pair, provide score and comment in this exact format:
                    Q1_SCORE: [number]
                    Q1_COMMENT: [brief judging comment in 6 words]
                    Q2_SCORE: [number]
                    Q2_COMMENT: [brief judging comment in 6 words]
                    And so on..."""
                },
                {
                    "role": "user",
                    "content": f"Evaluate all Q&A pairs according to these criteria:\n{ANSWER_SCORING_PROMPT}\n\nQ&A Pairs to Evaluate:\n{qa_pairs}"
                }
            ]
        )
        
        response_text = completion.choices[0].message.content
        scores = []
        total_score = 0
        
        for i, answer_pair in enumerate(request.questionAnswerPairs):
            score_pattern = rf"Q{i+1}_SCORE:\s*(\d+)"
            comment_pattern = rf"Q{i+1}_COMMENT:\s*(.+?)(?=Q\d+_SCORE:|$)"
            
            score_match = re.search(score_pattern, response_text)
            comment_match = re.search(comment_pattern, response_text, re.DOTALL)
            
            score = int(score_match.group(1)) if score_match else 0
            score = max(0, min(score, 10))
            comment = ' '.join((comment_match.group(1) if comment_match else "No comment provided").split()[:6])
            
            total_score += score
            scores.append(AnswerScore(
                id=answer_pair.id,
                question=answer_pair.question,
                answer=answer_pair.answer,
                score=score,
                comment=comment
            ))

        avg_score = total_score // len(request.questionAnswerPairs)
        
        return AnswerScoringResponse(root=scores)

    except Exception as e:
        logging.error(f"Error in score_answers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))