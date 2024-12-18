from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import PyPDF2
import io
from ..models import (
    JobMatchResponse, 
    AnalysisDetails, 
    StructuredJobDescription,
    TabularAnalysis,
    JobRequirement,
    JobApplicationForm
)
from ..prompts import CV_ANALYSIS_PROMPT
from app.config import client

router = APIRouter()

def generate_requirements_table(job_desc: StructuredJobDescription) -> str:
    table_rows = []
    for skill_set in job_desc.mandatory_skills:
        for skill in skill_set['skills']:
            table_rows.append(
                f"| {skill} | Required | Mandatory |"
            )
    
    if job_desc.skills_experience.get('preferred'):
        preferred_skills = job_desc.skills_experience['preferred'].split(',')
        for skill in preferred_skills:
            if skill.strip():
                table_rows.append(
                    f"| {skill.strip()} | Preferred | Optional |"
                )
    
    return "\n".join(table_rows)

@router.post("/upload-cv", response_model=JobMatchResponse)
async def upload_cv(
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
    mandatory_skill_1: str = Form(...),
    mandatory_skill_2: str = Form(...),
    mandatory_skill_3: str = Form(...),
    mandatory_skill_4: str = Form(...),
    mandatory_skill_5: str = Form(...),
    preferred_skills: str = Form(...),
    current_address: str = Form(...),
    expected_salary: str = Form(...),
    notice_period: int = Form(...),
    cover_letter: UploadFile = File(None)
):
    try:
        
        application_data = JobApplicationForm(
            mandatory_skill_1=mandatory_skill_1,
            mandatory_skill_2=mandatory_skill_2,
            mandatory_skill_3=mandatory_skill_3,
            mandatory_skill_4=mandatory_skill_4,
            mandatory_skill_5=mandatory_skill_5,
            preferred_skills=preferred_skills,
            current_address=current_address,
            expected_salary=expected_salary,
            notice_period=notice_period
        )
        
        pdf_content = await cv_file.read()
        cv_text = extract_pdf_text(pdf_content)

        cover_letter_text = ""
        if cover_letter:
            cover_letter_content = await cover_letter.read()
            cover_letter_text = extract_pdf_text(cover_letter_content)
            cv_text = f"{cv_text}\n\nCover Letter:\n{cover_letter_text}"

        job_desc = parse_job_description(job_description, application_data)

        tabular_analysis = create_tabular_analysis(cv_text, job_desc)

        requirements_table = generate_requirements_table(job_desc)
        
        completion = client.chat.completions.create(
            model="grok-beta",
            messages=[
                {
                    "role": "system", 
                    "content": """You are a professional CV analyzer. Always start your response with a clear match percentage.
                                The percentage should be a single number between 0-100 based on how well the CV matches the job requirements.
                                Example: MATCH_PERCENTAGE: 75"""
                },
                {"role": "user", "content": CV_ANALYSIS_PROMPT.format(
                    cv_text=cv_text, 
                    job_description=job_description,
                    application_data=application_data.dict(),
                    requirements_table=requirements_table
                )},
            ],
            temperature=0.7,
        )
        
        analysis = parse_cv_analysis(completion.choices[0].message.content, tabular_analysis)
        
        return analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_pdf_text(pdf_content: bytes) -> str:
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
    text = " ".join(page.extract_text() for page in pdf_reader.pages)
    print("\n=== Extracted CV Text ===")
    print(text)
    print("=== End of CV Text ===\n")
    return text

def parse_cv_analysis(response_text: str, tabular_analysis: TabularAnalysis) -> JobMatchResponse:
    sections = {
        "match_percentage": "0%",
        "key_matches": [],
        "missing_skills": [],
        "recommendations": []
    }

    try:
        for line in response_text.split('\n'):
            line = line.strip()
            if 'MATCH_PERCENTAGE:' in line:
                try:
                    percentage = line.split(':')[1].strip()
                    percentage = ''.join(filter(str.isdigit, percentage))
                    if percentage:
                        percentage_value = int(percentage)
                        if 0 <= percentage_value <= 100:
                            sections["match_percentage"] = f"{percentage_value}%"
                            break
                except (ValueError, IndexError):
                    continue

        current_section = None
        for line in response_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if 'KEY_MATCHES:' in line:
                current_section = "key_matches"
            elif 'MISSING_SKILLS:' in line:
                current_section = "missing_skills"
            elif 'RECOMMENDATIONS:' in line:
                current_section = "recommendations"
            elif line.startswith('- ') and current_section in ['key_matches', 'missing_skills', 'recommendations']:
                sections[current_section].append(line[2:])

        if sections["match_percentage"] == "0%":
            total_skills = len(tabular_analysis.requirements)
            if total_skills > 0:
                matched_skills = sum(1 for req in tabular_analysis.requirements if "100% match" in req.match_status)
                percentage = int((matched_skills / total_skills) * 100)
                sections["match_percentage"] = f"{percentage}%"

    except Exception as e:
        print(f"Error parsing CV analysis: {str(e)}")

    return JobMatchResponse(
        match_score=sections["match_percentage"],
        tabular_analysis=tabular_analysis,
        analysis=AnalysisDetails(
            match_percentage=sections["match_percentage"],
            key_matches=sections["key_matches"][:5] if sections["key_matches"] else ["No matches found"],
            missing_skills=sections["missing_skills"][:5] if sections["missing_skills"] else ["Skills assessment unavailable"],
            recommendations=sections["recommendations"][:1] if sections["recommendations"] else ["No recommendations available"]
        )
    )

def parse_job_description(job_description: str, application_data: JobApplicationForm) -> StructuredJobDescription:
    structured_data = {
        'title': '',
        'objective': '',
        'goals': '',
        'address': application_data.current_address,
        'work_model': '',
        'job_type': '',
        'salary_range': application_data.expected_salary,
        'mandatory_skills': [
            {'skills': [application_data.mandatory_skill_1], 'experience': ''},
            {'skills': [application_data.mandatory_skill_2], 'experience': ''},
            {'skills': [application_data.mandatory_skill_3], 'experience': ''},
            {'skills': [application_data.mandatory_skill_4], 'experience': ''},
            {'skills': [application_data.mandatory_skill_5], 'experience': ''}
        ],
        'skills_experience': {'preferred': application_data.preferred_skills},
        'location_details': {'notice_period': application_data.notice_period}
    }

    lines = job_description.split('\n')
    for line in lines:
        if line.startswith('Job Title:'):
            structured_data['title'] = line.split(':', 1)[1].strip()
            
    return StructuredJobDescription(**structured_data)

def create_tabular_analysis(cv_text: str, job_desc: StructuredJobDescription) -> TabularAnalysis:
    requirements = []

    for skill_set in job_desc.mandatory_skills:
        for skill in skill_set['skills']:
            requirements.append(JobRequirement(
                requirement=skill,
                expectation=f"{skill_set['experience']} experience",
                match_status="100% match" if skill.lower() in cv_text.lower() else "Not found"
            ))

    distance = calculate_distance(cv_text, job_desc.address)
    travel_time = calculate_travel_time(distance)
    
    return TabularAnalysis(
        requirements=requirements,
        candidate_distance=f"{distance} KM",
        travel_time=f"{travel_time} hours"
    )

def calculate_distance(cv_text: str, job_address: str) -> float:

    return 6000.0

def calculate_travel_time(distance: float) -> float:
    return distance / 800