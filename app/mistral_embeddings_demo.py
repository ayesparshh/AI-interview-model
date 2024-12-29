import os
import time
try:
    import numpy as np
except ImportError:
    print("Installing required dependencies...")
    import subprocess
    subprocess.check_call(["pip", "install", "numpy"])
    import numpy as np

from langchain_mistralai import MistralAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

# Set API key properly
api_key = "omgMZB6SpQcMsqYzPsju1HSGrYKjVSPg"
os.environ["MISTRAL_API_KEY"] = api_key

def process_with_delay(func, *args, delay=2, **kwargs):
    """Execute function with delay to avoid rate limits"""
    try:
        result = func(*args, **kwargs)
        time.sleep(delay)
        return result
    except Exception as e:
        print(f"Error occurred: {e}")
        time.sleep(delay * 2)
        return None

def init_vector_store(texts, embeddings):
    """Initialize vector store with error handling"""
    try:
        return InMemoryVectorStore.from_texts(
            texts,
            embedding=embeddings,
        )
    except Exception as e:
        print(f"Error initializing vector store: {e}")
        return None

def main():
    embeddings = MistralAIEmbeddings(
        model="mistral-embed",
        mistral_api_key=api_key
    )

    text1 = "LangChain is the framework for building context-aware reasoning applications"
    text2 = "LangGraph is a library for building stateful, multi-actor applications with LLMs"

    print("\nSingle text embedding example:")
    single_vector = process_with_delay(embeddings.embed_query, text1)
    if single_vector:
        print(f"Vector dimension: {len(single_vector)}")
        print(f"First few values: {single_vector[:5]}")

    print("\nMultiple text embedding example:")
    vectors = process_with_delay(embeddings.embed_documents, [text1])
    if vectors:
        print(f"Number of vectors: {len(vectors)}")
        print(f"Vector dimension: {len(vectors[0])}")

    print("\nVector store example:")
    vectorstore = init_vector_store([text1], embeddings)
    
    if vectorstore:
        print("\nRetrieval example:")
        retriever = vectorstore.as_retriever()
        result = process_with_delay(retriever.invoke, "What is LangChain?")
        if result:
            print(f"Retrieved content: {result[0].page_content}")
    else:
        print("Skipping retrieval due to vector store initialization failure")

if __name__ == "__main__":
    main()
