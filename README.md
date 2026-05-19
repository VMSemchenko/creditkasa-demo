# CreditKasa Support AI Copilot

An AI-powered customer support draft generation system with a human-in-the-loop review pipeline. Built for the CreditKasa AI Engineer vacancy.

## Architecture

```
Customer Query
     │
     ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  n8n / API   │───▶│  1. Classify  │───▶│ 2. RAG Search   │
│  (Webhook)   │    │  (Intent)    │    │ (Qdrant)        │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                │
                                                ▼
                   ┌──────────────┐    ┌─────────────────┐
                   │ 4. Human     │◀───│ 3. Generate     │
                   │ Review Queue │    │ Draft (GPT-4o)  │
                   └──────────────┘    └─────────────────┘
```

**Pipeline:** Intake → Intent Classification → RAG Retrieval → Draft Generation → Human Review

## Tech Stack

| Component          | Technology                        |
|--------------------|-----------------------------------|
| Orchestration      | n8n (workflow automation)         |
| LLM                | OpenAI GPT-4o-mini                |
| Embeddings         | text-embedding-3-small            |
| Vector DB          | Qdrant                            |
| Backend API        | Python FastAPI                    |
| Dashboard          | Vanilla HTML/CSS/JS               |
| Infrastructure     | Docker Compose                    |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- OpenAI API key

### 1. Clone & Configure

```bash
git clone git@github.com:VMSemchenko/creditkasa-demo.git
cd creditkasa-demo
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start All Services

```bash
docker-compose up -d --build
```

This starts:
- **Qdrant** → `http://localhost:6333`
- **n8n** → `http://localhost:5678`
- **FastAPI** → `http://localhost:8000` (Swagger docs at `/docs`)

### 3. Ingest Policy Documents

```bash
# Option A: Run inside Docker
docker exec -it creditkasa_api python -m src.ingest_policies

# Option B: Run locally
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/ingest_policies.py
```

### 4. Open the Human Review Dashboard

Open `dashboard/index.html` in your browser. You can submit customer queries and review AI-generated draft responses.

### 5. Import the n8n Workflow (Optional)

1. Open n8n at `http://localhost:5678`
2. Go to **Workflows → Import from File**
3. Select `workflows/support_pipeline.json`
4. Activate the workflow

## API Endpoints

| Method | Endpoint                    | Description                          |
|--------|-----------------------------|--------------------------------------|
| POST   | `/api/classify`             | Classify a customer query intent     |
| POST   | `/api/search`               | RAG search against policy documents  |
| POST   | `/api/generate-draft`       | Full pipeline: classify → search → draft |
| GET    | `/api/queue`                | List all drafts pending review       |
| POST   | `/api/queue/{id}/approve`   | Approve a draft response             |
| POST   | `/api/queue/{id}/reject`    | Reject a draft response              |
| GET    | `/api/health`               | Health check                         |

### Example Request

```bash
curl -X POST http://localhost:8000/api/generate-draft \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Я втратив роботу і не можу сплатити кредит цього місяця. Що мені робити?",
    "customer_id": "LOAN-12345"
  }'
```

## Project Structure

```
creditkasa-demo/
├── docker-compose.yml          # Qdrant + n8n + API
├── Dockerfile                  # FastAPI container
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── docs/                       # Knowledge base (mock policies)
│   ├── mock_loan_policy.md     # Loan restructuring rules
│   ├── overdue_payment_guidelines.md
│   └── general_faq.md
│
├── src/
│   ├── config.py               # Shared config & client factories
│   ├── ingest_policies.py      # RAG ingestion script
│   └── api.py                  # FastAPI backend (full pipeline)
│
├── workflows/
│   └── support_pipeline.json   # Importable n8n workflow
│
└── dashboard/
    └── index.html              # Human review UI
```

## Key Design Decisions

1. **Structured Outputs:** All LLM responses use `response_format={"type": "json_object"}` to ensure predictable parsing.
2. **Hallucination Control:** The generation prompt explicitly forbids inventing data and restricts the LLM to citing only the provided policy excerpts.
3. **Source Attribution:** Every draft includes `cited_sources` so the human reviewer can verify the response.
4. **Human-in-the-Loop:** No response is sent to the customer without explicit human approval via the review dashboard.
