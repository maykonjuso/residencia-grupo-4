"""Testes unitários e de integração do calendário acadêmico estruturado (Issue #57)."""

from datetime import date
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag import __main__ as cli, api, config
from rumo_rag.agentes.agente_fluxo import AgenteFluxo
from rumo_rag.agentes.mensagem import Mensagem
from rumo_rag.calendario import (
    CalendarioAcademico,
    carregar_calendario,
    validar_schema,
    verificar_vigencia_catalogo,
)


def test_catalogo_calendarios_todos_tem_vigencia():
    cat = yaml.safe_load(config.CATALOGO.read_text(encoding="utf-8"))
    cals = [d for d in cat["documentos"] if d.get("tipo") == "calendario"]
    assert {d["id"] for d in cals} == {"F29", "F30", "F57", "F58"}
    for d in cals:
        vig = d.get("vigencia")
        assert isinstance(vig, dict), f"{d['id']} sem vigencia no catalogo.yaml"
        assert vig.get("inicio") and vig.get("fim")
        assert vig["inicio"] <= vig["fim"]


def test_json_estruturado_existe_e_respeita_schema():
    cal = CalendarioAcademico.construir_do_catalogo()
    validar_schema(cal.dados)
    assert config.CALENDARIO_JSON.exists()
    dados_disco = json.loads(config.CALENDARIO_JSON.read_text(encoding="utf-8"))
    validar_schema(dados_disco)
    assert {s["semestre"] for s in cal.semestres} == {"2026.2", "2026.4"}


def test_consultas_por_data_issue_57():
    cal = carregar_calendario()

    r_20nov = cal.consultar_data("2026-11-20")
    assert r_20nov["status"] == "feriado"
    assert r_20nov["tem_aula"] is False
    assert r_20nov["bloqueia_agenda"] is True
    assert "Consciência Negra" in r_20nov["feriado"]["nome"]

    r_28out = cal.consultar_data(date(2026, 10, 28))
    assert r_28out["status"] == "ponto_facultativo"
    assert r_28out["tem_aula"] is None
    assert r_28out["bloqueia_agenda"] is False
    assert "Servidor" in r_28out["ponto_facultativo"]["nome"]

    r_24dez = cal.consultar_data("24/12/2026")
    assert r_24dez["status"] == "fora_periodo_aulas"
    assert r_24dez["tem_aula"] is False
    assert r_24dez["bloqueia_agenda"] is True
    assert "14/12/2026" in r_24dez["resumo"]
    assert "11/01/2027" in r_24dez["resumo"]
    assert r_24dez["ponto_facultativo"] is not None
    assert "13h" in (r_24dez["ponto_facultativo"]["horario"] or "")

    r_25dez = cal.consultar_data("2026-12-25")
    assert r_25dez["status"] == "feriado"
    assert r_25dez["tem_aula"] is False
    assert r_25dez["bloqueia_agenda"] is True

    r_dom = cal.consultar_data("2026-11-22")
    assert r_dom["status"] == "domingo"
    assert r_dom["tem_aula"] is False
    assert r_dom["bloqueia_agenda"] is True

    r_letivo = cal.consultar_data("2026-11-23")
    assert r_letivo["status"] == "dia_letivo_regular"
    assert r_letivo["tem_aula"] is True
    assert r_letivo["bloqueia_agenda"] is False
    assert r_letivo["semestre"] == "2026.2"

    r_verao_fer = cal.consultar_data("2027-01-01")
    assert r_verao_fer["status"] == "feriado"
    assert r_verao_fer["tem_aula"] is False
    assert r_verao_fer["bloqueia_agenda"] is True

    r_verao_aula = cal.consultar_data("2027-01-12")
    assert r_verao_aula["status"] == "dia_letivo_regular"
    assert r_verao_aula["tem_aula"] is True
    assert r_verao_aula["semestre"] == "2026.4"


def test_nao_aplica_calendario_vencido():
    cal = carregar_calendario()
    r_futuro = cal.consultar_data("2030-05-01")
    assert r_futuro["vigente"] is False
    assert r_futuro["status"] == "sem_calendario_vigente"
    assert r_futuro["tem_aula"] is None
    assert r_futuro["bloqueia_agenda"] is False

    aud = verificar_vigencia_catalogo("2026-11-20", cal.documentos_calendario)
    por_id = {x["id"]: x for x in aud}
    assert por_id["F30"]["status"] == "vencido"
    assert por_id["F30"]["utilizavel"] is False
    assert por_id["F57"]["status"] == "vigente"
    assert por_id["F58"]["status"] == "futuro"

    sem_vig = verificar_vigencia_catalogo("2026-11-20", [{"id": "X1", "titulo": "Sem vigência"}])
    assert sem_vig[0]["status"] == "sem_vigencia"
    assert sem_vig[0]["utilizavel"] is False


def test_filtrar_aulas_do_dia_para_agenda():
    cal = carregar_calendario()
    aulas = [
        {"disciplina": "Testes de Software", "horario": "10:00", "sala": "I-10"},
        {"disciplina": "Compiladores", "horario": "14:00", "sala": "S-1"},
    ]

    f_feriado = cal.filtrar_aulas_do_dia("2026-11-20", aulas)
    assert f_feriado["bloqueia_agenda"] is True
    assert f_feriado["aulas_ativas"] == []
    assert len(f_feriado["aulas_canceladas"]) == 2

    f_fora = cal.filtrar_aulas_do_dia("2026-12-24", aulas)
    assert f_fora["bloqueia_agenda"] is True
    assert f_fora["aulas_ativas"] == []

    f_letivo = cal.filtrar_aulas_do_dia("2026-11-23", aulas)
    assert f_letivo["bloqueia_agenda"] is False
    assert len(f_letivo["aulas_ativas"]) == 2
    assert f_letivo["aulas_canceladas"] == []

    f_pf = cal.filtrar_aulas_do_dia("2026-10-28", aulas)
    assert f_pf["bloqueia_agenda"] is False
    assert f_pf["tem_aula"] is None
    assert len(f_pf["aulas_ativas"]) == 2


def test_integracao_api_com_data_e_endpoint_calendario():
    ctx_feriado = api.Contexto(campus="gama", data=date(2026, 11, 19))
    expandida = api.com_data("Amanhã tem aula?", ctx_feriado)
    assert "20/11/2026" in expandida
    assert "feriado" in expandida.lower()

    client = TestClient(api.app)
    r_raiz = client.get("/")
    assert r_raiz.status_code == 200
    assert "/calendario" in r_raiz.json()["rotas"]

    r_cal = client.get("/calendario", params={"data": "2026-11-20"})
    assert r_cal.status_code == 200
    body = r_cal.json()
    assert body["status"] == "feriado"
    assert body["tem_aula"] is False
    assert body["bloqueia_agenda"] is True

    r_all = client.get("/calendario")
    assert r_all.status_code == 200
    assert len(r_all.json()["semestres"]) == 2


def test_integracao_agente_fluxo_e_cli():
    agente = AgenteFluxo()
    msg = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Tem aula no dia 20 de novembro?",
        contexto={"data": "2026-11-19"},
    )
    resp = agente.executar(msg)
    assert "[1]" in resp.conteudo
    assert "Consciência Negra" in resp.conteudo
    assert resp.fontes[0]["doc_id"] == "F57"
    assert msg.contexto["calendario"]["bloqueia_agenda"] is True

    cli_20nov = cli.responder("Tem aula no dia 20 de novembro?", backend="extrativo")
    assert cli_20nov["sem_citacao"] is False
    assert cli_20nov["valores_sem_fonte"] == []
    assert "Consciência Negra" in cli_20nov["resposta"]

    cli_28out = cli.responder("O dia 28 de outubro é feriado na UnB?", backend="extrativo")
    assert "ponto facultativo" in cli_28out["resposta"].lower()
    assert "não é feriado" in cli_28out["resposta"].lower()

    cli_24dez = cli.responder("Tem aula no dia 24 de dezembro?", backend="extrativo")
    assert "14/12/2026" in cli_24dez["resposta"]
    assert "11/01/2027" in cli_24dez["resposta"]
    assert cli_24dez["valores_sem_fonte"] == []
