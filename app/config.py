import os
import logging
from logging.handlers import RotatingFileHandler
import pathlib
from mistralai import Mistral

log_dir = pathlib.Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "server.log"

with open(log_file, 'w') as f:
    f.write("")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            log_file,
            maxBytes=10485760,
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

MISTRAL_API_KEY = "omgMZB6SpQcMsqYzPsju1HSGrYKjVSPg"
client = Mistral(api_key=MISTRAL_API_KEY)
model = "mistral-large-latest"

# uvicorn app.main:app --reload
# python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# docker exec -it mypostgres psql -U user -d dbname
# python -m app.db.init_db