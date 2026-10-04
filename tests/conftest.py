import pytest

from triage.embeddings import HashingEmbedder
from triage.fault_api import MockFaultApi
from triage.knowledge_base import KnowledgeBase


@pytest.fixture(scope="session")
def kb():
    # The hashing embedder keeps the tests fast and fully offline.
    return KnowledgeBase.from_history(embedder=HashingEmbedder())


@pytest.fixture
def fault_api():
    return MockFaultApi()
