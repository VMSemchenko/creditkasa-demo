# CreditKasa Support AI Copilot Demo

This project demonstrates a production-ready AI pipeline for customer support, designed specifically for the AI Engineer vacancy at CreditKasa.

## Architecture

1. **Intake & Orchestration:** n8n acts as the workflow engine to receive customer queries.
2. **Knowledge Retrieval (RAG):** Qdrant Vector Database stores internal guidelines (e.g., Loan Restructuring Policies).
3. **Analysis & Generation:** OpenAI (via LangChain and n8n) analyzes the query, searches the vector database, and generates a structured draft response.
4. **Human-in-the-Loop:** The draft is queued for human review before being sent back to the customer.

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone git@github.com:VMSemchenko/creditkasa-demo.git
   cd creditkasa-demo
   ```

2. **Start Infrastructure (n8n & Qdrant):**
   ```bash
   docker-compose up -d
   ```
   - Qdrant will be available at `http://localhost:6333`
   - n8n will be available at `http://localhost:5678`

3. **Ingest Mock Policies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   Create a `.env` file in the root directory and add your `OPENAI_API_KEY`:
   ```env
   OPENAI_API_KEY=sk-your-key-here
   ```
   Run the ingestion script:
   ```bash
   python src/ingest_policies.py
   ```

4. **Build the n8n Workflow:**
   - Open `http://localhost:5678`.
   - Create a new workflow triggered by a Webhook.
   - Use the AI Agent or Basic LLM Chain nodes to connect to OpenAI.
   - Use the Qdrant node to connect to the `creditkasa_policies` collection.
   - Design the prompt to draft a response based on the retrieved context.
