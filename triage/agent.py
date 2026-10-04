"""LLM triage agent that uses tool calling.

The model gets four tools:
  search_similar_faults  RAG lookup in the vector store of resolved faults
  get_device_history     fault history for a device, from the Fault Management API
  create_fault_ticket    opens a ticket through the API (only when the user allows it)
  submit_triage          final structured answer; ends the loop

The loop runs until the model calls submit_triage or MAX_AGENT_STEPS is reached.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from . import config
from .fault_api import FaultApi
from .knowledge_base import KnowledgeBase
from .models import TriageRequest, TriageResult
from .offline import offline_triage

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a network operations (NOC) triage assistant.
Given a fault description, you:
1. ALWAYS call search_similar_faults first, and search again with different wording if the results look unrelated.
2. If a device is named, call get_device_history to check for repeat issues.
3. Base the root cause and steps on the retrieved past faults, and cite their ids. Do not invent fixes that are not supported by the history unless you clearly label them as general advice.
4. Only call create_fault_ticket if ticket creation is allowed for this request.
5. Finish by calling submit_triage exactly once.
Severity guide: CRITICAL = many users or a whole site down; HIGH = a service degraded or redundancy lost; MEDIUM = partial or intermittent impact; LOW = a single user."""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_similar_faults",
        "description": "Semantic search over historically resolved network faults. Returns the most similar past faults with their root cause and resolution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Symptoms to search for"},
                "k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_device_history",
        "description": "Get previously reported faults for a specific device from the Fault Management API.",
        "input_schema": {
            "type": "object",
            "properties": {"device_name": {"type": "string"}},
            "required": ["device_name"],
        },
    },
    {
        "name": "create_fault_ticket",
        "description": "Open a new fault ticket in the Fault Management API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "device_name": {"type": "string"},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "description": {"type": "string"},
            },
            "required": ["title", "device_name", "severity"],
        },
    },
    {
        "name": "submit_triage",
        "description": "Submit the final triage result. Call this exactly once at the end.",
        "input_schema": {
            "type": "object",
            "properties": {
                "likely_category": {"type": "string", "description": "Category of the most similar past faults, e.g. bgp_flap"},
                "suggested_severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "likely_root_cause": {"type": "string"},
                "recommended_steps": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "cited_fault_ids": {"type": "array", "items": {"type": "integer"}},
                "summary": {"type": "string", "description": "2-3 sentence explanation for the engineer"},
            },
            "required": ["likely_category", "suggested_severity", "likely_root_cause",
                         "recommended_steps", "confidence", "cited_fault_ids", "summary"],
        },
    },
]


def _block_to_dict(block: Any) -> dict:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return dict(block.__dict__)


class TriageAgent:
    def __init__(self, kb: KnowledgeBase, fault_api: FaultApi, client: Any = None,
                 model: str = config.ANTHROPIC_MODEL, max_steps: int = config.MAX_AGENT_STEPS):
        self.kb = kb
        self.api = fault_api
        self.model = model
        self.max_steps = max_steps
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    # ---- tool implementations -------------------------------------------------
    def _run_tool(self, name: str, args: dict, request: TriageRequest, state: dict) -> Any:
        if name == "search_similar_faults":
            hits = self.kb.search(args["query"], k=int(args.get("k", 5)))
            for h in hits:
                state["similar"].setdefault(h.id, h.to_dict())
            return [h.to_dict() for h in hits]
        if name == "get_device_history":
            return self.api.device_history(args["device_name"])
        if name == "create_fault_ticket":
            if not request.create_ticket:
                return {"error": "Ticket creation is not allowed for this request."}
            ticket = self.api.create_fault(
                title=args["title"], device_name=args["device_name"],
                severity=args["severity"], description=args.get("description", ""))
            state["actions"].append({"action": "create_fault_ticket", "result": ticket})
            return ticket
        return {"error": f"Unknown tool {name}"}

    # ---- main loop ------------------------------------------------------------
    def triage(self, request: TriageRequest) -> TriageResult:
        user_msg = f"Fault description: {request.description}"
        if request.device_name:
            user_msg += f"\nDevice: {request.device_name}"
        user_msg += f"\nTicket creation allowed: {'yes' if request.create_ticket else 'no'}"

        messages: list[dict] = [{"role": "user", "content": user_msg}]
        state: dict = {"similar": {}, "actions": []}

        for step in range(self.max_steps):
            response = self.client.messages.create(
                model=self.model, max_tokens=1500, system=SYSTEM_PROMPT,
                tools=TOOLS, messages=messages,
            )
            blocks = [_block_to_dict(b) for b in response.content]
            messages.append({"role": "assistant", "content": blocks})

            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                messages.append({"role": "user", "content": "Please call submit_triage with your final answer."})
                continue

            results = []
            for tu in tool_uses:
                if tu["name"] == "submit_triage":
                    return self._finish(tu["input"], state)
                try:
                    output = self._run_tool(tu["name"], tu["input"], request, state)
                    results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                    "content": json.dumps(output, default=str)})
                except Exception as exc:
                    log.exception("tool %s failed", tu["name"])
                    results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                    "content": f"Tool error: {exc}", "is_error": True})
            messages.append({"role": "user", "content": results})

        log.warning("Agent did not submit within %d steps; falling back to offline triage", self.max_steps)
        result = offline_triage(self.kb, request.description)
        result.actions_taken = state["actions"]
        return result

    def _finish(self, final: dict, state: dict) -> TriageResult:
        similar = list(state["similar"].values())
        similar.sort(key=lambda s: s["similarity"], reverse=True)
        return TriageResult(
            mode="llm",
            likely_category=final["likely_category"],
            suggested_severity=final["suggested_severity"],
            likely_root_cause=final["likely_root_cause"],
            recommended_steps=final["recommended_steps"],
            confidence=max(0.0, min(1.0, float(final["confidence"]))),
            cited_fault_ids=[int(i) for i in final.get("cited_fault_ids", [])],
            similar_faults=similar[:5],
            actions_taken=state["actions"],
            summary=final.get("summary", ""),
        )
