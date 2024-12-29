import requests
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
headers = {"Authorization": "Bearer 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"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

def clean_text(text):
    """Cleans the text by removing irrelevant characters, lowercasing, etc."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = text.lower()
    return text

def tokenize_text(text):
    """Tokenizes the text into individual words."""
    return nltk.word_tokenize(text)

def remove_stopwords(tokens):
    """Removes common stop words from the tokens."""
    stop_words = set(stopwords.words('english'))
    return [token for token in tokens if token not in stop_words]

def lemmatize_tokens(tokens):
    """Reduces tokens to their base form using lemmatization."""
    lemmatizer = WordNetLemmatizer()
    return [lemmatizer.lemmatize(token) for token in tokens]

# def preprocess_text(text):
#     """Combines all preprocessing steps."""
#     cleaned_text = clean_text(text)
#     tokens = tokenize_text(cleaned_text)
#     tokens = remove_stopwords(tokens)
#     tokens = lemmatize_tokens(tokens)
#     return " ".join(tokens)

def get_embedding(text):
    """Gets the vector embedding for the given text using the Hugging Face API."""
    try:
        payload = {
            "inputs": {
                "source_sentence": text,
                "sentences": [text]
            }
        }
        output = query(payload)
        return output[0] if isinstance(output, list) else 0.0
    except Exception as e:
        raise Exception(f"Embedding error: {str(e)}")

def calculate_similarity(processed_cv, processed_job):
    """Calculates the similarity between CV and job description."""
    try:
        payload = {
            "inputs": {
                "source_sentence": processed_job,
                "sentences": [processed_cv]
            }
        }
        scores = query(payload)
        return scores[0] if isinstance(scores, list) else 0.0
    except Exception as e:
        raise Exception(f"Similarity calculation error: {str(e)}")

def preprocess_text(text):
    """Combines all preprocessing steps."""
    
    text = re.sub(r'[^\w\s]', ' ', text)
    text = ' '.join(text.split())
    text = text.lower()
    
    tokens = nltk.word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    tokens = [token for token in tokens if token not in stop_words]
    
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(token) for token in tokens]
    
    return ' '.join(tokens)

def match_cvs_to_job_description(job_description_path, cv_folder):
    """Matches CVs in a folder to a job description using sentence similarity."""
    try:
        if not os.path.isfile(job_description_path):
            raise FileNotFoundError(f"Job description file not found: {job_description_path}")
        if not os.path.isdir(cv_folder):
            raise NotADirectoryError(f"CV folder not found: {cv_folder}")

        cv_files = [f for f in os.listdir(cv_folder) if f.endswith('.txt')]
        if not cv_files:
            raise FileNotFoundError(f"No CV files (.txt) found in {cv_folder}")

        with open(job_description_path, 'r', encoding='utf-8') as f:
            job_description_text = f.read()
            if not job_description_text.strip():
                raise ValueError("Job description file is empty")
        
        processed_job = preprocess_text(job_description_text)
        
        cv_scores = []
        for filename in cv_files:
            try:
                cv_path = os.path.join(cv_folder, filename)
                with open(cv_path, 'r', encoding='utf-8') as f:
                    cv_text = f.read()
                    if not cv_text.strip():
                        print(f"Warning: {filename} is empty")
                        continue
                
                processed_cv = preprocess_text(cv_text)
                
                similarity_score = calculate_similarity(processed_cv, processed_job)
                cv_scores.append((filename, similarity_score))
                
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                continue

        if not cv_scores:
            raise ValueError("No CVs were successfully processed")

        ranked_cvs = sorted(cv_scores, key=lambda x: x[1], reverse=True)
        return ranked_cvs

    except Exception as e:
        print(f"Error in CV matching process: {str(e)}")
        return []

if __name__ == "__main__":
    try:
        print("Starting CV matching process...")
        print("Reading job description and CVs...")
        
        ranked_cvs = match_cvs_to_job_description('job_description.txt', 'cv_folder')
        
        if ranked_cvs:
            print("\nRanked CVs based on similarity to the job description:")
            print("-" * 50)
            for filename, score in ranked_cvs:
                print(f"CV: {filename:<20} Similarity: {score:.4f}")
            print("-" * 50)
            
            best_match = ranked_cvs[0]
            print(f"\nBest Match: {best_match[0]}")
            print(f"Similarity Score: {best_match[1]:.4f}")
        else:
            print("No results found. Please check the error messages above.")
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    finally:
        print("\nCV matching process completed.")