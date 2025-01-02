from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Dict, Optional
import json
import logging
from pydantic import BaseModel
from ..models import (
    QuestionGenerationResponse, 
    QuestionWithTime,
    QuestionWithDifficulty,
    FollowUpQuestionRequest
)
from ..prompts import QUESTION_GENERATION_PROMPT, FOLLOW_UP_QUESTION_PROMPT
from app.config import client, model

logger = logging.getLogger(__name__)

router = APIRouter()

def clean_json_string(content: str) -> str:
    """Clean and prepare string for JSON parsing"""
    start = content.find('{')
    end = content.rfind('}')
    
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in response")
    json_str = content[start:end + 1]
    
    json_str = json_str.strip('`').strip('"').strip("'")
    
    return json_str

def create_structured_prompt(text: str, question_type: str, num_questions: int) -> str:
    """Create a more specific prompt for technical questions"""
    return f"""Generate {num_questions} technical interview questions about {question_type}.
Focus on practical, real-world scenarios and problem-solving.

STRICTLY RETURN JSON IN THIS FORMAT:
{{
    "questions": [
        {{
            "question": "Your technical question here",
            "time_minutes": 4
        }}
    ]
}}

Context:
{text}

Requirements:
1. Questions must be detailed technical questions
2. Focus on hands-on experience
3. Include system design and architecture
4. Cover best practices and patterns
5. Ask about real-world problem solving

Example valid question structures:
- Explain how you would implement X using Y
- Design a system that handles X with Y requirements
- Describe your experience with X and how you solved Y
- Walk through your approach to implementing X
"""

def parse_llm_response_text(content: str) -> list[QuestionWithTime]:
    questions = []
    current_question = None
    current_time = None
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('QUESTION:') or line.startswith('Q:') or (line[0].isdigit() and '.' in line[:3]):
            if current_question and current_time:
                questions.append(QuestionWithTime(
                    question=current_question,
                    estimated_time_minutes=current_time
                ))
            current_question = line.split(':', 1)[-1].strip()
            if current_question.startswith('.'):
                current_question = current_question[1:].strip()
            current_time = 4 
        elif line.startswith('TIME:') or line.startswith('T:') or 'minutes' in line.lower():
            try:
                time_str = ''.join(filter(str.isdigit, line))
                if time_str:
                    current_time = min(max(int(time_str), 2), 6)
            except ValueError:
                current_time = 4

    if current_question and current_time:
        questions.append(QuestionWithTime(
            question=current_question,
            estimated_time_minutes=current_time
        ))
    
    return questions

class QuestionGenerationRequest(BaseModel):
    cv_data: str
    job_description: str
    count: int = 3

@router.post("/generate-questions", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest = Body(...)):
    """Generates interview questions based on CV and job description."""
    try:
        tech_context = f"""
        CV Technology Background:
        {request.cv_data}
        
        Job Requirements:
        {request.job_description}
        
        Generate questions that assess both the candidate's experience ({request.cv_data}) 
        and the job requirements ({request.job_description}).
        """

        completion = client.chat.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert technical interviewer specializing in software engineering.
                    Always return responses in valid JSON format matching the specified structure."""
                },
                {
                    "role": "user",
                    "content": create_structured_prompt(tech_context, "software engineering", request.count)
                }
            ]
        )

        response_content = completion.choices[0].message.content
        
        try:
            data = json.loads(clean_json_string(response_content))
            questions = [
                QuestionWithTime(
                    question=q["question"],
                    estimated_time_minutes=min(max(int(q.get("time_minutes", 4)), 2), 6)
                )
                for q in data.get("questions", [])
                if q.get("question")
            ][:request.count]
            
        except json.JSONDecodeError:
            questions = parse_llm_response_text(response_content)[:request.count]
        
        if not questions:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate valid questions from AI"
            )
            
        return QuestionGenerationResponse(questions=questions)
            
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate interview questions"
        )

def parse_follow_up_response(content: str) -> dict:
    """Clean and parse LLM response into structured format"""
    try:
        content = ' '.join(content.split())
        
        json_pattern = r'\{.*\}'
        import re
        match = re.search(json_pattern, content)
        if not match:
            raise ValueError("No JSON object found in response")
            
        json_str = match.group(0)
        
        data = json.loads(json_str)
        
        return {
            "question": str(data.get("question", "")).strip(),
            "estimated_time_minutes": min(max(int(data.get("time_minutes", 5)), 3), 6),
            "difficulty_increase": str(data.get("difficulty_increase", "significant")),
            "related_concepts": list(data.get("related_concepts", []))[:3]
        }
    except Exception as e:
        logger.error(f"Parse error details: {str(e)}\nRaw content: {content}")
        raise

class FollowUpQuestionRequest(BaseModel):
    original_question: str
    provided_answer: str

class SimpleQuestionResponse(BaseModel):
    question: str
    estimated_time_minutes: int

@router.post("/generate-follow-up", response_model=SimpleQuestionResponse)
async def generate_follow_up(request: FollowUpQuestionRequest = Body(...)):
    """Generates a follow-up question based on original question and answer."""
    try:
        system_prompt = """You are an expert technical interviewer. You must respond with ONLY a valid JSON object.
Format:
{
    "question": "Your detailed technical follow-up question here",
    "time_minutes": 5
}"""

        user_prompt = f"""Based on:
Original Question: {request.original_question}
Candidate Answer: {request.provided_answer}

Generate a more challenging follow-up question that delves deeper into the technical aspects."""

        completion = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        response_text = completion.choices[0].message.content
        logger.debug(f"Raw LLM response: {response_text}")

        try:
            clean_json = clean_json_string(response_text)
            data = json.loads(clean_json)
            return SimpleQuestionResponse(
                question=data["question"],
                estimated_time_minutes=min(max(int(data.get("time_minutes", 5)), 3), 6)
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate valid follow-up question"
            )

    except Exception as e:
        logger.error(f"Error in follow-up generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate follow-up question: {str(e)}"
        )