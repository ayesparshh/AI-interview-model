from pydantic import BaseModel
from typing import List

class EmbeddingResponse(BaseModel):
    userId: str
    embeddings: List[float]
    status: str