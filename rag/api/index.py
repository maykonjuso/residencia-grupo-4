"""Entrypoint ASGI da API do RUmo para deploy serverless no Vercel (Root Directory: rag/)."""
import sys
from pathlib import Path

_RAG_ROOT = str(Path(__file__).resolve().parent.parent)
if _RAG_ROOT not in sys.path:
    sys.path.insert(0, _RAG_ROOT)

from rumo_rag.api import app  # noqa: E402, F401
