"""Tests the agent's tool-calling loop with a scripted fake LLM client (no API key needed)."""
import copy
from types import SimpleNamespace

from triage.agent import TriageAgent
from triage.models import TriageRequest


def tool_use(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


class FakeClient:
    """Returns pre-scripted responses and records every request it receives."""

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))  # snapshot: the agent keeps appending to messages
        return SimpleNamespace(content=self.scripted.pop(0))


FINAL = {
    "likely_category": "bgp_flap",
    "suggested_severity": "CRITICAL",
    "likely_root_cause": "MTU mismatch on the ISP link",
    "recommended_steps": ["Check the MTU on both ends"],
    "confidence": 0.8,
    "cited_fault_ids": [1001],
    "summary": "Matches past BGP flaps.",
}


def test_agent_runs_tools_then_submits(kb, fault_api):
    client = FakeClient([
        [tool_use("t1", "search_similar_faults", {"query": "bgp flapping", "k": 3})],
        [tool_use("t2", "get_device_history", {"device_name": "router-blr-01"})],
        [tool_use("t3", "submit_triage", FINAL)],
    ])
    agent = TriageAgent(kb, fault_api, client=client)
    result = agent.triage(TriageRequest(description="BGP keeps flapping", device_name="router-blr-01"))

    assert result.mode == "llm"
    assert result.likely_category == "bgp_flap"
    assert len(result.similar_faults) == 3  # collected from the search tool
    assert len(client.calls) == 3
    # the tool result from step 1 was sent back to the model
    last_user = client.calls[1]["messages"][-1]
    assert last_user["content"][0]["type"] == "tool_result"
    assert last_user["content"][0]["tool_use_id"] == "t1"


def test_ticket_creation_blocked_without_permission(kb, fault_api):
    client = FakeClient([
        [tool_use("t1", "create_fault_ticket",
                  {"title": "BGP down", "device_name": "router-blr-01", "severity": "CRITICAL"})],
        [tool_use("t2", "submit_triage", FINAL)],
    ])
    result = TriageAgent(kb, fault_api, client=client).triage(
        TriageRequest(description="BGP down", create_ticket=False))
    assert fault_api.faults == []
    assert result.actions_taken == []


def test_ticket_created_when_allowed(kb, fault_api):
    client = FakeClient([
        [tool_use("t1", "create_fault_ticket",
                  {"title": "BGP down", "device_name": "router-blr-01", "severity": "CRITICAL"})],
        [tool_use("t2", "submit_triage", FINAL)],
    ])
    result = TriageAgent(kb, fault_api, client=client).triage(
        TriageRequest(description="BGP down", create_ticket=True))
    assert len(fault_api.faults) == 1
    assert result.actions_taken[0]["result"]["status"] == "OPEN"


def test_falls_back_to_offline_when_agent_never_submits(kb, fault_api):
    text_only = [SimpleNamespace(type="text", text="thinking...")]
    client = FakeClient([text_only] * 3)
    agent = TriageAgent(kb, fault_api, client=client, max_steps=3)
    result = agent.triage(TriageRequest(description="DNS names not resolving but ping works"))
    assert result.mode == "offline"
    assert result.likely_category == "dns_failure"
