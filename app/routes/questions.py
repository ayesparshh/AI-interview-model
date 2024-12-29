from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Dict
import json
import logging
from pydantic import BaseModel
from ..models import QuestionGenerationResponse, QuestionWithTime
from ..prompts import QUESTION_GENERATION_PROMPT
from app.config import client
from .cv_matching import extract_pdf_text

logger = logging.getLogger(__name__)

router = APIRouter()

def chunk_text(text: str, max_length: int = 1000) -> List[str]:
    """Split text into chunks for processing"""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) > max_length:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
            
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks

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

def convert_text_to_json(content: str) -> str:
    """Convert text format to JSON if needed"""
    if content.strip().startswith('{'):
        return content
        
    questions = []
    current_question = None
    current_time = None
    
    for line in content.split('\n'):
        line = line.strip()
        if not line or line == '---':
            if current_question and current_time:
                questions.append({
                    "question": current_question,
                    "time_minutes": current_time
                })
                current_question = None
                current_time = None
            continue
            
        if "QUESTION:" in line:
            current_question = line.split("QUESTION:", 1)[1].strip()
        elif "TIME:" in line:
            try:
                time_str = line.split("TIME:", 1)[1].strip()
                current_time = int(float(time_str))
                current_time = min(max(current_time, 2), 6)
            except:
                current_time = 4
                
    if current_question and current_time:
        questions.append({
            "question": current_question,
            "time_minutes": current_time
        })
        
    return json.dumps({"questions": questions})

def parse_llm_response(content: str) -> List[QuestionWithTime]:
    """Parse LLM response with better error handling"""
    try:
        json_str = clean_json_string(content)
        
        data = json.loads(json_str)
        
        if not isinstance(data, dict) or "questions" not in data:
            raise ValueError("Invalid response structure")
            
        questions = []
        for q in data.get("questions", []):
            if not isinstance(q, dict):
                continue
                
            question = q.get("question", "").strip()
            time_minutes = q.get("time_minutes", 4)
            
            if not question:
                continue
                
            if not isinstance(time_minutes, (int, float)):
                time_minutes = 4
            time_minutes = min(max(int(time_minutes), 2), 6)
            
            questions.append(QuestionWithTime(
                question=question,
                estimated_time_minutes=time_minutes
            ))
            
        return questions
        
    except Exception as e:
        print(f"Failed to parse response: {str(e)}\nContent: {content}")
        return parse_llm_response_text(content)

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
async def generate_questions(
    request: QuestionGenerationRequest = Body(...)
):
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

        completion = client.chat.completions.create(
            model="grok-beta",
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
            ],
            temperature=0.7,
            max_tokens=2000
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
            questions = [
                QuestionWithTime(
                    question="Explain your experience with React.js and how you've used it in previous projects",
                    estimated_time_minutes=5
                ),
                QuestionWithTime(
                    question="Describe how you would design a scalable Node.js backend service",
                    estimated_time_minutes=6
                ),
                QuestionWithTime(
                    question="Walk through your approach to implementing authentication in a full-stack application",
                    estimated_time_minutes=4
                )
            ][:request.count]
            
        return QuestionGenerationResponse(questions=questions)
            
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate interview questions"
        )



# @router.post("/generate-questions", response_model=QuestionGenerationResponse)
# async def generate_questions(
#     cv_file: UploadFile = File(...),
#     job_description: str = Form(...),
#     previous_questions: str = Form(...),
#     num_questions: int = Form(...)
# ):
#     try:
#         pdf_content = await cv_file.read()
#         cv_text = extract_pdf_text(pdf_content)
        
#         cv_num = num_questions // 2
#         jd_num = num_questions - cv_num
        
#         cv_chunks = chunk_text(cv_text)
#         jd_chunks = chunk_text(job_description)
        
#         cv_questions = []
#         jd_questions = []
#         max_retries = 3
        
#         for chunk in cv_chunks:
#             if len(cv_questions) >= cv_num:
#                 break
                
#             for attempt in range(max_retries):
#                 try:
#                     cv_completion = client.chat.completions.create(
#                         model="grok-beta",
#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": """You are an expert technical interviewer. 
#                                 You MUST return only valid JSON matching the specified format.
#                                 Do not include any other text or explanations."""
#                             },
#                             {
#                                 "role": "user",
#                                 "content": create_structured_prompt(
#                                     chunk,
#                                     "cv",
#                                     min(cv_num - len(cv_questions), 2)
#                                 )
#                             }
#                         ],
#                         temperature=0.5,
#                         max_tokens=1000,
#                     )
                    
#                     response_content = cv_completion.choices[0].message.content.strip()
#                     new_questions = parse_llm_response(response_content)
                    
#                     if new_questions:
#                         cv_questions.extend(new_questions)
#                         break
                    
#                 except Exception as e:
#                     print(f"CV chunk processing attempt {attempt + 1} failed: {str(e)}")
#                     continue

#         for chunk in jd_chunks:
#             if len(jd_questions) >= jd_num:
#                 break
                
#             for attempt in range(max_retries):
#                 try:
#                     jd_completion = client.chat.completions.create(
#                         model="grok-beta",
#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": "You are an expert technical interviewer. Output MUST be valid JSON."
#                             },
#                             {
#                                 "role": "user",
#                                 "content": create_structured_prompt(
#                                     chunk,
#                                     "jd",
#                                     min(jd_num - len(jd_questions), 3)
#                                 )
#                             }
#                         ],
#                         temperature=0.7,
#                         max_tokens=1500,
#                     )
                    
#                     new_questions = parse_llm_response(jd_completion.choices[0].message.content)
#                     jd_questions.extend(new_questions)
#                     break
#                 except Exception as e:
#                     print(f"JD chunk processing attempt {attempt + 1} failed: {str(e)}")

#         questions = cv_questions[:cv_num] + jd_questions[:jd_num]
#         if not questions:
#             raise HTTPException(
#                 status_code=500,
#                 detail="Failed to generate any valid questions. Please try again."
#             )
            
#         return QuestionGenerationResponse(questions=questions[:num_questions])
        
#     except Exception as e:
#         print(f"Error generating questions: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))