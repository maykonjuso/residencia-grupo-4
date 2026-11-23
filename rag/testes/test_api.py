"""Testes da API HTTP multiagente (contrato v1.0 #44 e entrypoint Vercel)."""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag import api, config, geracao  # noqa: E402
from rumo_rag.coleta import cardapio  # noqa: E402

CHAVES_V1 = {
    "grupo",
    "resposta",
    "encontrou_base",
    "fontes",
    "valores_sem_fonte",
    "backend",
    "tempo_ms",
}
CHAVES_FONTE_V1 = {"n", "doc_id", "titulo", "orgao", "pagina", "url"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "BUSCA", "bm25")
    monkeypatch.setattr(config, "BACKEND", "extrativo")
    monkeypatch.setattr(config, "USAR_D1", False)
    monkeypatch.setattr(api, "TOKEN", "")
    orig_carregar = cardapio.carregar_semana_atual
    monkeypatch.setattr(
        cardapio,
        "carregar_semana_atual",
        lambda hoje=None, caminho=config.CARDAPIO_SEMANAL_JSON: orig_carregar(
            hoje=date(2026, 11, 20), caminho=config.CARDAPIO_SEMANAL_JSON
        ),
    )
    return TestClient(api.app)


def test_raiz_responde_status_multiagente(client):
    r = client.get("/")
    assert r.status_code == 200
    dados = r.json()
    assert dados["status"] == "ok"
    assert dados["multiagente"] is True
    assert "/perguntar" in dados["rotas"]
    assert "/saude" in dados["rotas"]


def test_saude_mantem_contrato_e_informa_multiagente(client):
    r = client.get("/saude")
    assert r.status_code == 200
    dados = r.json()
    for campo in ("status", "grupo", "busca", "backend", "token", "modelo", "chunks"):
        assert campo in dados
    assert dados["status"] == "ok"
    assert dados["grupo"] == "grupo04"
    assert dados["multiagente"] is True
    assert dados["agentes"] == [
        "Agente RU",
        "Agente Fluxo",
        "Agente Validador",
        "Sintetizador",
    ]
    assert dados["cardapio_semanal"] is True


def test_perguntar_criterio_issue_44_preserva_contrato_v1_estrito(client):
    r = client.post(
        "/perguntar",
        json={
            "pergunta": "Quais os pré-requisitos de Testes de Software?",
            "contexto": {"campus": "gama"},
            "max_trechos": 5,
        },
    )
    assert r.status_code == 200
    dados = r.json()
    assert set(dados.keys()) == CHAVES_V1
    assert "trace" not in dados
    assert dados["grupo"] == "grupo04"
    assert dados["encontrou_base"] is True
    assert dados["backend"] == "extrativo"
    assert isinstance(dados["tempo_ms"], int)
    assert dados["fontes"]
    for fonte in dados["fontes"]:
        assert set(fonte.keys()) == CHAVES_FONTE_V1
        assert isinstance(fonte["n"], int)
        assert isinstance(fonte["pagina"], int)


def test_perguntar_inclui_trace_quando_pedido_no_body_ou_query(client):
    r_body = client.post(
        "/perguntar",
        json={"pergunta": "Quais os pré-requisitos de Testes de Software?", "trace": True},
    )
    assert r_body.status_code == 200
    d_body = r_body.json()
    assert set(d_body.keys()) == CHAVES_V1 | {"trace"}
    assert {"subperguntas", "etapas", "interacoes", "degradado", "avisos"} <= set(
        d_body["trace"].keys()
    )

    r_query = client.post(
        "/perguntar?trace=true",
        json={"pergunta": "Quais os pré-requisitos de Testes de Software?"},
    )
    assert r_query.status_code == 200
    assert "trace" in r_query.json()


def test_perguntar_multiagente_composto_ru_e_fluxo(client):
    r = client.post(
        "/perguntar?trace=true",
        json={
            "pergunta": (
                "Qual o prato vegano do almoço de 20/11/2026? "
                "E quais os pré-requisitos de Testes de Software?"
            ),
            "contexto": {"campus": "gama", "data": "2026-11-20"},
            "max_trechos": 5,
        },
    )
    assert r.status_code == 200
    dados = r.json()
    assert dados["grupo"] == "grupo04"
    assert dados["encontrou_base"] is True
    docs = {f["doc_id"] for f in dados["fontes"]}
    assert "F56" in docs
    assert "F16" in docs
    assert len(dados["trace"]["subperguntas"]) == 2
    assert dados["trace"]["degradado"] is False


def test_perguntar_faz_fallback_para_extrativo_quando_llm_falha(client, monkeypatch):
    monkeypatch.setattr(config, "BACKEND", "openai")
    monkeypatch.setattr(
        geracao,
        "_gerar_openai",
        lambda msgs: (_ for _ in ()).throw(RuntimeError("OpenRouter indisponível")),
    )

    r = client.post(
        "/perguntar",
        json={"pergunta": "Quais os pré-requisitos de Testes de Software?"},
    )
    assert r.status_code == 200
    dados = r.json()
    assert dados["backend"] == "extrativo"
    assert dados["encontrou_base"] is True
    assert dados["fontes"]
    assert "OpenRouter" not in dados["resposta"]


def test_autenticacao_bearer_token(client, monkeypatch):
    monkeypatch.setattr(api, "TOKEN", "segredo-rumo-g4")

    sem = client.post("/perguntar", json={"pergunta": "Quanto custa o almoço?"})
    assert sem.status_code == 401

    errado = client.post(
        "/perguntar",
        json={"pergunta": "Quanto custa o almoço?"},
        headers={"Authorization": "Bearer errado"},
    )
    assert errado.status_code == 401

    ok = client.post(
        "/perguntar",
        json={"pergunta": "Quanto custa o almoço?"},
        headers={"Authorization": "Bearer segredo-rumo-g4"},
    )
    assert ok.status_code == 200
    assert ok.json()["grupo"] == "grupo04"


def test_entrypoint_vercel_expoe_app(client):
    entrypoint = _RAG / "api" / "index.py"
    spec = importlib.util.spec_from_file_location("vercel_api_index", entrypoint)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    assert mod.app is api.app
    vc_client = TestClient(mod.app)
    r = vc_client.get("/saude")
    assert r.status_code == 200
    assert r.json()["multiagente"] is True
