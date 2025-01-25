from app.db.database import init_db

from app.models.embedding_models import Candidate, JobDescription

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")