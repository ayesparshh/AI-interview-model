from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Dict, List
import json
from ..models.embedding_models import EmbeddingResponse
import PyPDF2
import io
from ..embeddings import EmbeddingGenerator

router = APIRouter()

def extract_pdf_text(pdf_content: bytes) -> str:
    """Extract text from PDF content"""
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")

@router.post("/process-resume", response_model=EmbeddingResponse)
async def process_resume(
    file: UploadFile = File(...),
    userId: str = Form(...)
):
    try:
        pdf_content = await file.read()
        cv_text = extract_pdf_text(pdf_content)
        
        embedding_gen = EmbeddingGenerator("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")
        
        embeddings = embedding_gen.generate_embeddings([(cv_text, userId)])
        
        embedding_vector = embeddings.drop(['document_id', 'timestamp'], axis=1).values[0].tolist()
        
        return EmbeddingResponse(
            userId=userId,
            embeddings=embedding_vector,
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))