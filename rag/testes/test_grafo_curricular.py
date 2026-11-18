from unittest.mock import patch

from rumo_rag import __main__ as cli
from rumo_rag.agentes.agente_fluxo import AgenteFluxo
from rumo_rag.agentes.mensagem import Mensagem
from rumo_rag.grafo_curricular import GrafoCurricular


def carregar_grafo():
    return GrafoCurricular.carregar_f16()


def test_extrai_nos_e_relacoes_da_transcricao_f16():
    grafo = carregar_grafo()

    assert grafo.disciplinas["FGA0313"].nome == "Requisitos de Software"
    assert grafo.disciplinas["FGA0313"].semestre == 5
    assert grafo.disciplinas["FGA0313"].creditos == 4
    assert any(
        aresta.origem == "FGA0312"
        and aresta.destino == "FGA0314"
        and aresta.incerta
        for aresta in grafo.arestas
    )
    assert any(aresta.relacao == "correquisito" for aresta in grafo.arestas)


def test_reprovar_em_requisitos_retorna_dependentes_transitivos_confirmados():
    consulta = carregar_grafo().consultar(
        "Se eu reprovar em Requisitos de Software, quais disciplinas travam?"
    )

    assert consulta is not None
    assert "Testes de Software (FGA0314)" in consulta.conteudo
    assert "Gerência de Configuração e Evolução de Software (GCES) (FGA0317)" in consulta.conteudo
    assert "[1]" in consulta.conteudo


def test_gargalo_e_calculado_pelo_grau_de_saida_do_grafo():
    consulta = carregar_grafo().consultar(
        "Qual disciplina de Engenharia de Software destrava mais matérias?"
    )

    assert consulta is not None
    assert "CIC0004" in consulta.conteudo
    assert "FGA0158" in consulta.conteudo
    assert "FGA0146" in consulta.conteudo
    assert "setas cheias" in consulta.conteudo


def test_pre_requisito_tracejado_permanece_incerto_e_pede_confirmacao_sigaa():
    consulta = carregar_grafo().consultar("Quais os pré-requisitos de Testes de Software?")

    assert consulta is not None
    assert "Requisitos de Software (FGA0313)" in consulta.conteudo
    assert "Métodos de Desenvolvimento de Software (MDS) (FGA0312)" in consulta.conteudo
    assert "ligação tracejada" in consulta.conteudo
    assert "confirme no SIGAA" in consulta.conteudo


def test_passar_em_requisitos_sinaliza_testes_como_relacao_incerta():
    consulta = carregar_grafo().consultar("Passando em Requisitos de Software, o que abre?")

    assert consulta is not None
    assert "Testes de Software (FGA0314)" in consulta.conteudo
    assert "ligação é tracejada" in consulta.conteudo
    assert "confirme no SIGAA" in consulta.conteudo


def test_caminho_critico_e_a_cadeia_mais_longa_de_setas_cheias():
    consulta = carregar_grafo().consultar("Qual é o caminho crítico de pré-requisitos?")

    assert consulta is not None
    assert "CIC0004" in consulta.conteudo
    assert "FGA0317" in consulta.conteudo
    assert "não uma previsão de semestres até a formatura" in consulta.conteudo


def test_agente_fluxo_responde_consulta_do_grafo_sem_chamar_llm_ou_indice():
    mensagem = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
        contexto={"backend": "ollama"},
    )

    with patch("rumo_rag.agentes.agente_fluxo.geracao.gerar_com_instrucoes") as gerar, patch(
        "rumo_rag.agentes.agente_fluxo.indice.buscar"
    ) as buscar:
        resposta = AgenteFluxo().executar(mensagem)

    gerar.assert_not_called()
    buscar.assert_not_called()
    assert "FGA0314" in resposta.conteudo
    assert resposta.fontes[0]["doc_id"] == "F16"
    assert mensagem.contexto["trechos_recuperados"][0]["doc_id"] == "F16"
    assert mensagem.contexto["tempo_geracao_s"] == 0.0


def test_cli_padrao_encaminha_perguntas_de_impacto_ao_grafo():
    with patch("rumo_rag.__main__.indice.decompor", side_effect=AssertionError), patch(
        "rumo_rag.__main__.indice.buscar_com_subperguntas", side_effect=AssertionError
    ), patch("rumo_rag.__main__.geracao.gerar", side_effect=AssertionError):
        resultado = cli.responder(
            "Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
            backend="ollama",
        )

    assert resultado["backend"] == "grafo"
    assert "FGA0314" in resultado["resposta"]
    assert "FGA0317" in resultado["resposta"]
    assert resultado["fontes_citadas"][0]["doc_id"] == "F16"
