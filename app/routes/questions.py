from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Dict, Optional, Any
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

def create_structured_prompt(text: str, question_type: str, num_questions: int, expected_config: List[Dict]) -> str:
    categories = [config["category"] for config in expected_config]
    times = [config["expectedTimeToAnswer"] for config in expected_config]
    
    return f"""Generate {num_questions} technical interview questions based on the provided context.
Each question should align with the job requirements and candidate's background, as well as consider the previously asked questions in the interview.

RETURN JSON IN THIS FORMAT:
{{
    "questions": [
        {{
            "question": "Your technical question here",
            "time_minutes": {times[0]},
            "category": "{categories[0]}",
            "sequence": 1
        }}
    ]
}}

Context:
{text}

Requirements:
1. Generate EXACTLY {num_questions} questions
2. Each question must be unique
3. Questions must match these categories: {', '.join(categories)}
4. Questions should take exactly the specified time: {', '.join(map(str, times))} minutes
5. Never repeat previous questions
6. Make questions progressively harder
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

class JobData(BaseModel):
    title: str
    objective: str
    goals: str 
    jobDescription: str
    skills: List[str]
    experienceRequired: int   

class QuestionGenerationRequest(BaseModel):
    cvParsedData: str 
    skillDescriptionMap: Dict[str, str]
    job: JobData
    previousQuestions: List[Dict[str, str]] = []
    expectedQuestionsConfig: List[Dict[str, Any]]

@router.post("/generate-questions", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest = Body(...)):
    try:
        previous_questions_text = ""
        if request.previousQuestions:
            previous_questions_text = ""
            for qa in request.previousQuestions:
                previous_questions_text += f"Q: {qa['question']}\nA: {qa['answer']}\n"

        job_context = f"""
        Job Title: {request.job.title}
        Objective: {request.job.objective}
        Goals: {request.job.goals}
        Description: {request.job.jobDescription}
        Required Skills: {', '.join(request.job.skills)}
        Experience Required: {request.job.experienceRequired} years
        """

        skill_context = ""
        for skill, desc in request.skillDescriptionMap.items():
            skill_context += f"- {skill}: {desc}\n"

        tech_context = f"""
        Following the data you need to consider when generating questions:
        CV Background:
        {request.cvParsedData}
        Job Details:
        {job_context}
        User's Experience in required Skills:
        {skill_context}
        Previously Asked Questions during this Interview (Take these into context when asking future questions) (You may ignore questions which were not answered):
        {previous_questions_text}
        """

        completion = client.chat.complete(
            model=model,
            messages=[{
                "role": "system", 
                "content": "You are an expert technical interviewer. Generate questions exactly matching the specified categories and times."
            }, {
                "role": "user",
                "content": create_structured_prompt(
                    tech_context, 
                    "technical", 
                    len(request.expectedQuestionsConfig),
                    request.expectedQuestionsConfig
                )
            }]
        )

        response_content = completion.choices[0].message.content
        questions_data = json.loads(clean_json_string(response_content))
        questions = []
        
        for i, q in enumerate(questions_data.get("questions", [])):
            if i < len(request.expectedQuestionsConfig):
                config = request.expectedQuestionsConfig[i]
                questions.append(QuestionWithTime(
                    question=q["question"],
                    estimated_time_minutes=config["expectedTimeToAnswer"],
                    category=config["category"],
                    sequenceNumber=config["sequenceNumber"]
                ))

        return QuestionGenerationResponse(questions=questions)

    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate questions")

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