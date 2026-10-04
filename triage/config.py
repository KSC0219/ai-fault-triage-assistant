import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = Path(os.getenv("FAULT_HISTORY_PATH", ROOT / "data" / "fault_history.json"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", ROOT / ".chroma"))
COLLECTION = "resolved_faults"

# "auto" uses sentence-transformers when installed, otherwise the offline hashing embedder.
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "auto")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "6"))

# Base URL of the Spring Boot Network Fault Management API. Empty = use the in-memory mock.
FAULT_API_URL = os.getenv("FAULT_API_URL", "")


def llm_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))
