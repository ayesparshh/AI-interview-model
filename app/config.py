import os
from mistralai import Mistral

MISTRAL_API_KEY = "omgMZB6SpQcMsqYzPsju1HSGrYKjVSPg"
client = Mistral(
    api_key=MISTRAL_API_KEY
)

model = "mistral-large-latest"