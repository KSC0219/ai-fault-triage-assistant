import json

from triage import config
from triage.evaluate import evaluate_retrieval
from triage.offline import offline_triage


def test_all_history_indexed(kb):
    assert kb.count() == len(json.loads(config.HISTORY_PATH.read_text()))


def test_search_returns_relevant_category(kb):
    hits = kb.search("BGP neighbor keeps flapping with the ISP", k=3)
    assert hits[0].category == "bgp_flap"
    assert hits[0].similarity >= hits[-1].similarity


def test_search_with_category_filter(kb):
    hits = kb.search("network is down", k=5, category="stp_loop")
    assert hits and all(h.category == "stp_loop" for h in hits)


def test_empty_query_returns_nothing(kb):
    assert kb.search("   ") == []


def test_offline_triage_structure(kb):
    result = offline_triage(kb, "users get 169.254 addresses and no DHCP lease")
    assert result.mode == "offline"
    assert result.likely_category == "dhcp_exhaustion"
    assert result.recommended_steps
    assert 0 < result.confidence <= 1
    assert set(result.cited_fault_ids) <= {f["id"] for f in result.similar_faults}


def test_retrieval_quality_does_not_regress(kb):
    items = json.loads((config.ROOT / "eval" / "eval_set.json").read_text())
    metrics = evaluate_retrieval(kb, items)
    assert metrics["hit@3"] >= 0.85
