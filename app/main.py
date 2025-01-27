from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import questions, cv_embed, job_match, answers, job_embed
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application server")
    yield
    logger.info("Shutting down application server")

app = FastAPI(lifespan=lifespan)

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
    logger.info("Starting development server")
    uvicorn.run(app, host="0.0.0.0", port=8000)