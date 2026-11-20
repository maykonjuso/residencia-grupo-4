import sys
from pathlib import Path
import pytest

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag import indice
from rumo_rag.agentes.agente_fluxo import AgenteFluxo


def test_agente_fluxo_busca_no_eixo_correto(monkeypatch):
    chamadas = {}

    def busca_falsa(pergunta, **kwargs):
        chamadas["pergunta"] = pergunta
        chamadas.update(kwargs)
        return [{
            "doc_id": "doc-001",
            "pagina": 1,
            "url": "https://exemplo.com",
            "titulo": "Fluxo do curso",
        }]

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    resultado = AgenteFluxo().pesquisar("Quais são os pré-requisitos?")

    assert chamadas["eixo"] == "fluxo"
    assert chamadas["decompor_pergunta"] is False
    assert resultado["agente"] == "Agente Fluxo"
    assert resultado["encontrou"] is True
    assert len(resultado["fontes"]) == 1


def test_agente_fluxo_rejeita_pergunta_vazia():
    with pytest.raises(ValueError):
        AgenteFluxo().pesquisar("   ")