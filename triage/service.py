"""Single entry point used by the API, the UI and the evaluation script."""
from __future__ import annotations

from functools import lru_cache

from . import config
from .agent import TriageAgent
from .fault_api import FaultApi, get_fault_api
from .knowledge_base import KnowledgeBase
from .models import TriageRequest, TriageResult
from .offline import offline_triage


class TriageService:
    def __init__(self, kb: KnowledgeBase, fault_api: FaultApi, use_llm: bool | None = None,
                 llm_client=None):
        self.kb = kb
        self.api = fault_api
        self.use_llm = config.llm_enabled() if use_llm is None else use_llm
        self.agent = TriageAgent(kb, fault_api, client=llm_client) if self.use_llm else None

    def triage(self, request: TriageRequest) -> TriageResult:
        if self.agent:
            return self.agent.triage(request)
        result = offline_triage(self.kb, request.description)
        if request.create_ticket and request.device_name:
            ticket = self.api.create_fault(
                title=request.description[:120], device_name=request.device_name,
                severity=result.suggested_severity, description=request.description)
            result.actions_taken.append({"action": "create_fault_ticket", "result": ticket})
        return result


@lru_cache
def get_service() -> TriageService:
    kb = KnowledgeBase.from_history(persist_dir=config.CHROMA_DIR)
    return TriageService(kb, get_fault_api())
