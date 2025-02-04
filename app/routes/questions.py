from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Dict, Optional, Any
import json
import logging
from pydantic import BaseModel, Field
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
    
    return f"""You are an expert technical interviewer conducting a deep technical assessment.
Review the previous Q&A carefully:
{text}

IMPORTANT RULES FOR FOLLOW-UP QUESTIONS:
1. Your next question MUST directly build upon the candidate's previous answers
2. For React.memo answer: Probe deeper into performance optimization scenarios
3. For microservices answer: Question specific implementation details mentioned

Example flow:
If they mentioned "message queues for async operations", ask about:
- Specific message queue implementation choices
- Error handling and retry strategies
- Message ordering guarantees

RETURN JSON IN THIS FORMAT:
{{
    "questions": [
        {{
            "question": "Your technical follow-up question that digs deeper into previous answers",
            "time_minutes": {times[0]},
            "category": "{categories[0]}"
        }}
    ]
}}

Requirements:
1. Questions MUST reference specific details from previous answers
2. Focus on technical depth rather than breadth
3. Challenge assumptions made in previous answers
4. Ask for concrete implementation details
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
    jobDescription: str = Field(..., alias="jobDescription")
    skills: List[str]
    experienceRequired: int

class QuestionGenerationRequest(BaseModel):
    cv_data: str = Field(..., alias="cvParsedData")
    skill_description_map: Dict[str, str] = Field(..., alias="skillDescriptionMap")
    job_data: JobData = Field(..., alias="job")
    previous_questions: List[Dict[str, str]] = Field(default=[], alias="previousQuestions")
    expected_questions_config: List[Dict[str, Any]] = Field(..., alias="expectedQuestionsConfig")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True
        arbitrary_types_allowed = True

@router.post("/generate-questions", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest = Body(...)):
    try:
        previous_questions_text = ""
        if request.previous_questions:
            previous_questions_text = ""
            for qa in request.previous_questions:
                previous_questions_text += f"Q: {qa['question']}\nA: {qa['answer']}\n"

        job_context = f"""
        Job Title: {request.job_data.title}  # Updated field name
        Objective: {request.job_data.objective}
        Goals: {request.job_data.goals}
        Description: {request.job_data.jobDescription}
        Required Skills: {', '.join(request.job_data.skills)}
        Experience Required: {request.job_data.experienceRequired} years
        """

        skill_context = ""
        for skill, desc in request.skill_description_map.items():
            skill_context += f"- {skill}: {desc}\n"

        tech_context = f"""
        Following the data you need to consider when generating questions:
        CV Background:
        {request.cv_data}  # Updated field name
        Job Details:
        {job_context}
        User's Experience in required Skills:
        {skill_context}
        Previously Asked Questions during this Interview:
        {previous_questions_text}
        """

        completion = client.chat.complete(
            model=model,
            messages=[{
                "role": "system", 
                "content": f"""You are an expert interviewer specializing in {request.expected_questions_config[0]['category']} questions.
                Generate questions that are strictly {request.expected_questions_config[0]['category']} in nature.
                Do not mix technical and behavioral aspects unless specifically asked for."""
            }, {
                "role": "user",
                "content": create_structured_prompt(
                    tech_context, 
                    request.expected_questions_config[0]['category'],
                    len(request.expected_questions_config),
                    request.expected_questions_config
                )
            }]
        )

        response_content = completion.choices[0].message.content
        questions_data = json.loads(clean_json_string(response_content))
        questions = []
        
        for i, q in enumerate(questions_data.get("questions", [])):
            if i < len(request.expected_questions_config):
                config = request.expected_questions_config[i]
                
                question_data = {
                    "question": q["question"],
                    "estimated_time_minutes": config["expectedTimeToAnswer"],
                    "category": config["category"],
                    **{k: v for k, v in config.items() 
                       if k not in ["expectedTimeToAnswer", "category"]}
                }

                questions.append(QuestionWithTime(**question_data))

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