from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class DifficultyLevel(str, Enum):
    HARDER = "harder"
    EXPERT = "expert"
    ADVANCED = "advanced"
    COMPLEX = "complex"

class TopicArea(str, Enum):
    SYSTEM_DESIGN = "system design"
    ALGORITHMS = "algorithms"
    ARCHITECTURE = "architecture"
    SCALABILITY = "scalability"
    PERFORMANCE = "performance"
    CACHING = "caching"
    DISTRIBUTED_SYSTEMS = "distributed systems"

class QuestionWithTime(BaseModel):
    question: str
    estimated_time_minutes: int
    category: str
    sequenceNumber: int

class QuestionGenerationResponse(BaseModel):
    questions: List[QuestionWithTime]

class FollowUpQuestionRequest(BaseModel):
    original_question: str
    provided_answer: str
    topic_area: TopicArea = Field(default=TopicArea.SYSTEM_DESIGN)
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.HARDER)

class QuestionWithDifficulty(QuestionWithTime):
    difficulty_increase: str
    related_concepts: List[str]