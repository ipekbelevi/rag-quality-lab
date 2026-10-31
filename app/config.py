"""Central configuration: reads .env once and exposes model names and paths.

Every other module imports settings from here, so swapping a model
(e.g. a cheaper judge) is a one-line change in .env, not a code change.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# System under test
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-haiku-5-5")

# Evaluator side (kept on a different provider than the chatbot)
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4.1-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Paths
DOCS_DIR = PROJECT_ROOT / "data" / "docs"
GOLDEN_DIR = PROJECT_ROOT / "data" / "golden"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
