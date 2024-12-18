from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import chat, cv_matching, multiple_jobs, questions, answers

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(cv_matching.router)
app.include_router(multiple_jobs.router)
app.include_router(questions.router)
app.include_router(answers.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)