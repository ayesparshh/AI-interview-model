import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from retry import retry
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    def __init__(self, api_token: str):
        self.model_id = "sentence-transformers/all-MiniLM-L6-v2"
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_id}"
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.output_dir = Path("embeddings_output")
        self.output_dir.mkdir(exist_ok=True)

    @retry(tries=3, delay=10, backoff=2, logger=logger)
    def query_api(self, texts: List[str]) -> List[List[float]]:
        """Query the HuggingFace API with retry logic"""
        try:
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json={"inputs": texts, "options": {"wait_for_model": True}}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def process_text(self, text: str) -> str:
        """Clean and prepare text for embedding"""
        return ' '.join(text.split())

    def generate_embeddings(self, texts: List[Tuple[str, str]]) -> pd.DataFrame:
        """Generate embeddings for a list of (text, label) tuples"""
        processed_texts = [(self.process_text(text), label) for text, label in texts]
        
        # Separate texts and labels
        text_list = [text for text, _ in processed_texts]
        labels = [label for _, label in processed_texts]

        try:
            embeddings = self.query_api(text_list)
            
            # Create DataFrame with labels and embeddings
            df = pd.DataFrame(embeddings)
            df.insert(0, 'document_id', labels)
            df.insert(1, 'timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            return df
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def save_embeddings(self, df: pd.DataFrame, filename: str):
        """Save embeddings to CSV with metadata"""
        try:
            # Create output path
            output_path = self.output_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Save to CSV
            df.to_csv(output_path, index=False)
            logger.info(f"Embeddings saved to {output_path}")
            
            # Save metadata
            metadata = {
                "model": self.model_id,
                "num_documents": len(df),
                "embedding_dim": len(df.columns) - 2,  # Subtract document_id and timestamp columns
                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            return output_path
        except Exception as e:
            logger.error(f"Failed to save embeddings: {e}")
            raise

def load_document(file_path: str, doc_id: str) -> Tuple[str, str]:
    """Load a document from file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content, doc_id
    except FileNotFoundError:
        logger.error(f"Document not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading document {file_path}: {e}")
        raise

def main():
    # Initialize embedding generator
    embedding_gen = EmbeddingGenerator("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")
    
    try:
        # Load job description
        job_desc, job_id = load_document('job_description.txt', 'job_description')
        
        # Load CVs
        cv_documents = []
        for i in range(1, 5):
            try:
                cv_content, cv_id = load_document(f'cv_folder/cv{i}.txt', f'cv_{i}')
                cv_documents.append((cv_content, cv_id))
            except FileNotFoundError:
                logger.warning(f"CV {i} not found, skipping...")
                continue
            except Exception as e:
                logger.error(f"Error processing CV {i}: {e}")
                continue
        
        if not cv_documents:
            raise ValueError("No valid CV documents found")

        # Combine job description and CVs
        all_documents = [(job_desc, job_id)] + cv_documents
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        embeddings_df = embedding_gen.generate_embeddings(all_documents)
        
        # Save embeddings
        output_path = embedding_gen.save_embeddings(embeddings_df, "document_embeddings")
        
        logger.info(f"Process completed successfully. Embeddings saved to {output_path}")
        
        # Display summary
        print("\nProcessing Summary:")
        print(f"Total documents processed: {len(embeddings_df)}")
        print(f"Embedding dimensions: {len(embeddings_df.columns) - 2}")
        print(f"Output file: {output_path}")
        
    except Exception as e:
        logger.error(f"Process failed: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {e}")
        exit(1)