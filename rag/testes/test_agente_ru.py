import pytest

from rumo_rag import indice
from rumo_rag.agentes import AgenteRU


def test_agente_ru_busca_no_eixo_correto(monkeypatch):
    chamadas = {}

    def busca_falsa(pergunta, **kwargs):
        chamadas["pergunta"] = pergunta
        chamadas.update(kwargs)

        return [{
            "chunk_id": "doc-001-0001",
            "doc_id": "doc-001",
            "titulo": "Cardápio RU",
            "orgao": "UnB",
            "pagina": 1,
            "secao": "Almoço",
            "url": "https://exemplo.com",
            "texto": "Exemplo de informação sobre o almoço.",
        }]

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    agente = AgenteRU()
    resultado = agente.pesquisar("Qual é o cardápio do almoço?")

    assert chamadas["eixo"] == "ru"
    assert chamadas["decompor_pergunta"] is False
    assert resultado["agente"] == "Agente RU"
    assert resultado["encontrou"] is True
    assert len(resultado["fontes"]) == 1


def test_agente_ru_sem_resultados(monkeypatch):
    monkeypatch.setattr(indice, "buscar", lambda *args, **kwargs: [])

    agente = AgenteRU()
    resultado = agente.pesquisar("Qual é o cardápio?")

    assert resultado["encontrou"] is False
    assert resultado["trechos"] == []
    assert resultado["fontes"] == []


def test_agente_ru_rejeita_pergunta_vazia():
    agente = AgenteRU()

    with pytest.raises(ValueError):
        agente.pesquisar("   ")


def test_agente_ru_remove_fontes_duplicadas(monkeypatch):
    def busca_falsa(pergunta, **kwargs):
        return [
            {
                "chunk_id": "doc-001-0001",
                "doc_id": "doc-001",
                "titulo": "Cardápio RU",
                "orgao": "UnB",
                "pagina": 1,
                "secao": "Almoço",
                "url": "https://exemplo.com",
                "texto": "Trecho 1",
            },
            {
                "chunk_id": "doc-001-0002",
                "doc_id": "doc-001",
                "titulo": "Cardápio RU",
                "orgao": "UnB",
                "pagina": 1,
                "secao": "Almoço",
                "url": "https://exemplo.com",
                "texto": "Trecho 2",
            },
        ]

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    agente = AgenteRU()
    resultado = agente.pesquisar("Qual é o cardápio?")

    assert len(resultado["trechos"]) == 2
    assert len(resultado["fontes"]) == 1


def test_agente_ru_limpa_pergunta(monkeypatch):
    chamadas = {}

    def busca_falsa(pergunta, **kwargs):
        chamadas["pergunta"] = pergunta
        return []

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    agente = AgenteRU()
    agente.pesquisar("  Qual é o cardápio?  ")

    assert chamadas["pergunta"] == "Qual é o cardápio?"


def test_agente_ru_rejeita_k_invalido():
    with pytest.raises(ValueError):
        AgenteRU(k=0)

    with pytest.raises(ValueError):
        AgenteRU(k=-1)

    with pytest.raises(ValueError):
        AgenteRU(k=1.5)


def test_agente_ru_rejeita_modo_invalido():
    with pytest.raises(ValueError):
        AgenteRU(modo="invalido")
