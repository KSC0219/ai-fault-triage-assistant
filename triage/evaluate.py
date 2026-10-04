"""Evaluate retrieval and triage quality on the hand-written test set.

Metrics
  hit@1, hit@3, hit@5  share of questions where a past fault of the right category is in the top k
  MRR                  mean reciprocal rank of the first correct result
  triage accuracy      share of questions where the final predicted category is correct

Usage
  python -m triage.evaluate              # retrieval + offline triage
  python -m triage.evaluate --llm        # also evaluate the LLM agent (needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import config
from .fault_api import MockFaultApi
from .knowledge_base import KnowledgeBase
from .models import TriageRequest
from .offline import offline_triage

EVAL_PATH = config.ROOT / "eval" / "eval_set.json"
RESULTS_PATH = config.ROOT / "eval" / "results.json"


def evaluate_retrieval(kb: KnowledgeBase, items: list[dict], k: int = 5) -> dict:
    hits = {1: 0, 3: 0, 5: 0}
    rr_total = 0.0
    for item in items:
        cats = [h.category for h in kb.search(item["query"], k=k)]
        for n in hits:
            if item["expected_category"] in cats[:n]:
                hits[n] += 1
        if item["expected_category"] in cats:
            rr_total += 1 / (cats.index(item["expected_category"]) + 1)
    n = len(items)
    return {**{f"hit@{k}": round(v / n, 3) for k, v in hits.items()}, "mrr": round(rr_total / n, 3)}


def evaluate_triage(triage_fn, items: list[dict]) -> dict:
    correct, failures, start = 0, [], time.time()
    for item in items:
        predicted = triage_fn(item["query"]).likely_category
        if predicted == item["expected_category"]:
            correct += 1
        else:
            failures.append({"query": item["query"], "expected": item["expected_category"],
                             "predicted": predicted})
    return {
        "accuracy": round(correct / len(items), 3),
        "avg_seconds": round((time.time() - start) / len(items), 3),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also evaluate the LLM agent")
    args = parser.parse_args()

    items = json.loads(EVAL_PATH.read_text())
    kb = KnowledgeBase.from_history()
    print(f"Embedder: {kb.embedder.name} | indexed faults: {kb.count()} | questions: {len(items)}\n")

    report = {"embedder": kb.embedder.name, "questions": len(items)}
    report["retrieval"] = evaluate_retrieval(kb, items)
    print("Retrieval:", report["retrieval"])

    report["offline_triage"] = evaluate_triage(lambda q: offline_triage(kb, q), items)
    print("Offline triage accuracy:", report["offline_triage"]["accuracy"])

    if args.llm:
        from .agent import TriageAgent
        agent = TriageAgent(kb, MockFaultApi())
        report["llm_triage"] = evaluate_triage(
            lambda q: agent.triage(TriageRequest(description=q)), items)
        print("LLM agent triage accuracy:", report["llm_triage"]["accuracy"])

    RESULTS_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nSaved full report (including failures) to {RESULTS_PATH.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
