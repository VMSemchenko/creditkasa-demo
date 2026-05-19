"""
FastAPI backend for the CreditKasa Support AI Copilot.
Uses Google Gemini for LLM inference.

Endpoints:
  POST /api/classify       – Classify a customer query intent
  POST /api/search         – Search Qdrant for relevant policy chunks
  POST /api/generate-draft – Full pipeline: classify → search → generate draft
  GET  /api/queue          – List all draft responses pending human review
  POST /api/queue/{id}/approve – Approve a draft
  POST /api/queue/{id}/reject  – Reject a draft
  GET  /api/health         – Health check
"""
import uuid
import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai

from config import (
    GOOGLE_API_KEY,
    GEMINI_MODEL,
    QDRANT_URL,
    COLLECTION_NAME,
    get_embeddings,
    get_qdrant_client,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CreditKasa Support AI Copilot",
    version="0.1.0",
    description="AI-powered support draft generation with human-in-the-loop review.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

# ---------------------------------------------------------------------------
# In-memory review queue (would be a DB in production)
# ---------------------------------------------------------------------------
review_queue: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CustomerQuery(BaseModel):
    query: str = Field(..., min_length=3, description="The customer's support message")
    customer_id: str | None = Field(None, description="Optional customer/loan identifier")


class ClassificationResult(BaseModel):
    intent: str
    confidence: float
    language: str


class SearchResult(BaseModel):
    content: str
    source_document: str
    relevance_score: float


class DraftResponse(BaseModel):
    id: str
    customer_query: str
    customer_id: str | None
    intent: str
    confidence: float
    draft_reply: str
    cited_sources: list[str]
    status: str  # "pending_review" | "approved" | "rejected"
    created_at: str


# ---------------------------------------------------------------------------
# Helper: call Gemini with JSON output
# ---------------------------------------------------------------------------
def call_gemini(system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
    """Call Gemini and parse the JSON response."""
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


# ---------------------------------------------------------------------------
# 1. Intent Classification
# ---------------------------------------------------------------------------
CLASSIFY_SYSTEM_PROMPT = """You are an intent classifier for CreditKasa, a Ukrainian online lending company.
Given a customer support query, classify it into exactly ONE of these intents:
- restructuring_request: Client wants to restructure their loan, extend terms, or get payment relief.
- overdue_inquiry: Client is asking about overdue status, penalties, or payment deadlines.
- repayment_question: Client asks how to pay, overpayment refund, or extension request.
- loan_application: Client asks about loan amounts, interest rates, eligibility, or application status.
- account_security: Client reports unauthorized access, password issues, or account lockout.
- general_question: Any other question that doesn't fit the above categories.

Respond with a valid JSON object only:
{"intent": "<intent>", "confidence": <0.0-1.0>, "language": "<uk|en|ru>"}"""


@app.post("/api/classify", response_model=ClassificationResult)
async def classify_query(payload: CustomerQuery):
    """Classify the customer query into a predefined intent category."""
    result = call_gemini(CLASSIFY_SYSTEM_PROMPT, payload.query, temperature=0.0)
    return ClassificationResult(**result)


# ---------------------------------------------------------------------------
# 2. RAG Search
# ---------------------------------------------------------------------------
@app.post("/api/search", response_model=list[SearchResult])
async def search_policies(payload: CustomerQuery):
    """Search Qdrant for the top-3 most relevant policy chunks."""
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(payload.query)

    client = get_qdrant_client()
    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=3,
        with_payload=True,
    )

    results = []
    for point in hits.points:
        results.append(
            SearchResult(
                content=point.payload.get("page_content", ""),
                source_document=point.payload.get("metadata", {}).get(
                    "source_document", "unknown"
                ),
                relevance_score=round(point.score, 4),
            )
        )
    return results


# ---------------------------------------------------------------------------
# 3. Full Pipeline: Classify → Search → Generate Draft
# ---------------------------------------------------------------------------
GENERATE_SYSTEM_PROMPT = """You are a senior support agent AI copilot at CreditKasa, a Ukrainian online lending company.
Your task is to draft a professional, empathetic response to a customer query based ONLY on the provided internal policy excerpts.

RULES:
1. ONLY use information from the provided policy excerpts. If the answer is not in the excerpts, say "I need to escalate this to a senior agent."
2. Be empathetic and professional. Use the formal "Ви" form in Ukrainian.
3. Always cite which policy document you are referencing.
4. If the customer writes in Ukrainian, respond in Ukrainian. If in English, respond in English.
5. Never invent interest rates, penalties, loan amounts, or deadlines that are not explicitly stated in the policy excerpts.
6. Keep the response concise but complete (2-4 paragraphs max).

Respond with a valid JSON object:
{
  "draft_reply": "<your drafted response to the customer>",
  "cited_sources": ["<source_document_1.md>", "<source_document_2.md>"]
}"""


@app.post("/api/generate-draft", response_model=DraftResponse)
async def generate_draft(payload: CustomerQuery):
    """Full pipeline: classify intent, retrieve relevant policies, generate a draft response."""

    # Step 1: Classify
    classification = await classify_query(payload)

    # Step 2: Search for relevant context
    search_results = await search_policies(payload)
    context_block = "\n\n---\n\n".join(
        [
            f"[Source: {r.source_document} | Relevance: {r.relevance_score}]\n{r.content}"
            for r in search_results
        ]
    )

    # Step 3: Generate draft with grounded context
    user_message = f"""Customer Query: {payload.query}
Detected Intent: {classification.intent}
Customer ID: {payload.customer_id or 'N/A'}

--- INTERNAL POLICY EXCERPTS (use ONLY this information) ---

{context_block}

--- END OF EXCERPTS ---

Please draft a response to the customer based on the above information."""

    generation = call_gemini(GENERATE_SYSTEM_PROMPT, user_message, temperature=0.3)

    # Step 4: Queue for human review
    draft_id = str(uuid.uuid4())[:8]
    draft = DraftResponse(
        id=draft_id,
        customer_query=payload.query,
        customer_id=payload.customer_id,
        intent=classification.intent,
        confidence=classification.confidence,
        draft_reply=generation["draft_reply"],
        cited_sources=generation.get("cited_sources", []),
        status="pending_review",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    review_queue[draft_id] = draft.model_dump()

    return draft


# ---------------------------------------------------------------------------
# 4. Human Review Queue
# ---------------------------------------------------------------------------
@app.get("/api/queue", response_model=list[DraftResponse])
async def get_review_queue():
    """Return all items in the review queue."""
    return list(review_queue.values())


@app.post("/api/queue/{draft_id}/approve")
async def approve_draft(draft_id: str):
    """Approve a draft response."""
    if draft_id not in review_queue:
        raise HTTPException(status_code=404, detail="Draft not found")
    review_queue[draft_id]["status"] = "approved"
    return {"message": f"Draft {draft_id} approved.", "draft": review_queue[draft_id]}


@app.post("/api/queue/{draft_id}/reject")
async def reject_draft(draft_id: str):
    """Reject a draft response."""
    if draft_id not in review_queue:
        raise HTTPException(status_code=404, detail="Draft not found")
    review_queue[draft_id]["status"] = "rejected"
    return {"message": f"Draft {draft_id} rejected.", "draft": review_queue[draft_id]}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "model": GEMINI_MODEL, "collection": COLLECTION_NAME}
