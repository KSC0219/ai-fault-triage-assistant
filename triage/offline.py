"""Retrieval-only triage, used when no LLM API key is configured.

It runs a similarity-weighted vote over the top-k retrieved faults to pick the
category, then reuses the most relevant root causes and fixes from that category.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .knowledge_base import KnowledgeBase
from .models import TriageResult


def offline_triage(kb: KnowledgeBase, description: str, k: int = 5) -> TriageResult:
    hits = kb.search(description, k=k)
    if not hits:
        raise ValueError("Knowledge base is empty")

    votes: dict[str, float] = defaultdict(float)
    for h in hits:
        # cube the similarity so the closest matches dominate the vote
        votes[h.category] += max(h.similarity, 0.0) ** 3
    category = max(votes, key=votes.get)
    total = sum(votes.values()) or 1.0
    confidence = round(votes[category] / total, 2)

    same = [h for h in hits if h.category == category]
    severity = Counter(h.severity for h in same).most_common(1)[0][0]
    root_cause = Counter(h.root_cause for h in same).most_common(1)[0][0]

    steps, seen = [], set()
    for h in same:
        if h.resolution not in seen:
            seen.add(h.resolution)
            steps.append(h.resolution)

    return TriageResult(
        mode="offline",
        likely_category=category,
        suggested_severity=severity,
        likely_root_cause=root_cause,
        recommended_steps=steps[:3],
        confidence=confidence,
        cited_fault_ids=[h.id for h in same[:3]],
        similar_faults=[h.to_dict() for h in hits[:5]],
        summary=(f"Looks like {category.replace('_', ' ')} "
                 f"({confidence:.0%} of the similar past faults agree)."),
    )
