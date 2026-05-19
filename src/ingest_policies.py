"""
Ingests all markdown documents from the /docs folder into Qdrant.
Supports loading multiple files at once with metadata tagging.
"""
import os
import glob
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore

from config import QDRANT_URL, COLLECTION_NAME, get_embeddings, OPENAI_API_KEY


DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')


def ingest_documents():
    """Load all .md files from docs/, chunk them, and upsert into Qdrant."""
    md_files = glob.glob(os.path.join(DOCS_DIR, '*.md'))
    if not md_files:
        print(f"No markdown files found in {DOCS_DIR}")
        return

    all_docs = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )

    for filepath in md_files:
        filename = os.path.basename(filepath)
        print(f"  Loading: {filename}")
        loader = TextLoader(filepath, encoding="utf-8")
        documents = loader.load()
        # Tag each chunk with the source document name
        for doc in documents:
            doc.metadata["source_document"] = filename
        chunks = text_splitter.split_documents(documents)
        all_docs.extend(chunks)

    print(f"\nTotal chunks across {len(md_files)} file(s): {len(all_docs)}")
    print("Generating embeddings and upserting into Qdrant...")

    embeddings = get_embeddings()

    QdrantVectorStore.from_documents(
        all_docs,
        embeddings,
        url=QDRANT_URL,
        prefer_grpc=False,
        collection_name=COLLECTION_NAME,
        force_recreate=True,
    )

    print(f"✅ Ingestion complete! Collection '{COLLECTION_NAME}' is ready.")


if __name__ == "__main__":
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not set. Create a .env file (see .env.example).")
    else:
        ingest_documents()
