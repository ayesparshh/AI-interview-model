from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import PyPDF2
import io

app = FastAPI()

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

XAI_API_KEY = "xai-bDQHyZKnMNcSnDz2ARt0FF5kCEahZd40JYEls5Ty3NCJp4G1mjEWf1WK5GmhGnP3qrGuUK7rpifqZGVX"
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class AnalysisDetails(BaseModel):
    match_percentage: str
    key_matches: list[str]
    missing_skills: list[str]
    recommendations: list[str]

class JobMatchResponse(BaseModel):
    match_score: str
    analysis: AnalysisDetails

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        completion = client.chat.completions.create(
            model="grok-beta",
            messages=[
                {"role": "system", "content": "You are Grok, a chatbot inspired by the Hitchhikers Guide to the Galaxy."},
                {"role": "user", "content": request.message},
            ],
        )
        return ChatResponse(response=completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-cv", response_model=JobMatchResponse)
async def upload_cv(
    cv_file: UploadFile = File(...),
    job_description: str = Form(...)
):
    try:
        # Read and extract text from PDF
        pdf_content = await cv_file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        cv_text = ""
        for page in pdf_reader.pages:
            cv_text += page.extract_text()

        # Create prompt for analysis
        analysis_prompt = """
        Analyze the CV against the job description and provide a structured response. Break down your analysis into these EXACT sections:

        MATCH_PERCENTAGE: [Single percentage number]

        KEY_MATCHES:
        - [List each matching point]

        MISSING_SKILLS:
        - [List each missing skill]

        RECOMMENDATIONS:
        - [List each recommendation]

        Be concise and use bullet points. Start each section with the EXACT heading shown above.

        CV: {cv_text}
        Job Description: {job_description}
        """

        # Get analysis from X.AI
        completion = client.chat.completions.create(
            model="grok-beta",
            messages=[
                {"role": "system", "content": "You are a professional CV analyzer. Provide clear, structured analysis with specific details."},
                {"role": "user", "content": analysis_prompt.format(cv_text=cv_text, job_description=job_description)},
            ],
        )

        # Parse the response into structured format
        response_text = completion.choices[0].message.content
        sections = {
            "match_percentage": "",
            "key_matches": [],
            "missing_skills": [],
            "recommendations": []
        }

        current_section = None
        for line in response_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if 'MATCH_PERCENTAGE:' in line:
                current_section = "match_percentage"
                sections[current_section] = line.split(':')[1].strip().strip('%') + '%'
            elif 'KEY_MATCHES:' in line:
                current_section = "key_matches"
            elif 'MISSING_SKILLS:' in line:
                current_section = "missing_skills"
            elif 'RECOMMENDATIONS:' in line:
                current_section = "recommendations"
            elif line.startswith('- ') and current_section in ['key_matches', 'missing_skills', 'recommendations']:
                sections[current_section].append(line[2:])

        return JobMatchResponse(
            match_score=sections["match_percentage"],
            analysis=AnalysisDetails(
                match_percentage=sections["match_percentage"],
                key_matches=sections["key_matches"],
                missing_skills=sections["missing_skills"],
                recommendations=sections["recommendations"]
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)