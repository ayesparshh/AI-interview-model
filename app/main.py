from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import questions,cv_embed,job_match,answers
from .routes import job_embed

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router)
app.include_router(cv_embed.router)
app.include_router(job_match.router)
app.include_router(answers.router)
app.include_router(job_embed.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)