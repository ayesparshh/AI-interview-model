import os
from mistralai import Mistral

MISTRAL_API_KEY = "omgMZB6SpQcMsqYzPsju1HSGrYKjVSPg"
client = Mistral(
    api_key=MISTRAL_API_KEY
)

model = "mistral-large-latest"

# uvicorn app.main:app --reload
# python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# docker exec -it mypostgres psql -U user -d dbname
#  python -m app.db.init_db