import pytest

from rumo_rag import indice
from rumo_rag.agentes import AgenteRU


def test_agente_ru_busca_no_eixo_correto(monkeypatch):
    chamadas = {}

    def busca_falsa(pergunta, **kwargs):
        chamadas["pergunta"] = pergunta
        chamadas.update(kwargs)

        return [{
            "chunk_id": "F04-0001",
            "doc_id": "F04",
            "titulo": "Valores das refeições",
            "orgao": "UnB",
            "pagina": 1,
            "secao": "Valores",
            "url": "https://exemplo.com",
            "texto": "O almoço para Grupo II custa R$ 4,50.",
        }]

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    agente = AgenteRU()
    resultado = agente.pesquisar("Quanto custa o almoço no RU?")

    assert chamadas["eixo"] == "ru"
    assert chamadas["decompor_pergunta"] is False
    assert resultado["agente"] == "Agente RU"
    assert resultado["encontrou"] is True
    assert len(resultado["fontes"]) == 1


def test_agente_ru_cardapio_consulta_apenas_json_e_valida_semana(monkeypatch, tmp_path):
    import json
    from datetime import date
    from rumo_rag import geracao
    from rumo_rag.agentes import Mensagem
    from rumo_rag.coleta import cardapio

    def nao_deve_chamar_rag(*args, **kwargs):
        raise AssertionError("AgenteRU não deve consultar a RAG para perguntas de cardápio")

    monkeypatch.setattr(indice, "buscar", nao_deve_chamar_rag)

    json_path = tmp_path / "cardapio_semanal.json"
    json_path.write_text(json.dumps({
        "unidade": "gama",
        "semana": {"inicio": "2026-11-16", "fim": "2026-11-22"},
        "atualizado_em": "2026-11-18T12:00:00",
        "fonte": {"doc_id": "F37", "url": "https://ru.unb.br/cardapio.pdf"},
        "alergenicos": {"disponivel": True, "legenda": []},
        "refeicoes": [{
            "unidade": "gama",
            "data": "2026-11-18",
            "refeicao": "almoco",
            "compartimentos": [{
                "slot": "principal",
                "titulo": "Prato principal",
                "max": 1,
                "opcoes": [{
                    "id": "risoto",
                    "nome": "Risoto de ervilha com queijo",
                    "trilha": "ovolacto",
                    "alergenicos": ["leite", "gluten"],
                    "fonte": {"doc_id": "F37", "pagina": 2, "chunk_id": "F37-0008"},
                }],
            }],
            "mesa_apoio": [],
            "alergenicos": {"disponivel": True, "legenda": [], "observacao": ""},
            "fonte": {"doc_id": "F37", "pagina": 2, "chunk_id": "F37-0008", "url": "https://ru.unb.br/cardapio.pdf"},
            "avisos": [],
        }],
    }), encoding="utf-8")

    orig_carregar = cardapio.carregar_semana_atual
    monkeypatch.setattr(
        cardapio,
        "carregar_semana_atual",
        lambda hoje=None, caminho=json_path: orig_carregar(hoje=date(2026, 11, 18), caminho=json_path),
    )

    agente = AgenteRU()
    res = agente.pesquisar("O que tem no almoço de quarta-feira e tem derivados de leite?")
    assert res["encontrou"] is True
    assert res["trechos"][0]["doc_id"] == "F37"
    assert "[Alergênicos: leite, gluten]" in res["trechos"][0]["texto"]

    # Semana desatualizada: deve recusar mesmo sem RAG
    monkeypatch.setattr(
        cardapio,
        "carregar_semana_atual",
        lambda hoje=None, caminho=json_path: orig_carregar(hoje=date(2026, 11, 25), caminho=json_path),
    )
    res_antigo = agente.pesquisar("O que tem no almoço de hoje?")
    assert res_antigo["encontrou"] is False
    assert "desatualizado" in (res_antigo.get("aviso_cardapio") or "")

    resp = agente.executar(Mensagem(remetente="Orq", destinatario="Agente RU", conteudo="Qual o cardápio do almoço?", contexto={"backend": "extrativo"}))
    assert resp.conteudo == geracao.RECUSA


def test_agente_ru_sem_resultados(monkeypatch):
    monkeypatch.setattr(indice, "buscar", lambda *args, **kwargs: [])

    agente = AgenteRU()
    resultado = agente.pesquisar("Qual é o horário de funcionamento?")

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
    resultado = agente.pesquisar("Qual o horário do RU?")

    assert len(resultado["trechos"]) == 2
    assert len(resultado["fontes"]) == 1


def test_agente_ru_limpa_pergunta(monkeypatch):
    chamadas = {}

    def busca_falsa(pergunta, **kwargs):
        chamadas["pergunta"] = pergunta
        return []

    monkeypatch.setattr(indice, "buscar", busca_falsa)

    agente = AgenteRU()
    agente.pesquisar("  Qual o horário do RU?  ")

    assert chamadas["pergunta"] == "Qual o horário do RU?"


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
