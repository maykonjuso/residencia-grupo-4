"""Testes de privacidade e tratamento efêmero de documentos pessoais (#59, LGPD)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag import api, config, geracao, privacidade  # noqa: E402
from rumo_rag.agentes import AgenteFluxo, Mensagem, ferramentas  # noqa: E402


def _gerar_pdf_sintetico_bytes(linhas: list[str]) -> bytes:
    """Constrói um PDF %PDF-1.4 mínimo em memória, sem gravação em disco."""
    comandos = ["BT", "/F1 11 Tf", "50 760 Td"]
    for idx, linha in enumerate(linhas):
        segura = (
            linha.encode("latin-1", "replace")
            .decode("latin-1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        if idx > 0:
            comandos.append("0 -16 Td")
        comandos.append(f"({segura}) Tj")
    comandos.append("ET")
    stream = "\n".join(comandos).encode("latin-1")

    objetos = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        ),
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objetos:
        offsets.append(len(buf))
        buf.extend(obj)

    pos_xref = len(buf)
    buf.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    buf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.extend(
        (
            f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
            f"startxref\n{pos_xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(buf)


def test_sanitizacao_estrita_descarta_pii_e_mantem_quatro_campos():
    bruto = {
        "disciplinas": [
            {
                "codigo": "fga0314",
                "turma": "01",
                "horario": "35T23",
                "sala": "I10",
                "disciplina": "Testes de Software",
                "nota": "SS",
                "professor": "Beltrano",
            },
            {
                "codigo": "MAT0026",
                "turma": "A",
                "horario": "24M12",
                "sala": "123.456.789-00",
                "cpf": "123.456.789-00",
            },
            {"codigo": "123456789", "turma": "01", "horario": "24M12", "sala": "S1"},
        ],
        "nome": "Fulano Ficticio",
        "cpf": "123.456.789-00",
        "matricula": "22/1022560",
        "ira": 4.21,
        "reprovacoes": ["FGA0001"],
    }

    limpo = privacidade.sanitizar_perfil_contexto(bruto)
    assert limpo is not None
    assert set(limpo.keys()) == {"disciplinas"}
    assert len(limpo["disciplinas"]) == 2
    assert limpo["disciplinas"][0] == {
        "codigo": "FGA0314",
        "turma": "01",
        "horario": "35T23",
        "sala": "I10",
    }
    assert limpo["disciplinas"][1] == {
        "codigo": "MAT0026",
        "turma": "A",
        "horario": "24M12",
        "sala": "",
    }
    serializado = json.dumps(limpo, ensure_ascii=False)
    for proibido in ("123.456.789-00", "22/1022560", "Fulano", "Beltrano", "4.21", "FGA0001"):
        assert proibido not in serializado


def test_processar_comprovante_em_memoria_nao_grava_em_disco_nem_expoe_pii(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_bytes = _gerar_pdf_sintetico_bytes([
        "SIGAA - Sistema Integrado de Gestao de Atividades Academicas",
        "Atestado de Matricula",
        "Nome: FULANO DE TAL FICTICIO   CPF: 123.456.789-00   Matricula: 22/1022560",
        "IRA: 4.35   Mencao anterior: MM   Reprovacoes: 0",
        "FGA0314 Testes de Software 01 35T23 Sala I10",
        "CIC0004 Algoritmos e Programacao de Computadores 02 24M12 Sala MOCAP",
    ])

    with (
        mock.patch.object(tempfile, "NamedTemporaryFile", side_effect=AssertionError("Não deve criar temp file")),
        mock.patch.object(tempfile, "mkstemp", side_effect=AssertionError("Não deve usar mkstemp")),
    ):
        res = privacidade.processar_comprovante_em_memoria(pdf_bytes)

    assert res["sucesso"] is True
    assert res["recusado"] is False
    assert res["tipo_documento"] == "comprovante_matricula"
    assert res["persistido_em_servidor"] is False
    assert res["enviado_llm_externo"] is False
    assert list(tmp_path.iterdir()) == []
    assert os.listdir(tmp_path) == []

    assert len(res["disciplinas"]) == 2
    for item in res["disciplinas"]:
        assert set(item.keys()) == set(privacidade.CAMPOS_PERMITIDOS_DOCUMENTO)

    assert res["disciplinas"][0] == {
        "codigo": "FGA0314",
        "turma": "01",
        "horario": "35T23",
        "sala": "I10",
    }
    assert res["disciplinas"][1] == {
        "codigo": "CIC0004",
        "turma": "02",
        "horario": "24M12",
        "sala": "MOCAP",
    }

    serializado = json.dumps(res, ensure_ascii=False)
    for dado_sensivel in ("FULANO", "123.456.789-00", "22/1022560", "4.35", "Reprovacoes", "MM"):
        assert dado_sensivel not in serializado


def test_recusa_historico_escolar_sem_horarios():
    pdf_historico = _gerar_pdf_sintetico_bytes([
        "Universidade de Brasilia - SIGAA",
        "Historico Escolar",
        "Indice de Rendimento Academico (IRA): 4.10",
        "2025.1 FGA0312 METODOS DE DESENVOLVIMENTO DE SOFTWARE 4 CR MS",
        "2025.2 FGA0313 REQUISITOS DE SOFTWARE 4 CR II",
    ])

    res = privacidade.processar_comprovante_em_memoria(pdf_historico)
    assert res["sucesso"] is False
    assert res["recusado"] is True
    assert res["tipo_documento"] == "historico_escolar"
    assert res["motivo"] == "historico_escolar_nao_suportado"
    assert res["disciplinas"] == []
    assert "Atestado de Matrícula" in res["mensagem"]


def test_validar_pdf_rejeita_arquivo_nao_pdf_ou_vazio():
    with pytest.raises(ValueError):
        privacidade.validar_pdf_em_memoria(b"")
    with pytest.raises(ValueError):
        privacidade.validar_pdf_em_memoria(b"conteudo texto plano sem header pdf")
    with pytest.raises(ValueError):
        privacidade.validar_pdf_em_memoria(b"%PDF-1.4\n" + b"0" * (privacidade.MAX_BYTES_PDF + 1))


def test_decodificar_horario_sigaa_e_minha_agenda_com_quatro_campos():
    slots = privacidade.decodificar_horario_sigaa("35T23")
    assert slots == [
        {"dia": "terça-feira", "horario": "14:00-15:50"},
        {"dia": "quinta-feira", "horario": "14:00-15:50"},
    ]

    perfil = {
        "disciplinas": [
            {"codigo": "FGA0314", "turma": "01", "horario": "35T23", "sala": "I10"},
            {"codigo": "MAT0026", "turma": "B", "horario": "24M34", "sala": "S1"},
        ],
        "cpf": "123.456.789-00",
        "nome": "Nome Proibido",
    }
    res = ferramentas.minha_agenda("terça", perfil=perfil)
    assert res.sucesso is True
    assert len(res.dados["aulas"]) == 1
    aula = res.dados["aulas"][0]
    assert aula["codigo"] == "FGA0314"
    assert aula["turma"] == "01"
    assert aula["horario"] == "14:00-15:50"
    assert aula["sala"] == "I10"
    assert "14:00-15:50" in res.texto_base
    assert "Turma 01" in res.texto_base
    assert "Sala I10" in res.texto_base
    assert "123.456.789-00" not in res.texto_base
    assert "Nome Proibido" not in res.texto_base


def test_dados_pessoais_nunca_vao_para_llm_externo():
    res = ferramentas.minha_agenda(
        "terça",
        perfil={"disciplinas": [{"codigo": "FGA0314", "turma": "01", "horario": "35T23", "sala": "I10"}]},
    )

    with mock.patch.object(geracao, "gerar_com_instrucoes") as mock_llm:
        texto, duracao, alertas, redigido = ferramentas.redigir_com_ferramenta(
            "Quais minhas aulas de terça?",
            res,
            "instrucoes",
            backend="openai",
        )
        mock_llm.assert_not_called()

    assert redigido is False
    assert duracao == 0.0
    assert texto == res.texto_base
    assert any("LLM externo" in a for a in alertas)

    agente = AgenteFluxo(modo="bm25")
    msg = Mensagem(
        remetente="orq",
        destinatario=agente.nome,
        conteudo="Qual minha agenda de terça-feira?",
        contexto={
            "backend": "openai",
            "perfil": {
                "disciplinas": [{"codigo": "FGA0314", "turma": "01", "horario": "35T23", "sala": "I10"}],
                "cpf": "123.456.789-00",
            },
        },
    )
    with mock.patch.object(geracao, "gerar_com_instrucoes") as mock_llm_agente:
        resp = agente.executar(msg)
        mock_llm_agente.assert_not_called()

    assert "FGA0314" in resp.conteudo
    assert "14:00-15:50" in resp.conteudo
    assert "123.456.789-00" not in resp.conteudo


def test_redacao_local_permitida_com_backend_ollama():
    res = ferramentas.minha_agenda(
        "terça",
        perfil={"disciplinas": [{"codigo": "FGA0314", "turma": "01", "horario": "35T23", "sala": "I10"}]},
    )
    with mock.patch.object(geracao, "gerar_com_instrucoes", return_value="Sua aula de terça é às 14:00-15:50 na Sala I10 [1].") as mock_ollama:
        texto, _, _, redigido = ferramentas.redigir_com_ferramenta(
            "Quais minhas aulas de terça?",
            res,
            "instrucoes",
            backend="ollama",
        )
        mock_ollama.assert_called_once()
    assert redigido is True
    assert "14:00-15:50" in texto


def test_api_expoe_politica_e_sanitiza_perfil_em_perguntar(monkeypatch):
    monkeypatch.setattr(config, "BUSCA", "bm25")
    monkeypatch.setattr(config, "BACKEND", "extrativo")
    monkeypatch.setattr(config, "USAR_D1", False)
    monkeypatch.setattr(api, "TOKEN", "")

    client = TestClient(api.app)

    r_pol = client.get("/privacidade/documento")
    assert r_pol.status_code == 200
    pol = r_pol.json()
    assert pol["campos_permitidos"] == ["codigo", "turma", "horario", "sala"]
    assert pol["armazenamento_servidor"] is False
    assert pol["envio_llm_externo"] is False
    assert "Antes de selecionar o arquivo" in pol["aviso_antes_upload"]
    assert "OpenRouter" in pol["aviso_antes_upload"]

    perfis_recebidos = []
    orig_executar = api.Orquestrador.executar

    def _spy_executar(self, pergunta, **kwargs):
        perfis_recebidos.append(kwargs.get("perfil"))
        return orig_executar(self, pergunta, **kwargs)

    monkeypatch.setattr(api.Orquestrador, "executar", _spy_executar)

    r_perg = client.post(
        "/perguntar",
        json={
            "pergunta": "Quais minhas aulas de terça-feira?",
            "contexto": {
                "campus": "gama",
                "perfil": {
                    "nome": "Fulano Ficticio",
                    "cpf": "123.456.789-00",
                    "notas": {"FGA0314": "SS"},
                    "disciplinas": [
                        {
                            "codigo": "FGA0314",
                            "turma": "01",
                            "horario": "35T23",
                            "sala": "I10",
                            "nota": "SS",
                        }
                    ],
                },
            },
        },
    )
    assert r_perg.status_code == 200
    dados = r_perg.json()
    assert dados["encontrou_base"] is True
    assert "14:00-15:50" in dados["resposta"]
    assert "Sala I10" in dados["resposta"]
    assert "Fulano" not in dados["resposta"]
    assert "123.456.789-00" not in dados["resposta"]

    assert len(perfis_recebidos) == 1
    assert perfis_recebidos[0] == {
        "disciplinas": [
            {"codigo": "FGA0314", "turma": "01", "horario": "35T23", "sala": "I10"}
        ]
    }


def test_comprovante_solicitacao_matricula_layout_real_sigaa_sintetico(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_sigaa = _gerar_pdf_sintetico_bytes([
        "Portal Discente",
        "U NIVERSIDADE DE B RASÍLIA",
        "S ISTEMA I NTEGRADO DE G ESTÃO DE A TIVIDADES A CADÊMICAS",
        "C OMPROVANTE DE S OLICITAÇÃO DE M ATRÍCULA N° 999999",
        "P ERÍODO 2026.2",
        "Matrícula: 99/9999999",
        "Discente: ESTUDANTE FICTICIO DA SILVA",
        "Curso: ENGENHARIA DE SOFTWARE/FCTE - Bacharelado - Presencial",
        "Status: ATIVO",
        "T URMAS SELECIONADAS",
        "Componente Curricular Turma Local Situação",
        "FGA0211 - FUNDAMENTOS DE REDES DE COMPUTADORES - 60h Turma 01 FCTE - MOCAP INDEFERIDA",
        "FGA0210 - PARADIGMAS DE PROGRAMAÇÃO - 60h Turma 01 FCTE - S4 DEFERIDA",
        "FGA0274 - PRODUTIVIDADE E PROFISSIONALISMO EM ENGENHARIA DE",
        "SOFTWARE - 60h Turma 01 FCTE - I5 INDEFERIDA",
        "FGA0160 - MÉTODOS NUMÉRICOS PARA ENGENHARIA - 60h Turma 02 FCTE - S1 / S4 INDEFERIDA",
        "FGA0109 - FUNDAMENTOS DE SISTEMAS EMBARCADOS - 60h (REMATRICULA) Turma 02 FCTE - I10 AGUARDANDO PROCESSAMENTO",
        "FGA0160 - MÉTODOS NUMÉRICOS PARA ENGENHARIA - 60h (REMATRICULA) Turma 01 FCTE - I9 DEFERIDA",
        "Horários Seg Ter Qua Qui Sex Sáb",
        "08:00 - 08:55 --- --- --- --- --- ---",
        "10:00 - 10:55 --- --- --- --- --- ---",
        "12:00 - 12:55 FGA0160 --- FGA0160 --- --- ---",
        "12:55 - 13:50 FGA0160 --- FGA0160 --- --- ---",
        "14:00 - 14:55 --- --- --- --- --- ---",
        "16:00 - 16:55 --- FGA0210 --- FGA0210 --- ---",
        "16:55 - 17:50 --- FGA0210 --- FGA0210 --- ---",
        "Para verificar a autenticidade deste documento acesse https://sigaa.example.invalid/",
        "Número do Documento: 999999",
        "Código de Verificação: abcdef1234",
    ])

    res = privacidade.processar_comprovante_em_memoria(pdf_sigaa)
    assert res["sucesso"] is True
    assert res["recusado"] is False
    assert res["tipo_documento"] == "comprovante_matricula"
    assert res["persistido_em_servidor"] is False
    assert res["enviado_llm_externo"] is False
    assert list(tmp_path.iterdir()) == []

    assert res["disciplinas"] == [
        {"codigo": "FGA0210", "turma": "01", "horario": "35T45", "sala": "FCTE - S4"},
        {"codigo": "FGA0160", "turma": "01", "horario": "24M5 24T1", "sala": "FCTE - I9"},
    ]

    serializado = json.dumps(res, ensure_ascii=False)
    for proibido in (
        "ESTUDANTE FICTICIO",
        "99/9999999",
        "abcdef1234",
        "999999",
        "FGA0211",
        "FGA0274",
        "FGA0109",
        "INDEFERIDA",
        "AGUARDANDO PROCESSAMENTO",
    ):
        assert proibido not in serializado


def test_decodificar_horario_mescla_faixas_contiguas_entre_turnos():
    assert privacidade.decodificar_horario_sigaa("24M5 24T1") == [
        {"dia": "segunda-feira", "horario": "12:00-13:50"},
        {"dia": "quarta-feira", "horario": "12:00-13:50"},
    ]

    res = ferramentas.minha_agenda(
        "segunda",
        perfil={"disciplinas": [{"codigo": "FGA0160", "turma": "01", "horario": "24M5 24T1", "sala": "FCTE - I9"}]},
    )
    assert res.sucesso is True
    assert len(res.dados["aulas"]) == 1
    assert res.dados["aulas"][0]["horario"] == "12:00-13:50"
    assert res.dados["aulas"][0]["turma"] == "01"
    assert res.dados["aulas"][0]["sala"] == "FCTE - I9"
    assert "12:00-13:50" in res.texto_base
    assert "Turma 01" in res.texto_base
    assert "Sala FCTE - I9" in res.texto_base

