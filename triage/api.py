"""REST API for the triage assistant.

Run:  uvicorn triage.api:app --reload
Docs: http://localhost:8000/docs
"""
from fastapi import Depends, FastAPI, HTTPException, Query

from . import config
from .models import TriageRequest, TriageResult
from .service import TriageService, get_service

app = FastAPI(
    title="AI Network Fault Triage Assistant",
    description="RAG + LLM agent that suggests root causes and fixes from past network faults.",
    version="1.0.0",
)


@app.get("/health")
def health(service: TriageService = Depends(get_service)):
    return {
        "status": "ok",
        "mode": "llm" if service.use_llm else "offline",
        "embedder": service.kb.embedder.name,
        "indexed_faults": service.kb.count(),
        "fault_api": config.FAULT_API_URL or "in-memory mock",
    }


@app.post("/triage", response_model=TriageResult)
def triage(request: TriageRequest, service: TriageService = Depends(get_service)):
    try:
        return service.triage(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Triage failed: {exc}") from exc


@app.get("/similar")
def similar(q: str = Query(..., min_length=3), k: int = Query(5, ge=1, le=20),
            service: TriageService = Depends(get_service)):
    return [h.to_dict() for h in service.kb.search(q, k=k)]
