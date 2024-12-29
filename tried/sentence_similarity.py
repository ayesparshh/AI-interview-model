import requests

API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
headers = {"Authorization": "Bearer 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"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

if __name__ == "__main__":
    # Test the API with sample sentences
    test_payload = {
        "inputs": {
            "source_sentence": "That is a happy person",
            "sentences": [
                "That is a happy dog",
                "That is a very happy person",
                "Today is a sunny day"
            ]
        }
    }
    
    try:
        results = query(test_payload)
        print("Similarity scores:")
        for sentence, score in zip(test_payload["inputs"]["sentences"], results):
            # Convert score to float if it's not already
            score_val = float(score) if isinstance(score, (str, int)) else score
            print("'{}': {:.4f}".format(sentence, score_val))
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print("Full response:", results)
