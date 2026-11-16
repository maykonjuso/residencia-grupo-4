"""Pacote raiz para utilitários de avaliação e benchmark do RUmo RAG."""
import sys
from .avaliacao.scripts import benchmark, calibrar_limiar

sys.modules.setdefault(f"{__name__}.benchmark", benchmark)
sys.modules.setdefault(f"{__name__}.calibrar_limiar", calibrar_limiar)
