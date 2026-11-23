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
    msg_det = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
        contexto={"backend": "extrativo"},
    )

    with patch("rumo_rag.geracao.gerar_com_instrucoes") as gerar, patch(
        "rumo_rag.agentes.agente_fluxo.indice.buscar"
    ) as buscar:
        resp_det = AgenteFluxo().executar(msg_det)

    gerar.assert_not_called()
    buscar.assert_not_called()
    assert "FGA0314" in resp_det.conteudo
    assert resp_det.fontes[0]["doc_id"] == "F16"
    assert msg_det.contexto["trechos_recuperados"][0]["doc_id"] == "F16"
    assert msg_det.contexto["tempo_geracao_s"] == 0.0
    assert msg_det.contexto["ferramenta_chamada"]["redigido_por_llm"] is False

    msg_llm = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
        contexto={"backend": "ollama"},
    )
    with patch(
        "rumo_rag.geracao.gerar_com_instrucoes",
        return_value="Reprovando em Requisitos de Software, travam FGA0314 e FGA0317. [1]",
    ) as gerar_llm, patch("rumo_rag.agentes.agente_fluxo.indice.buscar") as buscar_llm:
        resp_llm = AgenteFluxo().executar(msg_llm)

    gerar_llm.assert_called_once()
    buscar_llm.assert_not_called()
    assert "FGA0314" in resp_llm.conteudo
    assert "FGA0317" in resp_llm.conteudo
    assert msg_llm.contexto["ferramenta_chamada"]["redigido_por_llm"] is True


def test_cli_padrao_encaminha_perguntas_de_impacto_ao_grafo():
    with patch("rumo_rag.__main__.indice.decompor", side_effect=AssertionError), patch(
        "rumo_rag.__main__.indice.buscar_com_subperguntas", side_effect=AssertionError
    ), patch("rumo_rag.__main__.geracao.gerar", side_effect=AssertionError), patch(
        "rumo_rag.geracao.gerar_com_instrucoes",
        return_value="Travam Testes de Software (FGA0314) e GCES (FGA0317). [1]",
    ):
        resultado = cli.responder(
            "Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
            backend="ollama",
        )

    assert resultado["backend"] == "grafo"
    assert "FGA0314" in resultado["resposta"]
    assert "FGA0317" in resultado["resposta"]
    assert resultado["fontes_citadas"][0]["doc_id"] == "F16"


def test_grafo_usa_networkx_digraph_e_valida_schema_json():
    import json
    import networkx as nx
    import pytest
    from rumo_rag.grafo_curricular import Aresta, GRAFO_JSON

    assert GRAFO_JSON.exists()
    dados = json.loads(GRAFO_JSON.read_text(encoding="utf-8"))
    GrafoCurricular.validar_json(dados)

    grafo = GrafoCurricular.carregar_json(GRAFO_JSON)
    assert isinstance(grafo.grafo, nx.DiGraph)
    assert nx.is_directed_acyclic_graph(grafo.grafo)
    assert grafo.grafo.number_of_nodes() == 47
    assert grafo.caminho_critico() == list(nx.dag_longest_path(grafo.grafo))

    estruturado = grafo.consultar_estruturado("Qual disciplina destrava mais matérias?")
    assert estruturado is not None
    assert estruturado["tipo_consulta"] == "gargalo"
    assert estruturado["dados"]["gargalos"][0]["codigo"] == "CIC0004"

    # Detecção de ciclo no DiGraph
    with pytest.raises(ValueError, match="ciclo"):
        GrafoCurricular(
            disciplinas={
                "CIC0004": grafo.disciplinas["CIC0004"],
                "FGA0158": grafo.disciplinas["FGA0158"],
            },
            arestas=[
                Aresta("CIC0004", "FGA0158", "pre_requisito", False, "teste"),
                Aresta("FGA0158", "CIC0004", "pre_requisito", False, "teste"),
            ],
        )


def test_repositorio_cobre_todos_os_5_cursos_fcte_com_dags_validos():
    import networkx as nx
    from rumo_rag.grafo_curricular import GRAFO_JSON, RepositorioGrafos

    repo = RepositorioGrafos.carregar_json(GRAFO_JSON)
    resumos = repo.listar_curriculos()
    cursos_slug = {r["curso_slug"] for r in resumos}
    ids = {r["curriculo_id"] for r in resumos}

    assert cursos_slug == {"software", "aeroespacial", "eletronica", "automotiva", "energia"}
    assert {
        "software-2024-2",
        "aeroespacial-2025",
        "eletronica-2023",
        "automotiva-2018-2026",
        "automotiva-2027",
        "energia-2024",
    } <= ids

    for cid, grafo in repo.curriculos.items():
        assert nx.is_directed_acyclic_graph(grafo.grafo), cid
        assert grafo.vigencia["inicio"]
        assert grafo.vigencia["descricao"]


def test_aeroespacial_e_eletronica_respondem_prerequisitos_corequisitos_e_gargalos():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_aero = repo.consultar_estruturado("Quais os pré-requisitos de Mecânica do Voo em Aeroespacial?")
    assert res_aero is not None
    assert res_aero["dados"]["curriculo_id"] == "aeroespacial-2025"
    cods_aero = {c["codigo"] for c in res_aero["dados"]["confirmados"]}
    assert cods_aero == {"FGA0008", "FGA0038"}
    assert res_aero["fonte"]["doc_id"] == "F17"
    assert "PPC 2025" in res_aero["texto"]

    res_el = repo.consultar_estruturado(
        "Quais os pré-requisitos e correquisitos de Teoria de Eletrônica Digital 1 em Eletrônica?"
    )
    assert res_el is not None
    assert res_el["dados"]["curriculo_id"] == "eletronica-2023"
    assert res_el["dados"]["confirmados"][0]["codigo"] == "MAT0031"
    assert res_el["dados"]["correquisitos"][0]["codigo"] == "FGA0071"
    assert res_el["fonte"]["doc_id"] == "F21"
    assert "PPC 2023" in res_el["texto"]


def test_automotiva_coexiste_com_duas_vigencias_e_recusa_prerequisitos_sem_inventar():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_2027 = repo.consultar_estruturado(
        "Quais os pré-requisitos de Dinâmica de Veículos em Automotiva 2027?"
    )
    assert res_2027 is not None
    assert res_2027["tipo_consulta"] == "prerequisitos_indisponiveis"
    assert res_2027["dados"]["curriculo_id"] == "automotiva-2027"
    assert res_2027["dados"]["cobertura_prerequisitos"] == "indisponivel_na_base"
    assert any(o["curriculo_id"] == "automotiva-2018-2026" for o in res_2027["dados"]["outras_vigencias"])
    assert res_2027["fonte"]["doc_id"] == "F19"

    res_2018 = repo.consultar_estruturado(
        "Disciplinas do 3º nível de Engenharia Automotiva para ingressantes de 2020"
    )
    assert res_2018 is not None
    assert res_2018["tipo_consulta"] == "vigencia_curriculo"
    assert res_2018["dados"]["curriculo_id"] == "automotiva-2018-2026"
    assert any("Ergonomia" in d["nome"] or "Ondulatória" in d["nome"] for d in res_2018["dados"]["disciplinas"])
    assert all(not d["codigo_oficial"] for d in res_2018["dados"]["disciplinas"])


def test_energia_responde_grade_e_nao_inventa_prerequisitos():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()
    res_pre = repo.consultar_estruturado("Quais os pré-requisitos de Biorrefinarias em Engenharia de Energia?")
    assert res_pre is not None
    assert res_pre["tipo_consulta"] == "prerequisitos_indisponiveis"
    assert res_pre["dados"]["curriculo_id"] == "energia-2024"
    assert res_pre["fonte"]["doc_id"] == "F23"


def test_equivalencias_e_resolucao_por_codigo_antigo():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_eq_sw = repo.consultar_estruturado("Qual a equivalência de FGA0172?")
    assert res_eq_sw is not None
    assert res_eq_sw["tipo_consulta"] == "equivalencias"
    assert res_eq_sw["dados"]["curriculo_id"] == "software-2024-2"
    assert res_eq_sw["dados"]["equivalencias"][0]["codigo"] == "FGA0313"
    assert "FGA0172" in res_eq_sw["dados"]["equivalencias"][0]["equivalentes"]

    res_eq_el = repo.consultar_estruturado("Qual a equivalência de FGA0308 em Engenharia Eletrônica?")
    assert res_eq_el is not None
    assert res_eq_el["dados"]["curriculo_id"] == "eletronica-2023"
    assert res_eq_el["dados"]["equivalencias"][0]["equivalentes"] == ["FGA0096"]
    assert res_eq_el["fonte"]["doc_id"] == "F21"

    # Perguntar pré-requisitos usando código antigo (FGA0238 -> FGA0314 Testes de Software)
    res_antigo = repo.consultar_estruturado("Quais os pré-requisitos de FGA0238?")
    assert res_antigo is not None
    assert res_antigo["tipo_consulta"] == "prerequisitos"
    assert res_antigo["dados"]["disciplina"]["codigo"] == "FGA0314"
    assert "FGA0238" in res_antigo["texto"]
