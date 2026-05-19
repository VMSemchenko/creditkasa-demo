import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

load_dotenv()

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "creditkasa_policies"

def ingest_documents():
    docs_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'mock_loan_policy.md')
    print(f"Loading document from: {docs_path}")
    
    loader = TextLoader(docs_path)
    documents = loader.load()
    
    print(f"Loaded {len(documents)} document(s). Splitting...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    
    print(f"Split into {len(docs)} chunks. Initializing embeddings and vector store...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Store in Qdrant
    qdrant = QdrantVectorStore.from_documents(
        docs,
        embeddings,
        url=QDRANT_URL,
        prefer_grpc=False,
        collection_name=COLLECTION_NAME,
        force_recreate=True
    )
    
    print("Ingestion complete! Data is now available in Qdrant.")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set in the environment or .env file.")
    else:
        ingest_documents()
