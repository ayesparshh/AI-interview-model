from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Dict
import json
from ..models import QuestionGenerationResponse, QuestionWithTime
from ..prompts import QUESTION_GENERATION_PROMPT
from app.config import client
from .cv_matching import extract_pdf_text

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
    # Find the first { and last }
    start = content.find('{')
    end = content.rfind('}')
    
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in response")
        
    # Extract just the JSON part
    json_str = content[start:end + 1]
    
    # Remove any markdown formatting or quotes around the JSON
    json_str = json_str.strip('`').strip('"').strip("'")
    
    return json_str

def create_structured_prompt(text: str, question_type: str, num_questions: int) -> str:
    template = {
        "cv": """Generate {n} technical interview questions based on this CV section.
Return ONLY a JSON object in this exact format, nothing else:
{{
    "questions": [
        {{
            "question": "Question text here",
            "time_minutes": 4,
            "focus_area": "Technical Skills"
        }}
    ]
}}

CV Section: {text}

Rules:
1. Output must be VALID JSON only
2. Questions must be specific to experience
3. time_minutes must be between 2-6
4. No explanations, only JSON""",

        "jd": """Generate {n} technical interview questions based on this job requirements.
Return ONLY a JSON object in this exact format, nothing else:
{{
    "questions": [
        {{
            "question": "Question text here",
            "time_minutes": 4,
            "focus_area": "Required Skills"
        }}
    ]
}}

Job Description: {text}

Rules:
1. Output must be VALID JSON only
2. Questions must match requirements
3. time_minutes must be between 2-6
4. No explanations, only JSON"""
    }
    
    return template[question_type].format(n=num_questions, text=text)

def parse_llm_response(content: str) -> List[QuestionWithTime]:
    """Parse LLM response with better error handling"""
    try:
        # Clean and prepare the JSON string
        json_str = clean_json_string(content)
        
        # Parse JSON
        data = json.loads(json_str)
        
        # Validate structure
        if not isinstance(data, dict) or "questions" not in data:
            raise ValueError("Invalid response structure")
            
        questions = []
        for q in data.get("questions", []):
            if not isinstance(q, dict):
                continue
                
            question = q.get("question", "").strip()
            time_minutes = q.get("time_minutes", 4)
            
            # Validate question
            if not question:
                continue
                
            # Validate and normalize time
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
        # Try fallback parsing if JSON fails
        return parse_llm_response_text(content)

def parse_llm_response_text(content: str) -> list[QuestionWithTime]:
    questions = []
    current_question = None
    current_time = None
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Handle different question formats
        if line.startswith('QUESTION:') or line.startswith('Q:') or (line[0].isdigit() and '.' in line[:3]):
            if current_question and current_time:
                questions.append(QuestionWithTime(
                    question=current_question,
                    estimated_time_minutes=current_time
                ))
            current_question = line.split(':', 1)[-1].strip()
            if current_question.startswith('.'):
                current_question = current_question[1:].strip()
            current_time = 4  # Default time if not specified
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

@router.post("/generate-questions", response_model=QuestionGenerationResponse)
async def generate_questions(
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
    previous_questions: str = Form(...),
    num_questions: int = Form(...)
):
    try:
        pdf_content = await cv_file.read()
        cv_text = extract_pdf_text(pdf_content)
        
        cv_num = num_questions // 2
        jd_num = num_questions - cv_num
        
        # Split texts into manageable chunks
        cv_chunks = chunk_text(cv_text)
        jd_chunks = chunk_text(job_description)
        
        cv_questions = []
        jd_questions = []
        max_retries = 3
        
        # Generate CV-based questions from chunks
        for chunk in cv_chunks:
            if len(cv_questions) >= cv_num:
                break
                
            for attempt in range(max_retries):
                try:
                    cv_completion = client.chat.completions.create(
                        model="grok-beta",
                        messages=[
                            {
                                "role": "system",
                                "content": """You are an expert technical interviewer. 
                                You MUST return only valid JSON matching the specified format.
                                Do not include any other text or explanations."""
                            },
                            {
                                "role": "user",
                                "content": create_structured_prompt(
                                    chunk,
                                    "cv",
                                    min(cv_num - len(cv_questions), 2)  # Reduced to 2 questions per chunk
                                )
                            }
                        ],
                        temperature=0.5,  # Reduced temperature for more consistent output
                        max_tokens=1000,
                    )
                    
                    response_content = cv_completion.choices[0].message.content.strip()
                    new_questions = parse_llm_response(response_content)
                    
                    if new_questions:  # Only extend if we got valid questions
                        cv_questions.extend(new_questions)
                        break
                    
                except Exception as e:
                    print(f"CV chunk processing attempt {attempt + 1} failed: {str(e)}")
                    continue

        # Similar structure for JD questions
        for chunk in jd_chunks:
            if len(jd_questions) >= jd_num:
                break
                
            for attempt in range(max_retries):
                try:
                    jd_completion = client.chat.completions.create(
                        model="grok-beta",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert technical interviewer. Output MUST be valid JSON."
                            },
                            {
                                "role": "user",
                                "content": create_structured_prompt(
                                    chunk,
                                    "jd",
                                    min(jd_num - len(jd_questions), 3)  # Generate max 3 questions per chunk
                                )
                            }
                        ],
                        temperature=0.7,
                        max_tokens=1500,
                    )
                    
                    new_questions = parse_llm_response(jd_completion.choices[0].message.content)
                    jd_questions.extend(new_questions)
                    break
                except Exception as e:
                    print(f"JD chunk processing attempt {attempt + 1} failed: {str(e)}")

        # Combine and validate questions
        questions = cv_questions[:cv_num] + jd_questions[:jd_num]
        if not questions:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate any valid questions. Please try again."
            )
            
        return QuestionGenerationResponse(questions=questions[:num_questions])
        
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))